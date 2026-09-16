"""Windows foreground-window detection without extra dependencies."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


@dataclass(frozen=True)
class ForegroundWindow:
    process_name: str
    title: str
    process_id: int


def current_window() -> ForegroundWindow:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ForegroundWindow("", "", 0)

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

    title_length = user32.GetWindowTextLengthW(hwnd)
    title_buffer = ctypes.create_unicode_buffer(title_length + 1)
    user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))

    process_name = ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    if handle:
        try:
            path_buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(path_buffer))
            if kernel32.QueryFullProcessImageNameW(
                handle, 0, path_buffer, ctypes.byref(size)
            ):
                process_name = Path(path_buffer.value).name.lower()
        finally:
            kernel32.CloseHandle(handle)

    return ForegroundWindow(process_name, title_buffer.value, process_id.value)
