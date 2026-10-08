// Tencent is pleased to support the open source community by making ncnn available.
//
// Copyright (C) 2025 THL A29 Limited, a Tencent company. All rights reserved.
//
// Licensed under the BSD 3-Clause License (the "License"); you may not use this file except
// in compliance with the License. You may obtain a copy of the License at
//
// https://opensource.org/licenses/BSD-3-Clause
//
// Unless required by applicable law or agreed to in writing, software distributed
// under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.

#include "ppocrv5.h"

#include <iostream>
#include <vector>
#include <string>
#include <fstream>
#include <stdexcept>

#include <ImageAIModuleLoader.h>

#include "opencv2/core.hpp"
#include "opencv2/core/hal/interface.h"
#include "opencv2/imgcodecs.hpp"
#include "opencv2/imgproc.hpp"

#include <omp.h>

#include "ppocrv5_dict.h"

namespace {

inline int alignN(int x, int n) { return (x + n - 1) & ~(n - 1); }
static double contour_score(const cv::Mat& binary, const std::vector<cv::Point>& contour)
{
    cv::Rect rect = cv::boundingRect(contour);
    if (rect.x < 0)
        rect.x = 0;
    if (rect.y < 0)
        rect.y = 0;
    if (rect.x + rect.width > binary.cols)
        rect.width = binary.cols - rect.x;
    if (rect.y + rect.height > binary.rows)
        rect.height = binary.rows - rect.y;

    cv::Mat binROI = binary(rect);

    cv::Mat mask = cv::Mat::zeros(rect.height, rect.width, CV_8U);
    std::vector<cv::Point> roiContour;
    for (size_t i = 0; i < contour.size(); i++)
    {
        cv::Point pt = cv::Point(contour[i].x - rect.x, contour[i].y - rect.y);
        roiContour.push_back(pt);
    }

    std::vector<std::vector<cv::Point> > roiContours = {roiContour};
    cv::fillPoly(mask, roiContours, cv::Scalar(255));

    double score = cv::mean(binROI, mask).val[0];
    return score / 255.f;
}

static cv::Mat get_rotate_crop_image(const cv::Mat& rgb, const Object& object)
{
    const int orientation = object.orientation;
    const float rw = object.rrect.size.width;
    const float rh = object.rrect.size.height;

    const int target_height = 48;
    const float target_width = rh * target_height / rw;

    // warpperspective shall be used to rotate the image
    // but actually they are all rectangles, so warpaffine is almost enough  :P

    cv::Mat dst;

    cv::Point2f corners[4];
    object.rrect.points(corners);

    if (orientation == 0)
    {
        // horizontal text
        // corner points order
        //  0--------1
        //  |        |rw  -> as angle=90
        //  3--------2
        //      rh

        std::vector<cv::Point2f> src_pts(3);
        src_pts[0] = corners[0];
        src_pts[1] = corners[1];
        src_pts[2] = corners[3];

        std::vector<cv::Point2f> dst_pts(3);
        dst_pts[0] = cv::Point2f(0, 0);
        dst_pts[1] = cv::Point2f(target_width, 0);
        dst_pts[2] = cv::Point2f(0, target_height);

        cv::Mat tm = cv::getAffineTransform(src_pts, dst_pts);

        cv::warpAffine(rgb, dst, tm, cv::Size(target_width, target_height), cv::INTER_LINEAR, cv::BORDER_REPLICATE);
    }
    else
    {
        // vertial text
        // corner points order
        //  1----2
        //  |    |
        //  |    |
        //  |    |rh  -> as angle=0
        //  |    |
        //  |    |
        //  0----3
        //    rw

        std::vector<cv::Point2f> src_pts(3);
        src_pts[0] = corners[2];
        src_pts[1] = corners[3];
        src_pts[2] = corners[1];

        std::vector<cv::Point2f> dst_pts(3);
        dst_pts[0] = cv::Point2f(0, 0);
        dst_pts[1] = cv::Point2f(target_width, 0);
        dst_pts[2] = cv::Point2f(0, target_height);

        cv::Mat tm = cv::getAffineTransform(src_pts, dst_pts);

        cv::warpAffine(rgb, dst, tm, cv::Size(target_width, target_height), cv::INTER_LINEAR, cv::BORDER_REPLICATE);
    }

    return dst;
}



/// @brief 读取二进制文件到内存缓冲区
/// @param filepath 二进制文件路径
/// @return 存有文件全部字节的 std::vector<uint8_t>
static std::vector<uint8_t> load_binary_file(const std::string& filepath) {
    // 以二进制模式打开文件，并定位到文件末尾以获取大小
    std::ifstream file(filepath, std::ios::binary | std::ios::ate);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + filepath);
    }

    // 获取文件大小
    std::streamsize size = file.tellg();
    if (size < 0) {
        throw std::runtime_error("Failed to get file size: " + filepath);
    }

    // 分配缓冲区
    std::vector<uint8_t> buffer(static_cast<size_t>(size));

    // 回到文件开头，读取全部数据
    file.seekg(0, std::ios::beg);
    if (!file.read(reinterpret_cast<char*>(buffer.data()), size)) {
        throw std::runtime_error("Error reading file: " + filepath);
    }

    return buffer;
}

