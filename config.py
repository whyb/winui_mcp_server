"""
config.py - Project configuration constants.
"""
import os

# Project root directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Accessibility Insights for Windows (relative to project root)
ACCESSIBILITY_INSIGHTS_PATH = os.path.join(
    PROJECT_DIR, "AccessibilityInsights", "1.1", "AccessibilityInsights.exe"
)
