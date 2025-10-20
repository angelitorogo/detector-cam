# método 2 (redir)

from __future__ import annotations
import sys
import urllib.request
from urllib.parse import urljoin

def discover_snapshot_base_via_redirect(home_url: str, referer: str,
                                        cookie: str, set_base_cb, set_cookie_cb) -> bool:
    if not home_url:
        return False

    probe = urljoin(home_url, "out.jpg?q=30")
    headers = {
        "User-Agent": "Mozilla/5.0 (MotionClient)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": referer or ""
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        req = urllib.request.Request(probe, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            final_url = resp.geturl()
            set_cookie = resp.headers.get("Set-Cookie")
            if set_cookie:
                set_cookie_cb(set_cookie.split(";", 1)[0].strip())

        if "out.jpg" in final_url and "id=" in final_url:
            if "&r=" in final_url:
                final_url = final_url.split("&r=")[0]
            set_base_cb(final_url)
            print(f"[DISCOVER-REDIR] Base descubierta: {final_url}")
            return True

        print(f"[DISCOVER-REDIR] Respuesta sin id: {final_url}")
        return False

    except Exception as e:
        print(f"[DISCOVER-REDIR][ERR] {repr(e)}", file=sys.stderr)
        return False