const static float g_mean[3] = { 0.485, 0.456, 0.406 }; //顺序是RGB
const static float g_stds[3] = { 0.229, 0.224, 0.225 }; //顺序是RGB

// HWC -> CHW 并行处理，加了均值参数处理 Added by XiaoFan 2024-06-20
template <typename Stype, typename Dtype>
inline void hwc2chw_new2_omp(const size_t ch, const size_t w, const size_t h, const Stype* src, Dtype* dst, const double alpha,
                             const float* mean, const float* stds) {
    const size_t hw_stride = w * h;
    const size_t num_threads = omp_get_max_threads();
    const size_t chunk_size = hw_stride / num_threads;

#pragma omp parallel
    {
        const size_t thread_id = omp_get_thread_num();
        const size_t start_idx = thread_id * chunk_size;
        const size_t end_idx = (thread_id == num_threads - 1) ? hw_stride : (start_idx + chunk_size);

        size_t index = start_idx * ch;
        for (size_t s = start_idx; s < end_idx; ++s) {
            size_t stride_index = s;
            for (size_t c = 0UL; c < ch; ++c, stride_index += hw_stride) {
                //dst[stride_index] = static_cast<Dtype>(std::clamp<Dtype>((src[index++] * alpha - mean[c]) / stds[c], 0.0, 1.0));
                dst[stride_index] = static_cast<Dtype>((float(src[index++]) * alpha - mean[c]) / stds[c]); //输出的不是0到1之间
                //dst[stride_index] = static_cast<Dtype>((src[index++] * alpha - mean[c]) / stds[c]);
            }
        }
    }
}

// HWC -> CHW
template <typename Stype, typename Dtype>
inline void hwc2chw(const size_t ch, const size_t w, const size_t h, const Stype* src, Dtype* dst, const double alpha=1) {
    size_t index = 0UL;
    const size_t hw_stride = w * h;
    for (size_t s = 0UL; s < hw_stride; ++s) {
        size_t stride_index = s;
        for (size_t c = 0UL; c < ch; ++c, stride_index += hw_stride) {
            dst[stride_index] = static_cast<Dtype>(std::clamp<Dtype>(src[index++] * alpha, 0.0, 1.0));
        }
    }
}

// HWC -> CHW 并行处理 Added by Max 2024-04-26
template <typename Stype, typename Dtype>
inline void hwc2chw_new(const size_t ch, const size_t w, const size_t h, const Stype* src, Dtype* dst, const double alpha=1) {
    if(w <= 256 || h <= 256) {
        return hwc2chw(ch, w, h, src, dst, alpha);
    }
    const size_t hw_stride = w * h;
    const size_t num_threads = omp_get_max_threads();
    const size_t chunk_size = hw_stride / num_threads;

#pragma omp parallel
    {
        const size_t thread_id = omp_get_thread_num();
        const size_t start_idx = thread_id * chunk_size;
        const size_t end_idx = (thread_id == num_threads - 1) ? hw_stride : (start_idx + chunk_size);
        size_t index = start_idx * ch;
        for (size_t s = start_idx; s < end_idx; ++s) {
            size_t stride_index = s;
            for (size_t c = 0UL; c < ch; ++c, stride_index += hw_stride) {
                dst[stride_index] = static_cast<Dtype>(std::clamp<Dtype>(src[index++] * alpha, 0.0, 1.0));
            }
        }
    }
}

