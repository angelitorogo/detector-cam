from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

def _getenv_bool(name: str, default: bool) -> bool:
    v = os.getenv(name, str(default)).strip().lower()
    return v in ("1", "true", "yes", "y", "on")

def _parse_hex_color(s: str, default=(255, 165, 0)) -> tuple[int, int, int]:
    """
    Convierte '#rrggbb' o 'rrggbb' a BGR (OpenCV).
    Naranja por defecto si falla.
    """
    s = (s or "").strip().lstrip("#")
    if len(s) != 6:
        return (0, 165, 255)  # BGR naranja
    try:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        return (b, g, r)  # BGR para OpenCV
    except Exception:
        return (0, 165, 255)

@dataclass(frozen=True)
class Settings:
    # fuente
    SNAPSHOT_HOME: str
    SNAPSHOT_URL_INIT: str
    SNAPSHOT_REFERER: str
    SNAPSHOT_COOKIE: str

    # discovery
    USE_SELENIUM: bool
    SELENIUM_BROWSER: str

    # ventana
    SHOW_WINDOW: bool
    WINDOW_TITLE: str

    # telegram
    TG_BOT_TOKEN: str
    TG_CHAT_ID: str

    # motion
    ENABLE_MOTION: bool
    THRESH: int
    MIN_AREA: int
    PROC_WIDTH: int
    DILATE_ITERS: int
    MERGE_PADDING: int
    BOX_COLOR_BGR: tuple[int, int, int]
    BOX_THICKNESS: int

    # alertas TG movimiento
    SEND_TG_ON_MOTION: bool
    MOTION_ALERT_COOLDOWN_SEC: int
    PREVIEW_MAX_WIDTH: int
    PHOTO_JPEG_QUALITY: int

def load_settings() -> Settings:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    SNAPSHOT_HOME = os.getenv("SNAPSHOT_HOME", "").strip()
    SNAPSHOT_URL_INIT = os.getenv("SNAPSHOT_URL", "").strip()
    SNAPSHOT_REFERER = os.getenv("SNAPSHOT_REFERER", SNAPSHOT_HOME).strip()
    SNAPSHOT_COOKIE = os.getenv("SNAPSHOT_COOKIE", "").strip()

    USE_SELENIUM = _getenv_bool("USE_SELENIUM_DISCOVERY", True)
    SELENIUM_BROWSER = os.getenv("SELENIUM_BROWSER", "chrome").strip()

    SHOW_WINDOW = _getenv_bool("SHOW_WINDOW", True)
    WINDOW_TITLE = os.getenv("WINDOW_TITLE", "Webcam (solo vista)").strip()

    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
    TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()

    ENABLE_MOTION = _getenv_bool("ENABLE_MOTION", True)
    THRESH = int(os.getenv("THRESH", "15"))
    MIN_AREA = int(os.getenv("MIN_AREA", "1500"))
    PROC_WIDTH = int(os.getenv("PROC_WIDTH", "320"))
    DILATE_ITERS = int(os.getenv("DILATE_ITERS", "2"))
    MERGE_PADDING = int(os.getenv("MERGE_PADDING", "15"))
    BOX_COLOR_BGR = _parse_hex_color(os.getenv("BOX_COLOR", "#ffa500"))
    BOX_THICKNESS = int(os.getenv("BOX_THICKNESS", "2"))

    SEND_TG_ON_MOTION = _getenv_bool("SEND_TG_ON_MOTION", True)
    MOTION_ALERT_COOLDOWN_SEC = int(os.getenv("MOTION_ALERT_COOLDOWN_SEC", "30"))
    PREVIEW_MAX_WIDTH = int(os.getenv("PREVIEW_MAX_WIDTH", "640"))
    PHOTO_JPEG_QUALITY = int(os.getenv("PHOTO_JPEG_QUALITY", "80"))

    return Settings(
        SNAPSHOT_HOME=SNAPSHOT_HOME,
        SNAPSHOT_URL_INIT=SNAPSHOT_URL_INIT,
        SNAPSHOT_REFERER=SNAPSHOT_REFERER,
        SNAPSHOT_COOKIE=SNAPSHOT_COOKIE,
        USE_SELENIUM=USE_SELENIUM,
        SELENIUM_BROWSER=SELENIUM_BROWSER,
        SHOW_WINDOW=SHOW_WINDOW,
        WINDOW_TITLE=WINDOW_TITLE,
        TG_BOT_TOKEN=TG_BOT_TOKEN,
        TG_CHAT_ID=TG_CHAT_ID,
        ENABLE_MOTION=ENABLE_MOTION,
        THRESH=THRESH,
        MIN_AREA=MIN_AREA,
        PROC_WIDTH=PROC_WIDTH,
        DILATE_ITERS=DILATE_ITERS,
        MERGE_PADDING=MERGE_PADDING,
        BOX_COLOR_BGR=BOX_COLOR_BGR,
        BOX_THICKNESS=BOX_THICKNESS,
        SEND_TG_ON_MOTION=SEND_TG_ON_MOTION,
        MOTION_ALERT_COOLDOWN_SEC=MOTION_ALERT_COOLDOWN_SEC,
        PREVIEW_MAX_WIDTH=PREVIEW_MAX_WIDTH,
        PHOTO_JPEG_QUALITY=PHOTO_JPEG_QUALITY,
    )
