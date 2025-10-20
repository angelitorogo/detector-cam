# construir URL y descargar frames

from __future__ import annotations
import sys
import time
import numpy as np
import urllib.request
from urllib.parse import urlparse, urlencode, urlunparse, parse_qs

def build_snapshot_url(snapshot_base: str) -> str:
    """Añade/actualiza &r=timestamp a la URL base (anti caché)."""
    if not snapshot_base:
        return ""
    p = urlparse(snapshot_base)
    qs = parse_qs(p.query, keep_blank_values=True)

    # 🔧 Fuerza calidad alta
    qs["q"] = ["90"]  #quitar cuando pasemos a la grabacion

    qs["r"] = [str(int(time.time() * 1000))]
    return urlunparse(p._replace(query=urlencode(qs, doseq=True)))

def get_frame_once(snapshot_base: str, referer: str, cookie: str):
    """
    Descarga un frame JPEG y lo devuelve como ndarray BGR.
    Retorna (ok: bool, frame | None).
    """
    import cv2  # local import por rapidez de arranque

    url = build_snapshot_url(snapshot_base)
    if not url:
        print("[FRAME] snapshot_base vacío; no se puede construir URL", file=sys.stderr)
        return False, None

    headers = {
        "User-Agent": "Mozilla/5.0 (MotionClient)",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Referer": referer or ""
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()

        if not data:
            print(f"[FRAME] Respuesta vacía desde {url}", file=sys.stderr)
            return False, None

        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            print("[FRAME] imdecode devolvió None", file=sys.stderr)
            return False, None

        return True, frame

    except urllib.error.HTTPError as e:
        print(f"[FRAME][HTTP {e.code}] {e.reason} en {url}", file=sys.stderr)
    except Exception as e:
        print(f"[FRAME][ERR] {repr(e)}", file=sys.stderr)
    return False, None
