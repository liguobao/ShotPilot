"""Windows-specific helpers for screenshot service."""
import ctypes
import time
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import psutil

from ctypes import wintypes

FULL_SCREEN_HWND = -1
MONITOR_SENTINEL_BASE = -1000

user32 = ctypes.windll.user32

try:
    dwmapi = ctypes.windll.dwmapi
except Exception:
    dwmapi = None
try:
    shcore = ctypes.windll.shcore
except Exception:
    shcore = None

SW_RESTORE = 9
SW_SHOW = 5
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
)

GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
GetWindowRect = user32.GetWindowRect
SetForegroundWindow = user32.SetForegroundWindow
ShowWindow = user32.ShowWindow
GetWindowThreadProcessId = user32.GetWindowThreadProcessId

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

MonitorEnumProc = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    wintypes.HMONITOR,
    wintypes.HDC,
    ctypes.POINTER(RECT),
    wintypes.LPARAM,
)

MONITORINFOF_PRIMARY = 0x00000001

class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", ctypes.c_wchar * 32),
    ]

if hasattr(user32, "EnumDisplayMonitors") and hasattr(user32, "GetMonitorInfoW"):
    EnumDisplayMonitors = user32.EnumDisplayMonitors
    EnumDisplayMonitors.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(RECT),
        MonitorEnumProc,
        wintypes.LPARAM,
    ]
    EnumDisplayMonitors.restype = ctypes.c_bool

    GetMonitorInfoW = user32.GetMonitorInfoW
    GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]
    GetMonitorInfoW.restype = ctypes.c_bool
else:
    EnumDisplayMonitors = None
    GetMonitorInfoW = None

_monitor_lock = Lock()
_monitor_cache: Dict[int, Dict[str, Any]] = {}


def _refresh_monitors() -> List[Dict[str, Any]]:
    monitors: List[Dict[str, Any]] = []
    if not EnumDisplayMonitors or not GetMonitorInfoW:
        with _monitor_lock:
            _monitor_cache.clear()
        return monitors

    def _enum_cb(hmonitor, _hdc, _lprc, _lparam) -> int:
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return 1
        index = len(monitors) + 1
        sentinel = MONITOR_SENTINEL_BASE - index
        rect = (
            info.rcMonitor.left,
            info.rcMonitor.top,
            info.rcMonitor.right,
            info.rcMonitor.bottom,
        )
        label = f"显示器 {index}"
        if info.dwFlags & MONITORINFOF_PRIMARY:
            label += "（主显示器）"
        device = info.szDevice.rstrip("\x00")
        monitors.append(
            {
                "hwnd": sentinel,
                "index": index,
                "title": label,
                "rect": rect,
                "device": device,
                "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
            }
        )
        return 1

    callback = MonitorEnumProc(_enum_cb)
    EnumDisplayMonitors(None, None, callback, 0)

    with _monitor_lock:
        _monitor_cache.clear()
        for item in monitors:
            _monitor_cache[item["hwnd"]] = item
    return monitors


def _get_monitor_entry(hwnd: int) -> Optional[Dict[str, Any]]:
    with _monitor_lock:
        entry = _monitor_cache.get(hwnd)
    if entry:
        return entry
    _refresh_monitors()
    with _monitor_lock:
        return _monitor_cache.get(hwnd)


def set_dpi_awareness() -> None:
    try:
        if shcore:
            shcore.SetProcessDpiAwareness(2)
        else:
            user32.SetProcessDPIAware()
    except Exception:
        pass


def is_window_cloaked(hwnd: int) -> bool:
    if not dwmapi:
        return False
    is_cloaked = wintypes.DWORD()
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(is_cloaked), ctypes.sizeof(is_cloaked)
    )
    if hr != 0:
        return False
    return bool(is_cloaked.value)


def get_window_title(hwnd: int) -> str:
    if hwnd == FULL_SCREEN_HWND:
        return "全部屏幕"
    monitor = _get_monitor_entry(hwnd)
    if monitor:
        return monitor["title"]
    length = GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip()


