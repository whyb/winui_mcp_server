"""Windows window capture utilities backed by GDI and OpenCV.

The screenshot is written through a temporary BMP so OpenCV can decode it
without adding Pillow or direct NumPy array construction to the package.
"""
import ctypes
import ctypes.wintypes
import os
import tempfile
from dataclasses import dataclass


class CaptureError(RuntimeError):
    """Raised when a window image cannot be captured."""


@dataclass
class WindowCapture:
    """A captured window image and its screen-coordinate origin."""

    image: object
    left: int
    top: int
    width: int
    height: int


_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32


class _BitmapFileHeader(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("bfType", ctypes.wintypes.WORD),
        ("bfSize", ctypes.wintypes.DWORD),
        ("bfReserved1", ctypes.wintypes.WORD),
        ("bfReserved2", ctypes.wintypes.WORD),
        ("bfOffBits", ctypes.wintypes.DWORD),
    ]


class _BitmapInfoHeader(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("biSize", ctypes.wintypes.DWORD),
        ("biWidth", ctypes.wintypes.LONG),
        ("biHeight", ctypes.wintypes.LONG),
        ("biPlanes", ctypes.wintypes.WORD),
        ("biBitCount", ctypes.wintypes.WORD),
        ("biCompression", ctypes.wintypes.DWORD),
        ("biSizeImage", ctypes.wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.wintypes.LONG),
        ("biYPelsPerMeter", ctypes.wintypes.LONG),
        ("biClrUsed", ctypes.wintypes.DWORD),
        ("biClrImportant", ctypes.wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BitmapInfoHeader),
        ("bmiColors", ctypes.wintypes.DWORD * 3),
    ]


_user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
_user32.GetWindowRect.restype = ctypes.wintypes.BOOL
_user32.GetDC.argtypes = [ctypes.wintypes.HWND]
_user32.GetDC.restype = ctypes.wintypes.HDC
_user32.ReleaseDC.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int
_user32.PrintWindow.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HDC, ctypes.wintypes.UINT]
_user32.PrintWindow.restype = ctypes.wintypes.BOOL

_gdi32.CreateCompatibleDC.argtypes = [ctypes.wintypes.HDC]
_gdi32.CreateCompatibleDC.restype = ctypes.wintypes.HDC
_gdi32.CreateCompatibleBitmap.argtypes = [ctypes.wintypes.HDC, ctypes.c_int, ctypes.c_int]
_gdi32.CreateCompatibleBitmap.restype = ctypes.wintypes.HBITMAP
_gdi32.SelectObject.argtypes = [ctypes.wintypes.HDC, ctypes.wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = ctypes.wintypes.HGDIOBJ
_gdi32.BitBlt.argtypes = [
    ctypes.wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.wintypes.DWORD,
]
_gdi32.BitBlt.restype = ctypes.wintypes.BOOL
_gdi32.GetDIBits.argtypes = [
    ctypes.wintypes.HDC, ctypes.wintypes.HBITMAP, ctypes.wintypes.UINT,
    ctypes.wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(_BitmapInfo),
    ctypes.wintypes.UINT,
]
_gdi32.GetDIBits.restype = ctypes.c_int
_gdi32.DeleteObject.argtypes = [ctypes.wintypes.HGDIOBJ]
_gdi32.DeleteObject.restype = ctypes.wintypes.BOOL
_gdi32.DeleteDC.argtypes = [ctypes.wintypes.HDC]
_gdi32.DeleteDC.restype = ctypes.wintypes.BOOL


def _window_rect(hwnd):
    rect = ctypes.wintypes.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise CaptureError("GetWindowRect failed")
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise CaptureError("Window has no capturable area")
    return rect, width, height


def _capture_dib(hwnd, rect, width, height, use_print_window):
    source_hwnd = hwnd if use_print_window else 0
    source_dc = _user32.GetDC(source_hwnd)
    if not source_dc:
        return None
    mem_dc = None
    bitmap = None
    old_bitmap = None
    try:
        mem_dc = _gdi32.CreateCompatibleDC(source_dc)
        bitmap = _gdi32.CreateCompatibleBitmap(source_dc, width, height)
        if not mem_dc or not bitmap:
            return None
        old_bitmap = _gdi32.SelectObject(mem_dc, bitmap)

        if use_print_window:
            # PW_RENDERFULLCONTENT includes DirectComposition content on Windows 8.1+.
            if not _user32.PrintWindow(hwnd, mem_dc, 2):
                return None
        elif not _gdi32.BitBlt(
            mem_dc, 0, 0, width, height,
            source_dc, rect.left, rect.top, 0x00CC0020,
        ):
            return None

        info = _BitmapInfo()
        info.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # top-down DIB
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0  # BI_RGB
        info.bmiHeader.biSizeImage = width * height * 4
        bits = ctypes.create_string_buffer(info.bmiHeader.biSizeImage)
        rows = _gdi32.GetDIBits(
            mem_dc, bitmap, 0, height, bits, ctypes.byref(info), 0
        )
        if rows != height:
            return None
        return bits.raw
    finally:
        if old_bitmap:
            _gdi32.SelectObject(mem_dc, old_bitmap)
        if bitmap:
            _gdi32.DeleteObject(bitmap)
        if mem_dc:
            _gdi32.DeleteDC(mem_dc)
        if source_dc:
            _user32.ReleaseDC(source_hwnd, source_dc)


def _dib_to_bmp(raw, width, height, path):
    file_header = _BitmapFileHeader()
    file_header.bfType = 0x4D42  # BM
    file_header.bfOffBits = ctypes.sizeof(_BitmapFileHeader) + ctypes.sizeof(_BitmapInfoHeader)
    file_header.bfSize = file_header.bfOffBits + len(raw)

    info_header = _BitmapInfoHeader()
    info_header.biSize = ctypes.sizeof(_BitmapInfoHeader)
    info_header.biWidth = width
    info_header.biHeight = -height
    info_header.biPlanes = 1
    info_header.biBitCount = 32
    info_header.biCompression = 0
    info_header.biSizeImage = len(raw)

    with open(path, "wb") as handle:
        handle.write(bytes(file_header))
        handle.write(bytes(info_header))
        handle.write(raw)


def capture_window(hwnd):
    """Capture a top-level window and return a BGR OpenCV image."""
    if not hwnd:
        raise CaptureError("A valid window handle is required")
    try:
        import cv2
    except ImportError as exc:
        raise CaptureError(
            "OpenCV is required for OCR capture. Install the winui-mcp-server dependencies."
        ) from exc

    rect, width, height = _window_rect(hwnd)
    raw = _capture_dib(hwnd, rect, width, height, True)
    if raw is not None:
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as handle:
                temp_path = handle.name
            _dib_to_bmp(raw, width, height, temp_path)
            image = cv2.imread(temp_path, cv2.IMREAD_COLOR)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        if image is not None and sum(cv2.mean(image)[:3]) > 1.5:
            return WindowCapture(image, rect.left, rect.top, width, height)

    # Some applications reject PrintWindow; screen BitBlt is a best-effort fallback.
    raw = _capture_dib(hwnd, rect, width, height, False)
    if raw is None:
        raise CaptureError("PrintWindow and BitBlt both failed")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as handle:
            temp_path = handle.name
        _dib_to_bmp(raw, width, height, temp_path)
        image = cv2.imread(temp_path, cv2.IMREAD_COLOR)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    if image is None:
        raise CaptureError("OpenCV could not decode the captured window")
    return WindowCapture(image, rect.left, rect.top, width, height)
