import os
import time
from datetime import datetime
import re
from io import BytesIO
from threading import Event, Lock, Thread
from typing import Dict, List, Optional, Tuple

import psutil
from PIL import ImageGrab

import ctypes
from ctypes import wintypes

# --- Windows API ---
user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
try:
    shcore = ctypes.windll.shcore
except Exception:
    shcore = None

SW_RESTORE = 9
SW_SHOW = 5
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

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

FULL_SCREEN_HWND = -1


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def set_dpi_awareness() -> None:
    """Avoid coordinate issues on high DPI displays."""
    try:
        if shcore:
            shcore.SetProcessDpiAwareness(2)  # Per Monitor v2
        else:
            user32.SetProcessDPIAware()
    except Exception:
        pass


def is_window_cloaked(hwnd: int) -> bool:
    """Skip UWP windows that are cloaked."""
    is_cloaked = wintypes.DWORD()
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(is_cloaked), ctypes.sizeof(is_cloaked)
    )
    if hr != 0:
        return False
    return bool(is_cloaked.value)


def get_window_title(hwnd: int) -> str:
    if hwnd == FULL_SCREEN_HWND:
        return "全屏桌面"
    length = GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip()


def hwnd_to_pid(hwnd: int) -> int:
    if hwnd == FULL_SCREEN_HWND:
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


def list_windows() -> List[Dict[str, str]]:
    rows = []
    rows.append(
        {
            "hwnd": FULL_SCREEN_HWND,
            "hwnd_hex": "全屏",
            "pid": 0,
            "process": "Desktop",
            "title": "全屏桌面",
            "display": "全屏桌面 (Desktop)",
        }
    )
    for hwnd in enum_windows():
        title = get_window_title(hwnd)
        pid = hwnd_to_pid(hwnd)
        try:
            pname = psutil.Process(pid).name()
        except Exception:
            pname = "N/A"
        rows.append(
            {
                "hwnd": hwnd,
                "hwnd_hex": hex(hwnd),
                "pid": pid,
                "process": pname,
                "title": title,
                "display": f"{title} ({pname})",
            }
        )
    rows.sort(
        key=lambda x: (
            x["hwnd"] != FULL_SCREEN_HWND,
            str(x["process"]).lower(),
            str(x["title"]).lower(),
        )
    )
    return rows


def bring_to_front(hwnd: int) -> None:
    if hwnd == FULL_SCREEN_HWND:
        return
    ShowWindow(hwnd, SW_RESTORE)
    ShowWindow(hwnd, SW_SHOW)
    SetForegroundWindow(hwnd)
    time.sleep(0.2)  # let the window refresh


def get_virtual_screen_rect() -> Tuple[int, int, int, int]:
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return left, top, left + width, top + height


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    if hwnd == FULL_SCREEN_HWND:
        return get_virtual_screen_rect()
    rect = RECT()
    if dwmapi and hasattr(dwmapi, "DwmGetWindowAttribute"):
        dwm_rect = RECT()
        if dwmapi.DwmGetWindowAttribute(
            hwnd,
            DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(dwm_rect),
            ctypes.sizeof(dwm_rect),
        ) == 0:
            return dwm_rect.left, dwm_rect.top, dwm_rect.right, dwm_rect.bottom

    if GetWindowRect(hwnd, ctypes.byref(rect)):
        return rect.left, rect.top, rect.right, rect.bottom
    return None


def _grab_window(hwnd: int):
    rect = get_window_rect(hwnd)
    if not rect:
        raise RuntimeError("无法获取窗口矩形区域")
    l, t, r, b = rect
    try:
        img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
    except TypeError:
        img = ImageGrab.grab(bbox=(l, t, r, b))
    return img, (l, t, r, b)


def screenshot_window(hwnd: int, save_path: str) -> None:
    img, _ = _grab_window(hwnd)
    img.save(save_path, "PNG")


def capture_preview(hwnd: int) -> Tuple[bytes, Tuple[int, int, int, int]]:
    img, rect = _grab_window(hwnd)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue(), rect


def sanitize_directory_name(name: str) -> str:
    safe = re.sub(r"[^\w\-\.\s]", "_", name).strip()
    return safe or "window"


def default_base_dir() -> str:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    fallback = os.path.abspath("pictures")
    target = os.path.join(desktop, "screenshot")
    return target if os.path.isdir(desktop) else fallback


class ScreenshotManager:
    """Manages a background screenshot loop for a selected window."""

    def __init__(self) -> None:
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._lock = Lock()
        self._current: Optional[Dict[str, str]] = None
        self._last_error: Optional[str] = None
        self._count: int = 0
        self._last_file: Optional[str] = None
        set_dpi_awareness()

    def start(self, hwnd: int, interval: float = 0.5, base_dir: Optional[str] = None) -> Dict[str, str]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                raise RuntimeError("已有截屏任务在运行，请先停止")

            window_title = get_window_title(hwnd)
            if not window_title:
                raise RuntimeError("目标窗口不可用或没有标题")

            bring_to_front(hwnd)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = sanitize_directory_name(window_title)
            root_dir = os.path.abspath(base_dir or default_base_dir())
            os.makedirs(root_dir, exist_ok=True)
            out_dir = os.path.join(root_dir, f"{safe_title}_{timestamp}")
            os.makedirs(out_dir, exist_ok=True)

            self._stop_event.clear()
            self._last_error = None
            self._count = 0
            self._last_file = None

            self._thread = Thread(
                target=self._loop,
                args=(hwnd, interval, out_dir),
                name="ScreenshotWorker",
                daemon=True,
            )
            self._thread.start()

            self._current = {
                "hwnd": hwnd,
                "title": window_title,
                "interval": interval,
                "output_dir": out_dir,
                "base_dir": root_dir,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "count": self._count,
                "last_file": self._last_file,
            }
            return dict(self._current)

    def _loop(self, hwnd: int, interval: float, out_dir: str) -> None:
        idx = 0
        try:
            while not self._stop_event.is_set():
                save_path = os.path.join(out_dir, f"{idx}.png")
                screenshot_window(hwnd, save_path)
                idx += 1
                with self._lock:
                    self._count = idx
                    self._last_file = save_path
                    if self._current is not None:
                        self._current["count"] = idx
                        self._current["last_file"] = save_path
                # Wait on the event so we can stop promptly
                if self._stop_event.wait(max(0.01, interval)):
                    break
        except Exception as exc:
            self._last_error = str(exc)
        finally:
            with self._lock:
                self._thread = None
                self._current = None

    def stop(self) -> Dict[str, Optional[str]]:
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return {"stopped": False, "message": "没有运行中的任务"}
            self._stop_event.set()
            thread = self._thread
        thread.join(timeout=5)
        with self._lock:
            return {
                "stopped": True,
                "message": self._last_error,
                "count": self._count,
                "last_file": self._last_file,
            }

    def status(self) -> Dict[str, Optional[str]]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            current = dict(self._current) if self._current else None
        return {
            "running": running,
            "current": current,
            "last_error": self._last_error,
            "count": self._count,
            "last_file": self._last_file,
        }


screenshot_manager = ScreenshotManager()


__all__ = [
    "list_windows",
    "screenshot_manager",
    "capture_preview",
    "default_base_dir",
]
