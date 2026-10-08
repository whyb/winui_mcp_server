/**
 * @file ppocrv5.h
 * @brief PP-OCRv5 光学字符识别引擎
 *
 * @details
 * ## Module Overview
 *
 * PPOCRv5 是本项目的核心 OCR 推理引擎，封装了基于 ONNX Runtime 的 PP-OCRv5 文字检测与
 * 识别流水线。该模块利用 PaddlePaddle PP-OCR 系列模型，通过 ImageAI 动态加载机制调用
 * ONNX 后端（DirectML / CPU），提供端到端的图像文字提取能力。
 *
 * ### 设计意图
 * - 将 PP-OCRv5 的 检测(Detection) 与 识别(Recognition) 两个阶段统一封装为一个可复用的类。
 * - 分离模型加载与推理，支持按需加载/释放 GPU 资源。
 * - 通过 `Object` / `Character` 结构体提供结构化的 OCR 结果，便于上层直接消费。
 *
 * ### 核心职责
 * 1. **模型管理**: 加载/卸载 检测模型 (det) 和 识别模型 (rec) 的 ONNX 权重文件。
 * 2. **文字检测**: 输入 RGB 图像，输出一组旋转矩形区域 (RotatedRect) 及其置信度。
 * 3. **文字识别**: 对每个检测到的区域进行单行文字识别，输出字符序列及逐字置信度。
 *
 * ### 与其他模块的耦合
 * - `IImageAIInference`: 底层 ONNX 推理引擎接口（裸指针，由 load() 时动态库创建）。
 * - `ImageAIModuleLoader`: 工厂函数，用于创建 IImageAIInference 实例。
 * - `ppocrv5_dict.h`: 中文字符字典，用于将识别输出的类别索引映射到 UTF-8 字符串。
 * - `MainWindow` / `PdfOcrWorker`: 主要调用者，持有 std::shared_ptr<PPOCRv5>。
 *
 * ### 底层实现思路
 * - **检测流程**: RGB→预处理(归一化/缩放)→det推理→后处理(DB二值化→轮廓提取→
 *   minAreaRect→NMS过滤)→输出 Object 列表。
 * - **识别流程**: 对每个 Object 区域做仿射变换矫正→缩放到固定高度→归一化→rec推理→
 *   CTC解码→查字典→填充 Object::text。
 * - **内存策略**: 模型权重数据以 vector<uint8_t> 常驻内存；推理临时缓冲区在 DoInference
 *   中动态分配。
 * - **加速策略**: 预处理/后处理阶段大量使用 OpenCV 矩阵操作；部分像素级归一化通过
 *   OpenMP 并行加速。
 *
 * @note 所有 cv::Mat 输入要求为 RGB 三通道格式 (CV_8UC3)。
 * @warning 本类不可拷贝/移动，由 shared_ptr 管理生命周期。
 */

#pragma once

#include <opencv2/core/core.hpp>
#include <IImageAIInference.h>
#include "appsettings.h"

/**
 * @struct Character
 * @brief 单个识别字符及其置信度
 *
 * 文字识别结果中的最小单元。每个字符对应字典中的一个 UTF-8 条目。
 */
struct Character
{
    int id;     ///< 字符在字典 ppocrv5_dict 中的索引 (0-based)
    float prob; ///< 该字符的识别置信度，范围 [0.0, 1.0]
};

/**
 * @struct Object
 * @brief 一个被检测到的文字区域（块）
 *
 * 检测阶段的输出单元。每个 Object 代表图像中一块文字区域的位置、角度、
 * 检测置信度以及后续识别出的文本内容。
 */
struct Object
{
    cv::RotatedRect rrect;          ///< 旋转矩形，描述文字区域的包围盒（中心、尺寸、角度）
    int orientation;                ///< 文字方向标识。0=正立文字，1=180°倒置文字（需要 flip）
    float prob;                     ///< 检测置信度，范围 [0.0, 1.0]
    std::vector<Character> text;    ///< 识别结果：按阅读顺序排列的字符序列
};

/**
 * @class PPOCRv5
 * @brief PP-OCRv5 检测+识别流水线引擎
 *
 * 该类封装了完整的文字检测和识别流程。典型用法：
 * 1. 构造实例
 * 2. 调用 load() 加载 ONNX 模型
 * 3. 调用 detect() 获取图像中所有文字区域
 * 4. 对每个区域调用 recognize() 识别其中的文字
 * 5. 调用 release() 释放 GPU 资源
 *
 * @note 该类内部持有 IImageAIInference 裸指针（由动态库分配），
 *       析构时自动调用 release()。
 */
class PPOCRv5
{
public:
    /**
     * @brief 默认构造函数
     *
     * 初始化成员变量为零值/空指针。模型尚未加载，需调用 load() 后才能使用推理功能。
     */
    PPOCRv5();

    /**
     * @brief 析构函数
     *
     * 自动调用 release() 释放推理引擎资源。
     */
    ~PPOCRv5();

