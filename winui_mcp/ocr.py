"""PP-OCRv5/v6 ONNX inference pipeline.

The implementation follows the reference C++ PP-OCRv5 detector/recognizer:
image normalization, DB-style contour extraction, rotated crop, and CTC
decoding.  ONNX Runtime and OpenCV are imported lazily so normal UIA-only
workflows do not pay OCR startup cost.
"""
import os
from dataclasses import dataclass

from . import config


class OCRError(RuntimeError):
    """Raised for OCR model, inference, or image errors."""


@dataclass
class OCRLine:
    """A recognized text line with its screen-space geometry."""

    text: str
    confidence: float
    det_confidence: float
    box: list
    orientation: int = 0

    def as_dict(self):
        xs = [point[0] for point in self.box]
        ys = [point[1] for point in self.box]
        return {
            "text": self.text,
            "confidence": round(self.confidence, 6),
            "det_confidence": round(self.det_confidence, 6),
            "box": [[round(x, 2), round(y, 2)] for x, y in self.box],
            "bbox": {
                "left": round(min(xs), 2),
                "top": round(min(ys), 2),
                "right": round(max(xs), 2),
                "bottom": round(max(ys), 2),
            },
            "orientation": self.orientation,
        }


def _align(value, multiple=32):
    return (value + multiple - 1) // multiple * multiple


def _contour_score(binary, contour):
    x, y, width, height = cv2_bounding_rect(contour)
    if width <= 0 or height <= 0:
        return 0.0
    roi = binary[y:y + height, x:x + width]
    mask = _new_zeros(height, width)
    points = contour.reshape(-1, 2)
    shifted = points - (x, y)
    import cv2
    cv2.fillPoly(mask, [shifted], 255)
    return float(cv2.mean(roi, mask)[0]) / 255.0


def _new_zeros(height, width):
    import cv2
    return cv2.UMat(height, width, cv2.CV_8UC1).get()


def cv2_bounding_rect(contour):
    import cv2
    return cv2.boundingRect(contour)


def _line_sort_key(line):
    xs = [point[0] for point in line.box]
    ys = [point[1] for point in line.box]
    return (round(min(ys) / 12.0), min(xs))


