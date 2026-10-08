# PP-OCRv6 Tiny Models

These files are bundled so `ocr_scan` works offline after installing
`winui-mcp-server`.

## Files

| File | SHA-256 |
|------|---------|
| `det/PP-OCRv6_tiny_det.onnx` | `193BAB7A04FCA699A6C82E6ABB5B81BDB28177F0ABD4062552B04908DAFB19F8` |
| `rec/PP-OCRv6_tiny_rec.onnx` | `9EF676D6ED3C88256A2D92C640C44F25B0C40947E111B14B8BE8F594091563E6` |
| `PP-OCRv6_vocab_tiny.txt` | `34D139222B6E8D84830F57476E39F01E76BE3BAFFDE3E9DF75A079E251140598` |

## Runtime

- Detection and recognition use ONNX Runtime.
- Image preprocessing, DB-style post-processing, rotated crops, and CTC decoding use OpenCV.
- The Python implementation follows the PP-OCRv5 C++ reference pre/post-processing because PP-OCRv5 and PP-OCRv6 share the same inference contract.
- Set `WINUI_OCR_MODEL_DIR` to override the bundled model directory.
- Set `WINUI_OCR_PROVIDERS` to a comma-separated ONNX Runtime provider list when a compatible execution provider is installed. The default is `CPUExecutionProvider`.

## License

PP-OCR models are distributed by the PaddlePaddle/PaddleOCR project under
the Apache License 2.0. See the upstream PaddleOCR project for model
provenance and license details.