def hwnd_to_pid(hwnd: int) -> int:
    if hwnd == FULL_SCREEN_HWND or _get_monitor_entry(hwnd):
        return 0
    pid = wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def enum_windows() -> List[int]:
    hwnds: List[int] = []

    def cb(hwnd, _):
        if IsWindowVisible(hwnd) and not is_window_cloaked(hwnd):
            if get_window_title(hwnd):
                hwnds.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return hwnds


def list_windows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = [
        {
            "hwnd": FULL_SCREEN_HWND,
            "hwnd_hex": "全部屏幕",
            "pid": 0,
            "process": "Desktop",
            "title": "全部屏幕",
            "display": "全部屏幕 (Desktop)",
        }
    ]
    for monitor in _refresh_monitors():
        rect = monitor["rect"]
        width = max(0, rect[2] - rect[0])
        height = max(0, rect[3] - rect[1])
        device = monitor.get("device") or ""
        device_label = device or f"DISPLAY{monitor['index']}"
        rows.append(
            {
                "hwnd": monitor["hwnd"],
                "hwnd_hex": device_label,
                "pid": 0,
                "process": "显示器",
                "title": monitor["title"],
                "display": (
                    f"{monitor['title']}（{device_label}）"
                    if device_label
                    else monitor["title"]
                ),
                "monitor": {
                    "index": monitor["index"],
                    "device": device,
                    "primary": monitor["primary"],
                    "left": rect[0],
                    "top": rect[1],
                    "right": rect[2],
                    "bottom": rect[3],
                    "width": width,
                    "height": height,
                },
            }
        )
    window_entries: List[Dict[str, Any]] = []
    for hwnd in enum_windows():
        title = get_window_title(hwnd)
        pid = hwnd_to_pid(hwnd)
        try:
            pname = psutil.Process(pid).name()
        except Exception:
            pname = "N/A"
        window_entries.append(
            {
                "hwnd": hwnd,
                "hwnd_hex": hex(hwnd),
                "pid": pid,
                "process": pname,
                "title": title,
                "display": f"{title} ({pname})",
            }
        )
    window_entries.sort(
        key=lambda x: (str(x["process"]).lower(), str(x["title"]).lower())
    )
    rows.extend(window_entries)
    return rows


def bring_to_front(hwnd: int) -> None:
    if hwnd == FULL_SCREEN_HWND or _get_monitor_entry(hwnd):
        return
    ShowWindow(hwnd, SW_RESTORE)
    ShowWindow(hwnd, SW_SHOW)
    SetForegroundWindow(hwnd)
    time.sleep(0.2)


def get_virtual_screen_rect() -> Tuple[int, int, int, int]:
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return left, top, left + width, top + height


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    if hwnd == FULL_SCREEN_HWND:
        return get_virtual_screen_rect()
    monitor = _get_monitor_entry(hwnd)
    if monitor:
        return monitor["rect"]
    rect = RECT()
    if dwmapi and hasattr(dwmapi, "DwmGetWindowAttribute"):
        dwm_rect = RECT()
        if dwmapi.DwmGetWindowAttribute(
            hwnd,
            DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(dwm_rect),
            ctypes.sizeof(dwm_rect),
        ) == 0:
            return (
                dwm_rect.left,
                dwm_rect.top,
                dwm_rect.right,
                dwm_rect.bottom,
            )
    if GetWindowRect(hwnd, ctypes.byref(rect)):
        return rect.left, rect.top, rect.right, rect.bottom
    return None


def capture_image(hwnd: int):
    return None


__all__ = [
    "FULL_SCREEN_HWND",
    "MONITOR_SENTINEL_BASE",
    "set_dpi_awareness",
    "get_window_title",
    "hwnd_to_pid",
    "enum_windows",
    "list_windows",
    "bring_to_front",
    "get_virtual_screen_rect",
    "get_window_rect",
    "capture_image",
]