// CHW -> HWC
template <typename Stype, typename Dtype>
inline void chw2hwc(const size_t ch, const size_t w, const size_t h, const Stype* src, Dtype* dst, const double alpha=1) {
    size_t index = 0UL;
    const size_t hw_stride = w * h;
    for (size_t s = 0UL; s < hw_stride; ++s) {
        size_t stride_index = s;
        for (size_t c = 0UL; c < ch; ++c, stride_index += hw_stride) {
            dst[index++] = static_cast<Dtype>(std::clamp<short>(src[stride_index] * alpha, 0, 255));
        }
    }
}

// CHW -> HWC 并行处理版 Added by Max 2024-04-26
template <typename Stype, typename Dtype>
inline void chw2hwc_new(const size_t ch, const size_t w, const size_t h, const Stype* src, Dtype* dst, const double alpha=1) {
    if(w <= 256 || h <= 256) {
        return chw2hwc(ch, w, h, src, dst, alpha);
    }
    const size_t hw_stride = w * h;
    const size_t num_threads = omp_get_max_threads();
    const size_t chunk_size = hw_stride / num_threads;

#pragma omp parallel
    {
        const size_t thread_id = omp_get_thread_num();
        const size_t start_idx = thread_id * chunk_size;
        const size_t end_idx = (thread_id == num_threads - 1) ? hw_stride : (start_idx + chunk_size);
        size_t index = start_idx * ch;
        for (size_t s = start_idx; s < end_idx; ++s) {
            size_t stride_index = s;
            for (size_t c = 0UL; c < ch; ++c, stride_index += hw_stride) {
                dst[index++] = static_cast<Dtype>(std::clamp<short>(src[stride_index] * alpha, 0, 255));
            }
        }
    }
}

//----------------------------------------------------------------------
// 后处理：CTC 解码，将 raw_logits->[seq_len][num_classes] 转成 vector<Character>
//----------------------------------------------------------------------
static void ctc_decode(const float* raw_logits,
                       int seq_len, int num_classes,
                       std::vector<Character>& out_chars,
                       float& out_score) {
    out_chars.clear();
    int prev_idx = 0;
    float total_score = 0.f;
    int valid = 0;
    for (int t = 0; t < seq_len; t++) {
        const float* ptr = raw_logits + t * num_classes;
        // argmax
        int idx = std::max_element(ptr, ptr + num_classes) - ptr;
        float score = ptr[idx];
        // skip blank=0 and repeats
        if (idx > 0 && idx != prev_idx) {
            Character ch;
            ch.id   = idx - 1;  // Python 里 index-1
            ch.prob = score;
            out_chars.push_back(ch);
            total_score += score;
            valid++;
        }
        prev_idx = idx;
    }
    out_score = (valid>0 ? total_score/valid : 0.f);
}
}

PPOCRv5::PPOCRv5()
{
    ppocrv5_det = CreateImageAIInference();
    ppocrv5_det2 = CreateImageAIInference();
    ppocrv5_rec = CreateImageAIInference();
    target_size = 640;
}

PPOCRv5::~PPOCRv5()
{
    release();
}

bool PPOCRv5::load(const char* det_modelpath, const char* rec_modelpath, int gpu_index)
{
    ppocrv5_det->ReleaseModel();
    ppocrv5_rec->ReleaseModel();

    ppocrv5_det_data = load_binary_file(det_modelpath);
    ppocrv5_rec_data = load_binary_file(rec_modelpath);

    bool det_load_ret = ppocrv5_det->LoadModel(ppocrv5_det_data.data(), ppocrv5_det_data.size(), gpu_index);
    bool rec_load_ret = ppocrv5_rec->LoadModel(ppocrv5_rec_data.data(), ppocrv5_rec_data.size(), gpu_index);

    bool ok = det_load_ret && rec_load_ret;
    if (ok) autoDetectRecOutputDim();
    return ok;
}

