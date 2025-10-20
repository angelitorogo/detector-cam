from __future__ import annotations
import sys
import requests

def enabled(token: str, chat_id: str) -> bool:
    return bool(token and chat_id)

def send_text(token: str, chat_id: str, text: str) -> bool:
    """
    Envía texto a Telegram. Devuelve True si OK.
    Loguea causas típicas si falla (401 token, 400 chat).
    """
    if not enabled(token, chat_id):
        print("[TG] Deshabilitado: falta TG_BOT_TOKEN o TG_CHAT_ID", file=sys.stderr)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text},
            timeout=15
        )
        if r.ok:
            return True

        # Logs más expresivos
        msg = f"[TG] sendMessage fallo {r.status_code}: {r.text}"
        if r.status_code == 401:
            msg += "  (Token inválido)"
        elif r.status_code == 400:
            msg += "  (Chat no válido o el bot no tiene conversación/permiso)"
        print(msg, file=sys.stderr)
        return False

    except Exception as e:
        print(f"[TG] Error de red/envío: {e}", file=sys.stderr)
        return False
