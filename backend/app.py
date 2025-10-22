
import base64
import os
import sys
from typing import Any, Dict, Optional

import webview
from loguru import logger

from service import capture_preview, default_base_dir, list_windows, screenshot_manager

logger.add("./logs/{time}.log", rotation="10 MB")


class Api:
    """Expose screenshot workflows to the frontend via pywebview."""

    def list_apps(self) -> Dict[str, Any]:
        try:
            return {"success": True, "data": list_windows()}
        except Exception as exc:
            logger.exception("Failed to list windows")
            return {"success": False, "message": str(exc)}

    def start_capture(
        self,
        hwnd,
        interval=0.5,
        base_dir: Optional[str] = None,
        make_video: bool = False,
    ) -> Dict[str, Any]:
        try:
            hwnd_int = self._parse_hwnd(hwnd)
            info = screenshot_manager.start(
                hwnd_int,
                float(interval),
                base_dir=base_dir,
                make_video=bool(make_video),
            )
            return {"success": True, "data": info}
        except Exception as exc:
            logger.exception("Failed to start capture")
            return {"success": False, "message": str(exc)}

    def stop_capture(self) -> Dict[str, Any]:
        try:
            result = screenshot_manager.stop()
            return {
                "success": result.get("stopped", False),
                "data": result,
            }
        except Exception as exc:
            logger.exception("Failed to stop capture")
            return {"success": False, "message": str(exc)}

    def get_status(self) -> Dict[str, Any]:
        try:
            return {"success": True, "data": screenshot_manager.status()}
        except Exception as exc:
            logger.exception("Failed to fetch status")
            return {"success": False, "message": str(exc)}

    def choose_directory(self, initial: Optional[str] = None) -> Dict[str, Any]:
        try:
            window = webview.windows[0] if webview.windows else None
            if not window:
                return {"success": False, "message": "未找到应用窗口"}
            result = window.create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=initial or default_base_dir(),
            )
            if not result:
                return {"success": False, "message": "未选择目录"}
            # pywebview returns tuple/list
            path = result[0] if isinstance(result, (list, tuple)) else result
            return {"success": True, "data": path}
        except Exception as exc:
            logger.exception("Failed to choose directory")
            return {"success": False, "message": str(exc)}

    def get_default_directory(self) -> Dict[str, Any]:
        try:
            return {"success": True, "data": default_base_dir()}
        except Exception as exc:
            logger.exception("Failed to fetch default directory")
            return {"success": False, "message": str(exc)}

    def open_path(self, path: str) -> Dict[str, Any]:
        try:
            if not path:
                return {"success": False, "message": "路径为空"}
            if not os.path.exists(path):
                return {"success": False, "message": "路径不存在"}
            os.startfile(path)
            return {"success": True}
        except Exception as exc:
            logger.exception("Failed to open path")
            return {"success": False, "message": str(exc)}

    def preview_capture(self, hwnd) -> Dict[str, Any]:
        try:
            hwnd_int = self._parse_hwnd(hwnd)
            data, rect = capture_preview(hwnd_int)
            encoded = base64.b64encode(data).decode("ascii")
            l, t, r, b = rect
            meta = {
                "rect": {
                    "left": l,
                    "top": t,
                    "right": r,
                    "bottom": b,
                    "width": max(0, r - l),
                    "height": max(0, b - t),
                }
            }
            return {
                "success": True,
                "data": {
                    "image": f"data:image/png;base64,{encoded}",
                    "meta": meta,
                },
            }
        except Exception as exc:
            logger.exception("Failed to capture preview")
            return {"success": False, "message": str(exc)}

    @staticmethod
    def _parse_hwnd(hwnd) -> int:
        if isinstance(hwnd, str) and hwnd.startswith(("0x", "0X")):
            return int(hwnd, 16)
        return int(hwnd)


def get_html_path() -> str:
    if getattr(sys, "frozen", False):
        # 打包后，index.html 在 sys._MEIPASS/frontend/dist/index.html
        html_path = os.path.join(sys._MEIPASS, "frontend", "dist", "index.html")
    else:
        html_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "frontend", "dist", "index.html")
        )
    # logger.info(f"HTML file path: {html_path}")
    return html_path


if __name__ == "__main__":
    api = Api()
    html_path = get_html_path()
    file_url = "file://" + html_path.replace("\\", "/")
    window = webview.create_window(
        "自动截图器",
        url=file_url,
        js_api=api,
        width=960,
        height=900,
        resizable=True,
        min_size=(920, 720),
    )

    webview.start()