bool PPOCRv5::load(const char* det_modelpath, const char* det2_modelpath, const char* rec_modelpath, int gpu_index, DetModelMode mode)
{
    m_detModelMode = mode;
    ppocrv5_det->ReleaseModel();
    if (ppocrv5_det2) ppocrv5_det2->ReleaseModel();
    ppocrv5_rec->ReleaseModel();

    ppocrv5_rec_data = load_binary_file(rec_modelpath);
    bool rec_load_ret = ppocrv5_rec->LoadModel(ppocrv5_rec_data.data(), ppocrv5_rec_data.size(), gpu_index);
    if (!rec_load_ret) return false;

    if (mode == DetModelMode::Heavyweight) {
        ppocrv5_det_data = load_binary_file(det2_modelpath);
        bool ok = ppocrv5_det->LoadModel(ppocrv5_det_data.data(), ppocrv5_det_data.size(), gpu_index);
        if (ok) autoDetectRecOutputDim();
        return ok;
    }

    if (mode == DetModelMode::DualModel) {
        ppocrv5_det_data = load_binary_file(det_modelpath);
        ppocrv5_det2_data = load_binary_file(det2_modelpath);
        bool det1_ret = ppocrv5_det->LoadModel(ppocrv5_det_data.data(), ppocrv5_det_data.size(), gpu_index);
        bool det2_ret = ppocrv5_det2->LoadModel(ppocrv5_det2_data.data(), ppocrv5_det2_data.size(), gpu_index);
        bool ok = det1_ret && det2_ret;
        if (ok) autoDetectRecOutputDim();
        return ok;
    }

    ppocrv5_det_data = load_binary_file(det_modelpath);
    bool ok = ppocrv5_det->LoadModel(ppocrv5_det_data.data(), ppocrv5_det_data.size(), gpu_index);
    if (ok) autoDetectRecOutputDim();
    return ok;
}

void PPOCRv5::setDetModelMode(DetModelMode mode)
{
    m_detModelMode = mode;
}

void PPOCRv5::set_target_size(int _target_size)
{
    target_size = _target_size;
}

bool PPOCRv5::autoDetectRecOutputDim()
{
    if (!ppocrv5_rec) return false;
    int64_t s0, s1, s2, s3, s4;
    int ret = ppocrv5_rec->GetOutputShape(0, &s0, &s1, &s2, &s3, &s4);
    if (ret < 0) return false;
    // Output shape is [B, seq_len, num_classes] -- s2 is the vocab dim
    if (s2 > 0) {
        m_recOutputDim = (int)s2;
        return true;
    }
    return false;
}

