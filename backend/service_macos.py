"""macOS-specific helpers for screenshot service."""
import time
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageGrab

try:
    import Quartz
except Exception:
    Quartz = None

try:
    import AppKit
except Exception:
    AppKit = None

FULL_SCREEN_HWND = -1
MONITOR_SENTINEL_BASE = -1000

_monitor_lock = Lock()
_mac_monitor_cache: Dict[int, Dict[str, Any]] = {}
_mac_window_cache: Dict[int, Dict[str, Any]] = {}
_mac_window_lock = Lock()
_mac_global_top: Optional[int] = None
_screen_permission_granted: Optional[bool] = None
_screen_permission_prompted = False


def _ensure_screen_capture_permission() -> None:
    """Ensure the app has screen recording permission before capturing."""
    global _screen_permission_granted, _screen_permission_prompted
    if not Quartz:
        return
    preflight = getattr(Quartz, "CGPreflightShotPilotAccess", None)
    if not preflight:
        return
    if _screen_permission_granted:
        return
    try:
        granted = bool(preflight())
    except Exception:
        granted = True
    if granted:
        _screen_permission_granted = True
        return
    request_access = getattr(Quartz, "CGRequestShotPilotAccess", None)
    if request_access and not _screen_permission_prompted:
        try:
            request_access()
        except Exception:
            pass
        _screen_permission_prompted = True
        time.sleep(0.1)
        try:
            granted = bool(preflight())
        except Exception:
            granted = False
        if granted:
            _screen_permission_granted = True
            return
    _screen_permission_granted = False
    raise PermissionError(
        "检测到缺少屏幕录制权限，请在“系统设置 > 隐私与安全 > 屏幕录制”中为应用授予权限，并重新启动应用后再试。"
    )


def _cgimage_to_image(image) -> Optional[Image.Image]:
    if not Quartz or not image:
        return None
    width = Quartz.CGImageGetWidth(image)
    height = Quartz.CGImageGetHeight(image)
    if width <= 0 or height <= 0:
        return None
    data_provider = Quartz.CGImageGetDataProvider(image)
    data = Quartz.CGDataProviderCopyData(data_provider)
    buf = bytes(data)
    try:
        return Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", 0, 1)
    except Exception:
        return None


def _mac_refresh_monitors() -> List[Dict[str, Any]]:
    monitors: List[Dict[str, Any]] = []
    global _mac_global_top
    if not Quartz:
        with _monitor_lock:
            _mac_monitor_cache.clear()
            _mac_global_top = None
        return monitors
    max_displays = 16
    result = Quartz.CGGetActiveDisplayList(max_displays, None, None)
    if isinstance(result, tuple) and len(result) == 3:
        err, active_displays, display_count = result
    else:
        err = int(result)
        active_displays = ()
        display_count = 0
    if err != Quartz.kCGErrorSuccess:
        with _monitor_lock:
            _mac_monitor_cache.clear()
            _mac_global_top = None
        return monitors
    display_count = int(display_count or 0)
    active_display_ids = list(active_displays)[:display_count]
    temp_entries: List[Dict[str, Any]] = []
    max_top = None
    for idx, display_id in enumerate(active_display_ids):
        bounds = Quartz.CGDisplayBounds(display_id)
        left = int(bounds.origin.x)
        bottom = int(bounds.origin.y)
        width = int(bounds.size.width)
        height = int(bounds.size.height)
        top = bottom + height
        temp_entries.append(
            {
                "index": idx + 1,
                "display_id": int(display_id),
                "left": left,
                "bottom": bottom,
                "width": width,
                "height": height,
                "top": top,
                "primary": bool(Quartz.CGDisplayIsMain(display_id)),
            }
        )
        if max_top is None or top > max_top:
            max_top = top
    if max_top is None:
        with _monitor_lock:
            _mac_monitor_cache.clear()
            _mac_global_top = None
        return monitors
    monitors = []
    for entry in temp_entries:
        sentinel = MONITOR_SENTINEL_BASE - entry["index"]
        rect_left = int(entry["left"])
        rect_right = int(entry["left"] + entry["width"])
        rect_top = int(max_top - entry["top"])
        rect_bottom = int(max_top - entry["bottom"])
        title = f"显示器 {entry['index']}"
        if entry["primary"]:
            title += "（主显示器）"
        monitors.append(
            {
                "hwnd": sentinel,
                "index": entry["index"],
                "title": title,
                "rect": (rect_left, rect_top, rect_right, rect_bottom),
                "native_rect": (
                    entry["left"],
                    entry["bottom"],
                    entry["left"] + entry["width"],
                    entry["top"],
                ),
                "device": str(entry["display_id"]),
                "primary": entry["primary"],
                "display_id": entry["display_id"],
                "width": entry["width"],
                "height": entry["height"],
            }
        )
    with _monitor_lock:
        _mac_monitor_cache.clear()
        for item in monitors:
            _mac_monitor_cache[item["hwnd"]] = item
        _mac_global_top = int(max_top)
    return monitors


