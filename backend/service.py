import hashlib
import importlib
import importlib.util
import os
import re
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageGrab

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# --- Platform-specific helpers ---

_platform_module = None


def _import_platform(module_name: str):
    """Import helper that works in package, script, and frozen contexts."""
    candidates = []
    if __package__:
        candidates.append(f"{__package__}.{module_name}")
    candidates.append(module_name)
    for name in candidates:
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    # For frozen bundles (PyInstaller) try loading from the executable directory.
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    module_path = base_path / f"{module_name}.py"
    if module_path.exists():
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


if IS_WINDOWS:
    import service_windows as _platform_module
elif IS_MAC:
    import service_macos as _platform_module  # type: ignore

if _platform_module:
    FULL_SCREEN_HWND = _platform_module.FULL_SCREEN_HWND
    MONITOR_SENTINEL_BASE = _platform_module.MONITOR_SENTINEL_BASE
    set_dpi_awareness = _platform_module.set_dpi_awareness
    get_window_title = _platform_module.get_window_title
    hwnd_to_pid = _platform_module.hwnd_to_pid
    enum_windows = _platform_module.enum_windows
    list_windows = _platform_module.list_windows
    bring_to_front = _platform_module.bring_to_front
    get_virtual_screen_rect = _platform_module.get_virtual_screen_rect
    get_window_rect = _platform_module.get_window_rect
    _platform_capture_image = getattr(_platform_module, "capture_image", None)
else:
    FULL_SCREEN_HWND = -1
    MONITOR_SENTINEL_BASE = -1000

    def set_dpi_awareness() -> None:
        return

    def get_window_title(hwnd: int) -> str:
        return "全部屏幕" if hwnd == FULL_SCREEN_HWND else ""

    def hwnd_to_pid(hwnd: int) -> int:
        return 0

    def enum_windows() -> List[int]:
        return []

    def list_windows() -> List[Dict[str, Any]]:
        return [
            {
                "hwnd": FULL_SCREEN_HWND,
                "hwnd_hex": "全部屏幕",
                "pid": 0,
                "process": "Desktop",
                "title": "全部屏幕",
                "display": "全部屏幕 (Desktop)",
            }
        ]

    def bring_to_front(hwnd: int) -> None:
        return

    def get_virtual_screen_rect() -> Tuple[int, int, int, int]:
        img = ImageGrab.grab()
        return (0, 0, img.width, img.height)

    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        if hwnd == FULL_SCREEN_HWND:
            return get_virtual_screen_rect()
        return None

    def _capture_image_fallback(hwnd: int):
        return None

    _platform_capture_image = _capture_image_fallback

def _grab_window(hwnd: int):
    rect = get_window_rect(hwnd)
    if not rect:
        raise RuntimeError("无法获取窗口矩形区域")
    l, t, r, b = rect
    img: Optional[Any] = None
    if _platform_capture_image:
        img = _platform_capture_image(hwnd)
    if img is None:
        try:
            img = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
        except TypeError:
            img = ImageGrab.grab(bbox=(l, t, r, b))
    return img, (l, t, r, b)


def screenshot_window(hwnd: int, save_path: str) -> None:
    img, _ = _grab_window(hwnd)
    img.save(save_path, "PNG")


def capture_single(hwnd: int, base_dir: Optional[str] = None) -> str:
    """Capture a single frame and persist it to the target directory."""
    img, _ = _grab_window(hwnd)
    target_dir = base_dir or default_base_dir()
    os.makedirs(target_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = f"screenshot-{timestamp}"
    candidate = os.path.join(target_dir, f"{base_name}.png")
    suffix = 1
    while os.path.exists(candidate):
        candidate = os.path.join(target_dir, f"{base_name}-{suffix}.png")
        suffix += 1

    img.save(candidate, "PNG")
    return candidate


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
        self._make_longshot: bool = False
        self._longshot_path: Optional[str] = None
        self._out_dir: Optional[str] = None
        self._interval: float = 0.5
        set_dpi_awareness()

    def start(
        self,
        hwnd: int,
        interval: float = 0.5,
        base_dir: Optional[str] = None,
        make_longshot: bool = False,
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
            self._make_longshot = bool(make_longshot)
            self._longshot_path = None
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
                "make_longshot": self._make_longshot,
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
                        self._current["make_longshot"] = self._make_longshot
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
        longshot_path = None
        final_count = self._count
        final_last_file = self._last_file
        if self._make_longshot and final_count > 0 and self._out_dir:
            try:
                longshot_path = self._create_longshot(self._out_dir)
            except Exception as exc:
                self._last_error = self._last_error or str(exc)
                longshot_path = None
        with self._lock:
            self._longshot_path = longshot_path
            self._make_longshot = False
            self._out_dir = None
            self._interval = 0.5
            self._count = 0
            self._last_file = None
            return {
                "stopped": True,
                "message": self._last_error,
                "count": final_count,
                "last_file": final_last_file,
                "longshot_path": self._longshot_path,
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
            "longshot_path": self._longshot_path,
            "make_longshot": self._make_longshot,
        }

    def _create_longshot(self, out_dir: str) -> Optional[str]:
        def frame_key(path: str):
            stem = Path(path).stem
            if stem.isdigit():
                return (0, int(stem))
            return (1, stem)

        frame_paths = sorted(
            [
                os.path.join(out_dir, name)
                for name in os.listdir(out_dir)
                if name.lower().endswith((".png", ".jpg", ".jpeg"))
            ],
            key=frame_key,
        )
        if not frame_paths:
            return None
        subtitle_ratio = 0.22
        spacer_height = 8
        subtitle_blocks: List[Image.Image] = []
        seen_hashes: set[str] = set()

        first_frame_path = frame_paths[0]
        with Image.open(first_frame_path) as base_src:
            base_image = base_src.convert("RGBA")

        base_width = base_image.width
        base_height = base_image.height

        for path in frame_paths:
            with Image.open(path) as img:
                converted = img.convert("RGBA")
                crop_height = max(1, int(round(converted.height * subtitle_ratio)))
                crop_box = (
                    0,
                    max(0, converted.height - crop_height),
                    converted.width,
                    converted.height,
                )
                subtitle_region = converted.crop(crop_box).convert("RGBA")
                if subtitle_region.width != base_width:
                    subtitle_region = subtitle_region.resize(
                        (base_width, subtitle_region.height), Image.BILINEAR
                    )
                digest = hashlib.sha1(subtitle_region.tobytes()).hexdigest()
                if digest in seen_hashes:
                    subtitle_region.close()
                    converted.close()
                    continue
                seen_hashes.add(digest)
                subtitle_blocks.append(subtitle_region)
                converted.close()

        total_subtitle_height = sum(block.height for block in subtitle_blocks)
        if subtitle_blocks:
            total_subtitle_height += spacer_height * len(subtitle_blocks)

        canvas_height = base_height + total_subtitle_height
        longshot = Image.new("RGBA", (base_width, canvas_height), (0, 0, 0, 0))
        longshot.paste(base_image, (0, 0))
        offset = base_height
        for block in subtitle_blocks:
            if spacer_height:
                offset += spacer_height
            longshot.paste(block, (0, offset))
            offset += block.height
            block.close()
        base_image.close()
        longshot_path = os.path.join(out_dir, "longshot.png")
        longshot.save(longshot_path, "PNG")
        longshot.close()
        return longshot_path


screenshot_manager = ScreenshotManager()


__all__ = [
    "list_windows",
    "screenshot_manager",
    "capture_preview",
    "capture_single",
    "default_base_dir",
]
