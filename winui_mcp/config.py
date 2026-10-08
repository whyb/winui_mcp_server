"""Project configuration and external tool discovery."""
import glob
import os
import shutil

# Project root directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

_AI_EXE = "AccessibilityInsights.exe"


def _candidate_paths():
    candidates = []
    configured = os.environ.get("ACCESSIBILITY_INSIGHTS_PATH")
    if configured:
        candidates.append(configured)

    candidates.append(os.path.join(PROJECT_DIR, "AccessibilityInsights", "1.1", _AI_EXE))

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


ACCESSIBILITY_INSIGHTS_PATH = find_accessibility_insights()
