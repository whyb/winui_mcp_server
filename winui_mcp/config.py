"""Project configuration and bundled resource discovery."""
import glob
import os
import shutil

# Package directory (kept as PROJECT_DIR for backward compatibility).
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

_AI_EXE = "AccessibilityInsights.exe"
_OCR_MODEL_DIR = os.path.join(PROJECT_DIR, "models", "PP-OCRv6")
_OCR_REQUIRED_FILES = (
    os.path.join("det", "PP-OCRv6_tiny_det.onnx"),
    os.path.join("rec", "PP-OCRv6_tiny_rec.onnx"),
    "PP-OCRv6_vocab_tiny.txt",
)


def _candidate_paths():
    candidates = []
    configured = os.environ.get("ACCESSIBILITY_INSIGHTS_PATH")
    if configured:
        candidates.append(configured)

    candidates.append(os.path.join(PROJECT_DIR, "AccessibilityInsights", "1.1", _AI_EXE))
    candidates.append(os.path.join(
        os.path.dirname(PROJECT_DIR), "AccessibilityInsights", "1.1", _AI_EXE
    ))

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        patterns = [
            os.path.join(local_app_data, "Microsoft", "AccessibilityInsightsForWindows", "**", _AI_EXE),
            os.path.join(local_app_data, "AccessibilityInsights", "**", _AI_EXE),
            os.path.join(local_app_data, "Programs", "Accessibility Insights for Windows", "**", _AI_EXE),
        ]
        for pattern in patterns:
            candidates.extend(glob.glob(pattern, recursive=True))

    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(env_name, "")
        if root:
            candidates.append(os.path.join(root, "Microsoft Accessibility Insights", _AI_EXE))
            candidates.append(os.path.join(root, "Accessibility Insights for Windows", _AI_EXE))

    which = shutil.which("AccessibilityInsights")
    if which:
        candidates.append(which)
    return candidates


def find_accessibility_insights():
    """Return the first existing Accessibility Insights executable path."""
    for candidate in _candidate_paths():
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _ocr_model_candidates():
    """Return candidate PP-OCR model directories, priority first."""
    candidates = []
    configured = os.environ.get("WINUI_OCR_MODEL_DIR")
    if configured:
        candidates.append(configured)
    candidates.append(_OCR_MODEL_DIR)
    # Source-checkout fallback for alternate packaging layouts.
    candidates.append(os.path.join(os.path.dirname(PROJECT_DIR), "models", "PP-OCRv6"))
    return candidates


def find_ocr_model_dir():
    """Return a complete bundled PP-OCRv6 model directory, or None."""
    for candidate in _ocr_model_candidates():
        if not candidate:
            continue
        root = os.path.abspath(candidate)
        if all(os.path.isfile(os.path.join(root, relative)) for relative in _OCR_REQUIRED_FILES):
            return root
    return None


ACCESSIBILITY_INSIGHTS_PATH = find_accessibility_insights()
OCR_MODEL_DIR = find_ocr_model_dir()