static int detectImpl(IImageAIInference* engine, const cv::Mat& rgb, std::vector<Object>& objects)
{
    int img_w = alignN(rgb.cols, 32);
    int img_h = alignN(rgb.rows, 32);
    int wpad = img_w - rgb.cols;
    int hpad = img_h - rgb.rows;

    float scale = 1.f;
    cv::Mat in;
    cv::cvtColor(rgb, in, cv::COLOR_RGB2BGR);

    cv::Mat in_pad;
    cv::copyMakeBorder(in, in_pad,
                       hpad / 2, hpad - hpad / 2,
                       wpad / 2, wpad - wpad / 2,
                       cv::BORDER_CONSTANT, cv::Scalar(114, 114, 114));

    std::vector<float> memory_vec_in_float; //输入的data
    memory_vec_in_float.resize(3 * in_pad.cols * in_pad.rows);
    hwc2chw_new2_omp<uint8_t, float>(3, in_pad.cols, in_pad.rows, (std::uint8_t*)in_pad.data, memory_vec_in_float.data(), 1.0/255.0, g_mean, g_stds);
    std::vector<float> memory_vec_out_float; //输出的data
    memory_vec_out_float.resize(1 * in_pad.cols * in_pad.rows);

    IImageAIInference::InferenceInputs ppocrv5_det_inputs;
    IImageAIInference::Data ppocrv5_det_input0;
    ppocrv5_det_input0.name = "x";
    ppocrv5_det_input0.data = memory_vec_in_float.data();
    ppocrv5_det_input0.dataSize = memory_vec_in_float.size() * sizeof(float);
    ppocrv5_det_input0.dims = {1, 3, in_pad.rows, in_pad.cols};
    ppocrv5_det_inputs.emplace_back(ppocrv5_det_input0);
    IImageAIInference::InferenceInputs ppocrv5_det_outputs;
    IImageAIInference::Data ppocrv5_det_output0;
    ppocrv5_det_output0.name = "fetch_name_0";
    ppocrv5_det_output0.data = memory_vec_out_float.data();
    ppocrv5_det_output0.dataSize = memory_vec_out_float.size() * sizeof(float);
    ppocrv5_det_output0.dims = {1, 1, in_pad.rows, in_pad.cols};
    ppocrv5_det_outputs.emplace_back(ppocrv5_det_output0);
    bool infer_ret = engine->DoInference(ppocrv5_det_inputs, ppocrv5_det_outputs);
    if(!infer_ret) {
        std::string err_str = engine->GetLastError();
        std::cout << "det error: " << err_str << std::endl;
    }
    cv::Mat out_255(cv::Size(in_pad.cols, in_pad.rows), CV_8UC1);
    chw2hwc_new<float, uint8_t>(1, in_pad.cols, in_pad.rows, (float*)memory_vec_out_float.data(), (uint8_t*)out_255.data, 255.0);

    // threshold binary
    cv::Mat bitmap;
    const float threshold = 0.3f;
    cv::threshold(out_255, bitmap, threshold * 255, 255, cv::THRESH_BINARY);

    // boxes from bitmap
    {
        // should use dbnet post process, but I think unclip process is difficult to write
        // so simply implement expansion. This may lose detection accuracy
        // original implementation can be referenced
        // https://github.com/MhLiao/DB/blob/master/structure/representers/seg_detector_representer.py

        const float box_thresh = 0.6f;
        const float enlarge_ratio = 1.95f;

        const float min_size = 3 * scale;
        const int max_candidates = 1000;

        std::vector<std::vector<cv::Point> > contours;
        std::vector<cv::Vec4i> hierarchy;

        cv::findContours(bitmap, contours, hierarchy, cv::RETR_LIST, cv::CHAIN_APPROX_SIMPLE);

        contours.resize(std::min(contours.size(), (size_t)max_candidates));

        for (size_t i = 0; i < contours.size(); i++)
        {
            const std::vector<cv::Point>& contour = contours[i];
            if (contour.size() <= 2)
                continue;

            double score = contour_score(out_255, contour);
            if (score < box_thresh)
                continue;

            cv::RotatedRect rrect = cv::minAreaRect(contour);

            float rrect_maxwh = std::max(rrect.size.width, rrect.size.height);
            if (rrect_maxwh < min_size)
                continue;

            int orientation = 0;
            if (rrect.angle >= -30 && rrect.angle <= 30 && rrect.size.height > rrect.size.width * 2.7)
            {
                // vertical text
                orientation = 1;
            }
            if ((rrect.angle <= -60 || rrect.angle >= 60) && rrect.size.width > rrect.size.height * 2.7)
            {
                // vertical text
                orientation = 1;
            }

            if (rrect.angle < -30)
            {
                // make orientation from -90 ~ -30 to 90 ~ 150
                rrect.angle += 180;
            }
            if (orientation == 0 && rrect.angle < 30)
            {
                // make it horizontal
                rrect.angle += 90;
                std::swap(rrect.size.width, rrect.size.height);
            }
            if (orientation == 1 && rrect.angle >= 60)
            {
                // make it vertical
                rrect.angle -= 90;
                std::swap(rrect.size.width, rrect.size.height);
            }

            // enlarge
            rrect.size.height += rrect.size.width * (enlarge_ratio - 1);
            rrect.size.width *= enlarge_ratio;

            // adjust offset to original unpadded
            rrect.center.x = (rrect.center.x - (wpad / 2)) / scale;
            rrect.center.y = (rrect.center.y - (hpad / 2)) / scale;
            rrect.size.width = (rrect.size.width) / scale;
            rrect.size.height = (rrect.size.height) / scale;

            Object obj;
            obj.rrect = rrect;
            obj.orientation = orientation;
            obj.prob = score;
            objects.push_back(obj);
        }
    }

    return 0;
}