def _get_monitor_entry(hwnd: int) -> Optional[Dict[str, Any]]:
    with _monitor_lock:
        entry = _mac_monitor_cache.get(hwnd)
    if entry:
        return entry
    _mac_refresh_monitors()
    with _monitor_lock:
        return _mac_monitor_cache.get(hwnd)


def _mac_top_anchor() -> Optional[int]:
    global _mac_global_top
    if _mac_global_top is not None:
        return _mac_global_top
    _mac_refresh_monitors()
    if _mac_global_top is not None:
        return _mac_global_top
    if Quartz:
        try:
            bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
            return int(bounds.origin.y + bounds.size.height)
        except Exception:
            return None
    return None


def _mac_convert_bounds(bounds: Dict[str, Any]) -> Optional[Tuple[int, int, int, int]]:
    top_anchor = _mac_top_anchor()
    if top_anchor is None:
        return None
    x = int(round(bounds.get("X", 0)))
    y = int(round(bounds.get("Y", 0)))
    width = int(round(bounds.get("Width", 0)))
    height = int(round(bounds.get("Height", 0)))
    if width <= 0 or height <= 0:
        return None
    top = int(top_anchor - (y + height))
    bottom = int(top_anchor - y)
    return (x, top, x + width, bottom)


def _mac_refresh_windows() -> List[Dict[str, Any]]:
    windows: List[Dict[str, Any]] = []
    if not Quartz:
        with _mac_window_lock:
            _mac_window_cache.clear()
        return windows
    options = (
        Quartz.kCGWindowListOptionOnScreenOnly
        | Quartz.kCGWindowListExcludeDesktopElements
    )
    info_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
    with _mac_window_lock:
        _mac_window_cache.clear()
        for raw in info_list:
            window_id = int(raw.get("kCGWindowNumber", 0) or 0)
            if not window_id:
                continue
            bounds = raw.get("kCGWindowBounds") or {}
            rect = _mac_convert_bounds(bounds)
            if not rect:
                continue
            owner = raw.get("kCGWindowOwnerName") or "应用"
            title = raw.get("kCGWindowName") or ""
            if not title:
                title = owner
            pid = int(raw.get("kCGWindowOwnerPID", 0) or 0)
            display_text = title or owner or f"Window {window_id}"
            entry = {
                "hwnd": window_id,
                "hwnd_hex": hex(window_id),
                "pid": pid,
                "process": owner,
                "title": title,
                "display": f"{display_text} ({owner})" if owner else display_text,
                "rect": rect,
            }
            _mac_window_cache[window_id] = entry
            windows.append(entry)
    return windows


