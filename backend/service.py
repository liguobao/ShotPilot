import os
import time
from datetime import datetime
import re
from io import BytesIO
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional, Tuple

import psutil
from PIL import ImageGrab
try:
    from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
    MOVIEPY_AVAILABLE = True
except ModuleNotFoundError:
    ImageSequenceClip = None
    MOVIEPY_AVAILABLE = False

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


MONITOR_SENTINEL_BASE = -1000
_monitor_lock = Lock()
_monitor_cache: Dict[int, Dict[str, Any]] = {}

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
    rows: List[Dict[str, Any]] = []
    rows.append(
        {
            "hwnd": FULL_SCREEN_HWND,
            "hwnd_hex": "全部屏幕",
            "pid": 0,
            "process": "Desktop",
            "title": "全部屏幕",
            "display": "全部屏幕 (Desktop)",
        }
    )
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
    return desktop if os.path.isdir(desktop) else fallback


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
        self._make_video: bool = False
        self._video_path: Optional[str] = None
        self._out_dir: Optional[str] = None
        self._interval: float = 0.5
        set_dpi_awareness()

    def start(
        self,
        hwnd: int,
        interval: float = 0.5,
        base_dir: Optional[str] = None,
        make_video: bool = False,
    ) -> Dict[str, str]:
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
            if make_video and not MOVIEPY_AVAILABLE:
                raise RuntimeError("当前环境未安装 moviepy，无法生成视频，请先安装或关闭该选项。")
            self._make_video = bool(make_video)
            self._video_path = None
            self._out_dir = out_dir
            self._interval = interval if interval > 0 else 0.5

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
                "make_video": self._make_video,
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
                        self._current["make_video"] = self._make_video
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
        video_path = None
        final_count = self._count
        final_last_file = self._last_file
        if self._make_video and final_count > 0 and self._out_dir:
            try:
                video_path = self._create_video(self._out_dir, self._interval)
            except Exception as exc:
                self._last_error = self._last_error or str(exc)
                video_path = None
        with self._lock:
            self._video_path = video_path
            self._make_video = False
            self._out_dir = None
            self._interval = 0.5
            self._count = 0
            self._last_file = None
            return {
                "stopped": True,
                "message": self._last_error,
                "count": final_count,
                "last_file": final_last_file,
                "video_path": self._video_path,
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
            "video_path": self._video_path,
            "make_video": self._make_video,
        }

    def _create_video(self, out_dir: str, interval: float) -> Optional[str]:
        if not MOVIEPY_AVAILABLE:
            raise RuntimeError("当前环境未安装 moviepy，无法生成视频")
        frames = sorted(
            [
                os.path.join(out_dir, name)
                for name in os.listdir(out_dir)
                if name.lower().endswith((".png", ".jpg", ".jpeg"))
            ]
        )
        if not frames:
            return None
        actual_fps = 1.0 / interval if interval > 0 else 1.0
        target_fps = 60
        if actual_fps > target_fps:
            step = max(1, int(round(actual_fps / target_fps)))
            frames = frames[::step] or frames
            fps = target_fps
        else:
            fps = max(1, int(round(actual_fps)))
        clip = ImageSequenceClip(frames, fps=fps)
        video_path = os.path.join(out_dir, "capture.mp4")
        try:
            clip.write_videofile(
                video_path,
                codec="libx264",
                audio=False,
                fps=fps,
                logger=None,
            )
        finally:
            clip.close()
        return video_path


screenshot_manager = ScreenshotManager()


__all__ = [
    "list_windows",
    "screenshot_manager",
    "capture_preview",
    "default_base_dir",
]
