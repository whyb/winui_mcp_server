import unittest

from winui_mcp import config
from winui_mcp.ocr import PPOCREngine


class OcrEngineTests(unittest.TestCase):
    def test_bundled_tiny_models_are_present(self):
        self.assertIsNotNone(config.OCR_MODEL_DIR)
        self.assertTrue(config.OCR_MODEL_DIR.endswith("PP-OCRv6"))

    def test_synthetic_text_is_recognized(self):
        import cv2

        image = cv2.UMat(600, 900, cv2.CV_8UC3).get()
        image[:] = 255
        cv2.putText(
            image, "Save", (250, 320), cv2.FONT_HERSHEY_SIMPLEX,
            3.0, (0, 0, 0), 6, cv2.LINE_AA,
        )

        lines = PPOCREngine().recognize(image, min_text_confidence=0.5)

        self.assertTrue(lines)
        self.assertEqual(lines[0].text, "Save")
        self.assertGreater(lines[0].confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