int PPOCRv5::detect(const cv::Mat& rgb, std::vector<Object>& objects)
{
    objects.clear();

    if (m_detModelMode == DetModelMode::DualModel && ppocrv5_det2) {
        std::vector<Object> objects1, objects2;
        detectImpl(ppocrv5_det, rgb, objects1);
        detectImpl(ppocrv5_det2, rgb, objects2);

        const float iouThreshold = 0.7f;
        objects = std::move(objects1);
        for (size_t j = 0; j < objects2.size(); ++j) {
            bool overlaps = false;
            for (size_t i = 0; i < objects.size(); ++i) {
                std::vector<cv::Point2f> intersection;
                int ret = cv::rotatedRectangleIntersection(objects[i].rrect, objects2[j].rrect, intersection);
                if (ret == cv::INTERSECT_NONE) continue;
                float interArea = std::abs(cv::contourArea(intersection));
                float unionArea = objects[i].rrect.size.area() + objects2[j].rrect.size.area() - interArea;
                float iou = interArea / unionArea;
                if (iou > iouThreshold) {
                    overlaps = true;
                    if (objects2[j].prob > objects[i].prob)
                        objects[i] = objects2[j];
                    break;
                }
            }
            if (!overlaps) objects.push_back(objects2[j]);
        }
    } else {
        detectImpl(ppocrv5_det, rgb, objects);
    }

    return static_cast<int>(objects.size());
}

int PPOCRv5::recognize(const cv::Mat& rgb, Object& object)
{
    cv::Mat roi = get_rotate_crop_image(rgb, object);
#ifdef _DEBUG
    static int count = 0;
    cv::imwrite("E:/PPOCRv5/roi("+std::to_string(count++)+").png", roi);
#endif
    cv::Mat in;
    cv::cvtColor(roi, in, cv::COLOR_RGB2BGR);
    cv::resize(in, in, cv::Size(in.cols, 48));

    // ~/.paddlex/official_models/PP-OCRv5_mobile_rec/inference.yml
    const static float mean_vals[3] = {1.0, 1.0, 1.0};
    const static float norm_vals[3] = {1.0, 1.0, 1.0};
    std::vector<float> memory_vec_in_float; //输入的data
    memory_vec_in_float.resize(3 * in.rows * in.cols);
    hwc2chw_new<uint8_t, float>(3, in.cols, in.rows, (std::uint8_t*)in.data, memory_vec_in_float.data(), 1.0/255.0);

    IImageAIInference::InferenceInputs ppocrv5_rec_inputs;
    IImageAIInference::Data ppocrv5_rec_input0;
    ppocrv5_rec_input0.name = "x";
    ppocrv5_rec_input0.data = memory_vec_in_float.data();
    ppocrv5_rec_input0.dataSize = memory_vec_in_float.size() * sizeof(float);
    ppocrv5_rec_input0.dims = {1, 3, in.rows, in.cols};
    ppocrv5_rec_inputs.emplace_back(ppocrv5_rec_input0);
    IImageAIInference::InferenceInputs ppocrv5_rec_outputs;
    IImageAIInference::Data ppocrv5_rec_output0;
    ppocrv5_rec_output0.name = "fetch_name_0";
    ppocrv5_rec_output0.dims = {-1, -1, m_recOutputDim};
    ppocrv5_rec_outputs.emplace_back(ppocrv5_rec_output0);
    bool infer_ret = ppocrv5_rec->DoInference(ppocrv5_rec_inputs, ppocrv5_rec_outputs);
    if(!infer_ret) {
        std::string err_str = ppocrv5_rec->GetLastError();
        std::cout << "ppocrv5_rec error: " << err_str << std::endl;
    }

    // 取回推理结果的 dims 和指针
    auto& robj = ppocrv5_rec_outputs[0];
    int B = robj.dims[0];
    int seq_len     = robj.dims[1];
    int num_classes = robj.dims[2];
    float* raw_ptr  = reinterpret_cast<float*>(robj.data);

    // CTC 解码
    std::vector<Character> chars;
    float avg_score = 0.f;
    ctc_decode(raw_ptr, seq_len, num_classes, chars, avg_score);

    // 填充到 object
    object.text = std::move(chars);
    object.prob = avg_score;

    return 0;
}

void PPOCRv5::release()
{
    if(ppocrv5_det) {
        ppocrv5_det->ReleaseModel();
        ppocrv5_det = nullptr;
        std::cout << "ppocrv5_det->ReleaseModel();" << std::endl;
    }

    if(ppocrv5_det2) {
        ppocrv5_det2->ReleaseModel();
        ppocrv5_det2 = nullptr;
        std::cout << "ppocrv5_det2->ReleaseModel();" << std::endl;
    }

    if(ppocrv5_rec) {
        ppocrv5_rec->ReleaseModel();
        //ReleaseImageAIInference(ppocrv5_rec);
        ppocrv5_rec = nullptr;
        std::cout << "ppocrv5_rec->ReleaseModel();" << std::endl;
    }
}