class PPOCREngine:
    """Reusable PP-OCR detector plus recognizer."""

    def __init__(
        self,
        model_dir=None,
        providers=None,
        intra_op_threads=None,
        det_max_side=1600,
    ):
        self.model_dir = model_dir or config.find_ocr_model_dir()
        if not self.model_dir:
            raise OCRError(
                "Bundled PP-OCRv6 models were not found. Set WINUI_OCR_MODEL_DIR "
                "or reinstall winui-mcp-server."
            )
        self.providers = providers or self._providers_from_env()
        self.intra_op_threads = intra_op_threads
        self.det_max_side = max(0, int(det_max_side or 0))
        self._det_session = None
        self._rec_session = None
        self._det_input = None
        self._rec_input = None
        self._vocab = None

    @staticmethod
    def _providers_from_env():
        raw = os.environ.get("WINUI_OCR_PROVIDERS", "").strip()
        if raw:
            return [item.strip() for item in raw.split(",") if item.strip()]
        return ["CPUExecutionProvider"]

    def _session_options(self):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if self.intra_op_threads:
            options.intra_op_num_threads = int(self.intra_op_threads)
        return options

    def _load_session(self, relative_path):
        import onnxruntime as ort

        path = os.path.join(self.model_dir, relative_path)
        if not os.path.isfile(path):
            raise OCRError(f"OCR model not found: {path}")
        try:
            return ort.InferenceSession(
                path,
                sess_options=self._session_options(),
                providers=self.providers,
            )
        except Exception as exc:
            raise OCRError(f"Failed to load OCR model {path}: {exc}") from exc

    def load(self):
        """Load both ONNX sessions and the tiny recognition vocabulary."""
        if self._det_session is not None:
            return self
        self._det_session = self._load_session(os.path.join("det", "PP-OCRv6_tiny_det.onnx"))
        self._rec_session = self._load_session(os.path.join("rec", "PP-OCRv6_tiny_rec.onnx"))
        self._det_input = self._det_session.get_inputs()[0].name
        self._rec_input = self._rec_session.get_inputs()[0].name
        vocab_path = os.path.join(self.model_dir, "PP-OCRv6_vocab_tiny.txt")
        try:
            with open(vocab_path, "r", encoding="utf-8") as handle:
                self._vocab = handle.read().splitlines()
        except OSError as exc:
            raise OCRError(f"Failed to read OCR vocabulary {vocab_path}: {exc}") from exc
        return self

    def recognize(self, image, det_threshold=0.3, box_threshold=0.6,
                  unclip_ratio=1.95, min_text_confidence=0.45,
                  max_candidates=1000, max_lines=0):
        """Recognize text lines in a BGR OpenCV image."""
        import cv2

        if image is None or getattr(image, "size", 0) == 0:
            raise OCRError("OCR input image is empty")
        self.load()
        objects = self._detect(
            image,
            det_threshold=det_threshold,
            box_threshold=box_threshold,
            unclip_ratio=unclip_ratio,
            max_candidates=max_candidates,
            cv2=cv2,
        )
        lines = []
        for obj in objects:
            roi = self._rotate_crop(image, obj, cv2)
            if roi is None or getattr(roi, "size", 0) == 0:
                continue
            text, confidence = self._recognize_roi(roi, cv2)
            if not text:
                continue
            if confidence < min_text_confidence:
                continue
            lines.append(OCRLine(
                text=text,
                confidence=confidence,
                det_confidence=obj["det_confidence"],
                box=obj["box"],
                orientation=obj["orientation"],
            ))
        lines.sort(key=_line_sort_key)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
        return lines

    def recognize_text(self, image, **kwargs):
        """Return newline-joined text from ``recognize``."""
        return "\n".join(line.text for line in self.recognize(image, **kwargs))

    def _detect(self, image, det_threshold, box_threshold, unclip_ratio,
                max_candidates, cv2):
        original_height, original_width = image.shape[:2]
        scale = 1.0
        working = image
        if self.det_max_side and max(original_width, original_height) > self.det_max_side:
            scale = self.det_max_side / float(max(original_width, original_height))
            working = cv2.resize(
                image,
                (max(1, int(round(original_width * scale))), max(1, int(round(original_height * scale)))),
                interpolation=cv2.INTER_AREA,
            )

        height, width = working.shape[:2]
        aligned_width = _align(width, 32)
        aligned_height = _align(height, 32)
        pad_width = aligned_width - width
        pad_height = aligned_height - height
        padded = cv2.copyMakeBorder(
            working,
            pad_height // 2,
            pad_height - pad_height // 2,
            pad_width // 2,
            pad_width - pad_width // 2,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )

        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        blob = cv2.dnn.blobFromImage(
            rgb,
            scalefactor=1.0 / 255.0,
            size=(aligned_width, aligned_height),
            mean=(0.485 * 255.0, 0.456 * 255.0, 0.406 * 255.0),
            swapRB=False,
            crop=False,
        )
        blob[:, 0] /= 0.229
        blob[:, 1] /= 0.224
        blob[:, 2] /= 0.225
        try:
            output = self._det_session.run(None, {self._det_input: blob})[0]
        except Exception as exc:
            raise OCRError(f"PP-OCR detection inference failed: {exc}") from exc

        probability_map = output[0, 0]
        bitmap = cv2.threshold(
            probability_map, float(det_threshold), 255.0, cv2.THRESH_BINARY
        )[1].astype("uint8")
        contours, _ = cv2.findContours(
            bitmap, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = contours[:max_candidates]
        results = []
        for contour in contours:
            if len(contour) <= 2:
                continue
            score = _contour_score(bitmap, contour)
            if score < box_threshold:
                continue
            rect = cv2.minAreaRect(contour)
            (center_x, center_y), (rect_width, rect_height), angle = rect
            if max(rect_width, rect_height) < 3:
                continue

            orientation = 0
            if -30 <= angle <= 30 and rect_height > rect_width * 2.7:
                orientation = 1
            if (angle <= -60 or angle >= 60) and rect_width > rect_height * 2.7:
                orientation = 1
            if angle < -30:
                angle += 180
            if orientation == 0 and angle < 30:
                angle += 90
                rect_width, rect_height = rect_height, rect_width
            if orientation == 1 and angle >= 60:
                angle -= 90
                rect_width, rect_height = rect_height, rect_width

            rect_height += rect_width * (unclip_ratio - 1.0)
            rect_width *= unclip_ratio
            center_x = (center_x - pad_width / 2.0) / scale
            center_y = (center_y - pad_height / 2.0) / scale
            rect_width /= scale
            rect_height /= scale
            normalized = ((center_x, center_y), (rect_width, rect_height), angle)
            points = cv2.boxPoints(normalized)
            results.append({
                "rrect": normalized,
                "box": points.tolist(),
                "orientation": orientation,
                "det_confidence": float(score),
            })
        return results

    @staticmethod
    def _rotate_crop(image, obj, cv2):
        corners = cv2.boxPoints(obj["rrect"])
        orientation = obj["orientation"]
        rect_width, rect_height = obj["rrect"][1]
        if rect_width <= 0 or rect_height <= 0:
            return None
        target_width = max(1, int(round(rect_height * 48.0 / rect_width)))
        if orientation == 0:
            src = [corners[0], corners[1], corners[3]]
        else:
            src = [corners[2], corners[3], corners[1]]
        dst = [(0.0, 0.0), (float(target_width), 0.0), (0.0, 48.0)]
        try:
            # NumPy is used only as the OpenCV array bridge; image operations stay in cv2.
            import numpy as np

            matrix = cv2.getAffineTransform(
                np.float32(src), np.float32(dst)
            )
            return cv2.warpAffine(
                image, matrix, (target_width, 48),
                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
            )
        except Exception:
            return None

    def _recognize_roi(self, roi, cv2):
        if roi.shape[0] != 48:
            roi = cv2.resize(roi, (max(1, roi.shape[1]), 48))
        blob = cv2.dnn.blobFromImage(
            roi, scalefactor=1.0 / 255.0, size=(roi.shape[1], 48),
            mean=(0.0, 0.0, 0.0), swapRB=False, crop=False,
        )
        try:
            output = self._rec_session.run(None, {self._rec_input: blob})[0]
        except Exception as exc:
            raise OCRError(f"PP-OCR recognition inference failed: {exc}") from exc
        if output.ndim != 3 or output.shape[0] < 1:
            return "", 0.0
        return self._ctc_decode(output[0])

    def _ctc_decode(self, logits):
        if logits.shape[1] != len(self._vocab) + 2:
            # The model's last class is consistently unused for the bundled tiny vocab.
            pass
        previous = 0
        chars = []
        scores = []
        for row in logits:
            index = int(row.argmax())
            if index > 0 and index != previous:
                vocab_index = index - 1
                if 0 <= vocab_index < len(self._vocab):
                    chars.append(self._vocab[vocab_index])
                    scores.append(float(row[index]))
            previous = index
        confidence = sum(scores) / len(scores) if scores else 0.0
        return "".join(chars), confidence


_engine_cache = {}


def get_ocr_engine(model_dir=None):
    """Return a process-wide cached OCR engine for the selected model dir."""
    from . import config as config_module

    key = os.path.abspath(model_dir or config_module.find_ocr_model_dir() or "")
    engine = _engine_cache.get(key)
    if engine is None:
        engine = PPOCREngine(model_dir=model_dir)
        _engine_cache[key] = engine
    return engine


def clear_ocr_cache():
    """Release cached OCR sessions."""
    _engine_cache.clear()