def capture_image(hwnd: int) -> Optional[Image.Image]:
    if not Quartz:
        return None
    _ensure_screen_capture_permission()
    if hwnd == FULL_SCREEN_HWND:
        return None
    monitor = _get_monitor_entry(hwnd)
    if monitor and monitor.get("display_id") is not None:
        try:
            cg_image = Quartz.CGDisplayCreateImage(monitor["display_id"])
        except Exception:
            cg_image = None
        image = _cgimage_to_image(cg_image)
        if image:
            return image.convert("RGB")
    try:
        cg_image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            hwnd,
            Quartz.kCGWindowImageDefault
            | getattr(Quartz, "kCGWindowImageBoundsIgnoreFraming", 0),
        )
    except Exception:
        cg_image = None
    image = _cgimage_to_image(cg_image)
    if image:
        return image.convert("RGB")
    return None


def set_dpi_awareness() -> None:
    return


def get_window_title(hwnd: int) -> str:
    if hwnd == FULL_SCREEN_HWND:
        return "全部屏幕"
    monitor = _get_monitor_entry(hwnd)
    if monitor:
        return monitor["title"]
    with _mac_window_lock:
        entry = _mac_window_cache.get(hwnd)
    if entry:
        return entry.get("title") or ""
    for entry in _mac_refresh_windows():
        if entry["hwnd"] == hwnd:
            return entry.get("title") or ""
    return ""


def hwnd_to_pid(hwnd: int) -> int:
    if hwnd == FULL_SCREEN_HWND or _get_monitor_entry(hwnd):
        return 0
    with _mac_window_lock:
        entry = _mac_window_cache.get(hwnd)
    if entry:
        return int(entry.get("pid") or 0)
    for entry in _mac_refresh_windows():
        if entry["hwnd"] == hwnd:
            return int(entry.get("pid") or 0)
    return 0


def enum_windows() -> List[int]:
    return [entry["hwnd"] for entry in _mac_refresh_windows()]


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
    monitors = _mac_refresh_monitors()
    for monitor in monitors:
        rect = monitor["rect"]
        width = max(0, rect[2] - rect[0])
        height = max(0, rect[3] - rect[1])
        device_label = monitor.get("device") or f"DISPLAY{monitor['index']}"
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
                    "device": monitor.get("device"),
                    "primary": monitor.get("primary"),
                    "left": rect[0],
                    "top": rect[1],
                    "right": rect[2],
                    "bottom": rect[3],
                    "width": width,
                    "height": height,
                },
            }
        )
    window_entries = _mac_refresh_windows()
    window_entries.sort(
        key=lambda x: (str(x["process"]).lower(), str(x["title"]).lower())
    )
    rows.extend(window_entries)
    return rows


def bring_to_front(hwnd: int) -> None:
    if hwnd == FULL_SCREEN_HWND or _get_monitor_entry(hwnd):
        return
    pid = hwnd_to_pid(hwnd)
    if not pid or not AppKit:
        return
    try:
        app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app:
            app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
            time.sleep(0.2)
    except Exception:
        return


def get_virtual_screen_rect() -> Tuple[int, int, int, int]:
    monitors = _mac_refresh_monitors()
    if not monitors:
        img = ImageGrab.grab(all_screens=True)
        width, height = img.size
        return (0, 0, width, height)
    left = min(m["rect"][0] for m in monitors)
    top = min(m["rect"][1] for m in monitors)
    right = max(m["rect"][2] for m in monitors)
    bottom = max(m["rect"][3] for m in monitors)
    return (left, top, right, bottom)


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    if hwnd == FULL_SCREEN_HWND:
        return get_virtual_screen_rect()
    monitor = _get_monitor_entry(hwnd)
    if monitor:
        return tuple(monitor["rect"])
    with _mac_window_lock:
        entry = _mac_window_cache.get(hwnd)
    if entry:
        return tuple(entry["rect"])
    for entry in _mac_refresh_windows():
        if entry["hwnd"] == hwnd:
            return tuple(entry["rect"])
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
