from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

def _getenv_bool(name: str, default: bool) -> bool:
    v = os.getenv(name, str(default)).strip().lower()
    return v in ("1", "true", "yes", "y", "on")

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
    )
