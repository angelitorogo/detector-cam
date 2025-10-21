from __future__ import annotations
import os
import time
import json
import threading
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.parse

from app.common.state import set_armed, is_armed, ensure_initial_state
from app.telegram.client import send_text, send_photo_bgr  # ya existen en tu proyecto

def _runtime_dir() -> Path:
    raw = os.getenv("RUNTIME_DIR", "./runtime")
    p = Path(raw).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _latest_snapshot_path() -> Path:
    return _runtime_dir() / "latest.jpg"

def _commands_path() -> Path:
    return _runtime_dir() / "commands.json"

def _atomic_write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        except Exception:
            pass

def _enqueue_command(cmd: dict) -> None:
    """
    Añade un comando a commands.json (lista de dicts) de forma atómica.
    """
    path = _commands_path()
    # Leer lo existente (si hay)
    existing = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8")) or []
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    existing.append(cmd)
    _atomic_write_json(path, existing)

def _get_updates(token: str, offset: int | None, timeout: int = 25):
    base = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": str(timeout)}
    if offset is not None:
        params["offset"] = str(offset)
    url = base + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout + 5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("ok"):
        return []
    return data.get("result", [])

def _read_snapshot_with_retries(p: Path, retries: int = 6, delay: float = 0.15):
    """
    Intenta leer el snapshot con pequeños reintentos para evitar leer el archivo
    durante un replace/guardado en curso.
    """
    try:
        import cv2
    except Exception as e:
        print(f"[BOT] OpenCV no disponible: {e}")
        return None

    for _ in range(retries):
        try:
            if not p.exists():
                time.sleep(delay)
                continue
            try:
                size = p.stat().st_size
                if size == 0:
                    time.sleep(delay)
                    continue
            except Exception:
                time.sleep(delay)
                continue

            img = cv2.imread(str(p))
            if img is not None:
                return img

            time.sleep(delay)
        except Exception:
            time.sleep(delay)
    return None

def _loop(settings) -> None:
    allow_cmds = os.getenv("ALLOW_TG_COMMANDS", "false").lower() == "true"
    if not allow_cmds:
        print("[BOT] ALLOW_TG_COMMANDS=false -> bot desactivado.")
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN") or getattr(settings, "TG_BOT_TOKEN", None)
    if not token:
        print("[BOT] Falta TELEGRAM_BOT_TOKEN -> bot desactivado.")
        return

    allowed_chat = (os.getenv("TELEGRAM_CHAT_ID", "").strip()
                    or str(getattr(settings, "TG_CHAT_ID", "") or "")).strip()

    ensure_initial_state()
    print(f"[BOT] Poller activo. RUNTIME={_runtime_dir()} allowed_chat={allowed_chat or '*'}")

    offset = None
    while True:
        try:
            updates = _get_updates(token, offset)
            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg or "text" not in msg:
                    continue
                chat_id = str(msg["chat"]["id"]).strip()
                text = (msg["text"] or "").strip()

                if allowed_chat and chat_id != allowed_chat:
                    continue

                low = text.lower()
                if low.startswith("/arm"):
                    set_armed(True)
                    send_text(token, chat_id, "🔒 Sistema ARMADO.")
                elif low.startswith("/disarm"):
                    set_armed(False)
                    send_text(token, chat_id, "🔓 Sistema DESARMADO.")
                elif low.startswith("/status"):
                    status = "ARMADO 🔒" if is_armed() else "DESARMADO 🔓"
                    send_text(token, chat_id, f"Estado: {status}")
                elif low.startswith("/snapshot"):
                    p = _latest_snapshot_path()
                    img = _read_snapshot_with_retries(p)
                    if img is not None:
                        send_photo_bgr(token, chat_id, img, caption="📸 Snapshot")
                    else:
                        send_text(token, chat_id, f"⚠️ No se pudo leer el snapshot en {p} (cv2.imread=None).")
                elif low.startswith("/clip"):
                    # Formato: /clip N   (N en segundos, entero o float)
                    parts = text.split()
                    dur = 10.0  # por defecto 10 s
                    if len(parts) >= 2:
                        try:
                            dur = float(parts[1].replace(",", "."))
                            if dur <= 0:
                                dur = 1.0
                        except Exception:
                            pass
                    cmd = {
                        "type": "force_clip",
                        "duration_sec": dur,
                        "ts": time.time()
                    }
                    _enqueue_command(cmd)
                    send_text(token, chat_id, f"🎬 Clip forzado: {dur:.1f} s (con preroll).")
        except Exception as e:
            print(f"[BOT] loop error: {e}")
            time.sleep(1)

def start_poller(settings) -> None:
    t = threading.Thread(target=_loop, args=(settings,), daemon=True)
    t.start()
