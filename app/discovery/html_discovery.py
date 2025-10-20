# método 3 (HTML)

from __future__ import annotations
import sys
import re
import urllib.request
from urllib.parse import urljoin

def discover_snapshot_base_from_home(home_url: str, referer: str,
                                     cookie: str, set_base_cb, set_cookie_cb) -> bool:
    if not home_url:
        print("[DISCOVER] SNAPSHOT_HOME vacío", file=sys.stderr)
        return False

    headers = {
        "User-Agent": "Mozilla/5.0 (MotionClient)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": referer or ""
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        req = urllib.request.Request(home_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            set_cookie = resp.headers.get("Set-Cookie")
            if set_cookie:
                set_cookie_cb(set_cookie.split(";", 1)[0].strip())

        m = re.search(r'out\.jpg\?[^"\'\s<]+', html, re.IGNORECASE)
        if not m:
            print("[DISCOVER] No se encontró 'out.jpg?...' en la HOME", file=sys.stderr)
            return False

        rel = m.group(0)
        base = urljoin(home_url, rel)
        set_base_cb(base)
        print(f"[DISCOVER] Base descubierta: {base}")
        return True

    except Exception as e:
        print(f"[DISCOVER][ERR] {repr(e)}", file=sys.stderr)
        return False
