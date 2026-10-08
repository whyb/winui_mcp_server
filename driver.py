"""Compatibility wrapper for :mod:`winui_mcp.driver`."""
from winui_mcp import driver as _impl
from winui_mcp.driver import *  # noqa: F401,F403
from winui_mcp.driver import (
    _driver_cache,
    _escape_sendkeys_text,
    _get_process_name,
    _kernel32,
    _psapi,
    _user32,
)

auto = _impl.auto
ctypes = _impl.ctypes
time = _impl.time
