import unittest

from winui_mcp.ocr_pipeline import bind_ocr_lines, shift_ocr_lines


class OcrPipelineTests(unittest.TestCase):
    def test_line_binds_to_smallest_control(self):
        tree = {
            "ref": "0",
            "visible": True,
            "rect": {"left": 0, "top": 0, "right": 1000, "bottom": 800},
            "name": "",
            "children": [
                {
                    "ref": "0.0",
                    "visible": True,
                    "rect": {"left": 0, "top": 0, "right": 500, "bottom": 500},
                    "name": "",
                    "children": [
                        {
                            "ref": "0.0.0",
                            "visible": True,
                            "rect": {"left": 10, "top": 10, "right": 120, "bottom": 50},
                            "name": "Accessible save",
                            "children": [],
                        }
                    ],
                }
            ],
        }
        lines = [{
            "text": "Save",
            "confidence": 0.9,
            "det_confidence": 0.8,
            "box": [[20, 20], [80, 20], [80, 40], [20, 40]],
            "bbox": {"left": 20, "top": 20, "right": 80, "bottom": 40},
            "orientation": 0,
        }]

        stats, unbound = bind_ocr_lines(tree, lines, (0, 0))

        self.assertEqual(stats.bound, 1)
        self.assertEqual(stats.unbound, 0)
        self.assertEqual(unbound, [])
        leaf = tree["children"][0]["children"][0]
        self.assertEqual(leaf["ocr_text"], "Save")
        self.assertEqual(leaf["effective_text"], "Accessible save")
        self.assertEqual(leaf["text_source"], "uia+ocr")
        self.assertIsNone(tree["ocr_text"] or None)

    def test_shift_lines_uses_capture_origin(self):
        line = {
            "text": "Run",
            "confidence": 0.9,
            "det_confidence": 0.8,
            "box": [[1, 2], [3, 2], [3, 4], [1, 4]],
            "bbox": {"left": 1, "top": 2, "right": 3, "bottom": 4},
        }

        shifted = shift_ocr_lines([line], (10, 20))[0]

        self.assertEqual(shifted["bbox"]["left"], 11)
        self.assertEqual(shifted["bbox"]["top"], 22)
        self.assertEqual(shifted["box"][0], [11, 22])


if __name__ == "__main__":
    unittest.main()