    /**
     * @brief 加载检测和识别模型
     *
     * 从磁盘读取 ONNX 模型文件，通过 ImageAIModuleLoader 创建底层推理引擎实例。
     * 检测和识别模型分别加载为独立的 IImageAIInference 实例。
     *
     * @param det_modelpath [in] 检测模型文件路径（.onnx），不可为空。
     * @param rec_modelpath [in] 识别模型文件路径（.onnx），不可为空。
     * @param gpu_index [in] GPU 设备索引。 -1 表示 CPU 推理，>=0 表示 DirectML GPU 索引。
     * @return true 加载成功
     * @return false 加载失败（文件不存在、格式错误、引擎初始化失败等）
     *
     * @pre det_modelpath 和 rec_modelpath 指向有效的 .onnx 文件。
     * @note 重复调用 load() 前需先调用 release()。
     * @warning gpu_index 超出可用设备范围时行为由底层 ImageAI 实现定义。
     */
    bool load(const char* det_modelpath, const char* rec_modelpath, int gpu_index);

    void setDetModelMode(DetModelMode mode);

    bool load(const char* det_modelpath, const char* det2_modelpath, const char* rec_modelpath, int gpu_index, DetModelMode mode);

    /**
     * @brief 设置检测阶段的目标图像尺寸
     *
     * 控制检测模型预处理时的图像缩放目标。较大的 target_size 可提高小文字检出率
     * 但会增加计算量。
     *
     * @param target_size [in] 目标尺寸（长边像素数）。默认值在构造函数中设置。
     *
     * @note 必须在 detect() 调用前设置。
     */
    void set_target_size(int target_size);

    /**
     * @brief 自动检测 rec 模型输出维度
     *
     * 使用 GetOutputShape() 查询已加载 rec 模型的输出张量形状，
     * 提取分类维度。必须在 load() 之后调用。
     * @return 成功返回 true，失败返回 false（此时保持默认值 18385）
     */
    bool autoDetectRecOutputDim();

    /**
     * @brief 执行文字检测
     *
     * 对输入 RGB 图像运行检测模型，提取所有可能的文字区域。
     * 内部流程：图像预处理 → det模型推理 → DB后处理 → 轮廓提取 → 最小外接矩形 → 过滤。
     *
     * @param rgb [in] 输入图像，CV_8UC3 格式 (BGR通道顺序由调用者保证兼容)。
     * @param objects [out] 输出检测结果。函数会清空并重新填充该容器。
     *                      每个 Object 包含旋转矩形位置和检测置信度。
     *                      调用 detect() 后 objects 中的 text 字段尚未填充，
     *                      需后续调用 recognize() 逐块识别。
     * @return int 检测到的文字区域数量 (objects.size())
     *
     * @pre load() 已成功调用。
     * @note objects 参数会被清空（调用 clear()）。
     */
    int detect(const cv::Mat& rgb, std::vector<Object>& objects);

    /**
     * @brief 识别单个文字区域
     *
     * 对 detect() 返回的单个 Object 执行文字识别，将结果填入 object.text。
     * 内部流程：仿射变换矫正 → 缩放 → 归一化 → rec模型推理 → CTC解码 → 字典映射。
     *
     * @param rgb [in] 原始输入图像（与 detect() 传入的同一张图），CV_8UC3 格式。
     * @param object [in,out] 待识别的文字区域。识别结果写入 object.text，
     *                        每个 Character 包含字符索引(id)和置信度(prob)。
     *                        object.text 会被清空后重新填充。
     * @return int 识别的字符数量 (object.text.size())
     *
     * @pre load() 已成功调用。
     * @pre object.rrect 已由 detect() 填充有效值。
     * @note 若识别失败（如区域过小或文本模糊），返回 0，object.text 为空。
     */
    int recognize(const cv::Mat& rgb, Object& object);

    /**
     * @brief 释放推理引擎资源
     *
     * 释放检测和识别两个 IImageAIInference 实例（调用 ReleaseModel），
     * 重置指针为 nullptr，释放模型权重数据内存。
     *
     * @note 析构函数自动调用此方法，通常无需手动调用。
     * @note 释放后可重新调用 load() 加载新模型。
     */
    void release();

protected:
    /// @cond INTERNAL

    IImageAIInference * ppocrv5_det;        ///< 主检测模型推理引擎
    IImageAIInference * ppocrv5_det2;       ///< 副检测模型推理引擎（DualModel 模式使用）（裸指针，动态库管理）
    IImageAIInference * ppocrv5_rec;        ///< 识别模型推理引擎（裸指针，动态库管理）
    std::vector<uint8_t> ppocrv5_det_data;  ///< 主检测模型 ONNX 权重数据
    std::vector<uint8_t> ppocrv5_det2_data; ///< 副检测模型 ONNX 权重数据（内存缓存）
    std::vector<uint8_t> ppocrv5_rec_data;  ///< 识别模型 ONNX 权重数据（内存缓存）
    int target_size;                        ///< 检测目标尺寸
    int m_recOutputDim = 18385;             ///< Rec 模型输出维度（自动检测或默认）
    DetModelMode m_detModelMode = DetModelMode::Lightweight;  ///< 检测模型运行模式，控制预处理缩放

    /// @endcond
};