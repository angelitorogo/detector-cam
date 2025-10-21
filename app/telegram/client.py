from __future__ import annotations
import sys, mimetypes, uuid, urllib.request
import requests
import cv2
from pathlib import Path


def enabled(token: str, chat_id: str) -> bool:
    return bool(token and chat_id)

def send_text(token: str, chat_id: str, text: str) -> bool:
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

def send_photo_bgr(token: str, chat_id: str, frame_bgr, caption: str = "", jpeg_quality: int = 80) -> bool:
    """
    Envía un frame BGR como foto a Telegram.
    """
    if not enabled(token, chat_id):
        print("[TG] Deshabilitado: falta TG_BOT_TOKEN o TG_CHAT_ID", file=sys.stderr)
        return False
    try:
        q = min(100, max(1, int(jpeg_quality)))
        ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), q])
        if not ok:
            print("[TG] No se pudo codificar JPEG", file=sys.stderr)
            return False
        files = {"photo": ("preview.jpg", buf.tobytes(), "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption}
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=data, files=files, timeout=30)
        if r.ok:
            return True
        print(f"[TG] sendPhoto fallo {r.status_code}: {r.text}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[TG] Error de red/envío (foto): {e}", file=sys.stderr)
        return False
    

def send_video_file(bot_token: str, chat_id: str, file_path: str, caption: str | None = None) -> bool:
    """
    Envía un MP4 al chat indicado usando Telegram Bot API (sendVideo).
    Devuelve True/False.
    """
    try:
        video_path = Path(file_path)
        if not video_path.exists():
            print(f"[TG] Video no existe: {file_path}", file=sys.stderr)
            return False

        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}

        mime, _ = mimetypes.guess_type(video_path.name)
        if not mime: mime = "video/mp4"

        def part(name: str, value: str) -> bytes:
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")

        def file_part(name: str, filename: str, content_type: str, data: bytes) -> bytes:
            header = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
            return header + data + b"\r\n"

        body = b""
        body += part("chat_id", str(chat_id))
        if caption:
            body += part("caption", caption)

        data = video_path.read_bytes()
        body += file_part("video", video_path.name, mime, data)
        body += f"--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            _ = resp.read()  # 200 OK → enviado
        return True

    except Exception as e:
        print(f"[TG] Error al enviar video: {e}", file=sys.stderr)
        return False    
