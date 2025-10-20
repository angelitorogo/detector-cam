# orquestación del descubrimiento

from __future__ import annotations
from typing import Callable

from .selenium_discovery import discover_snapshot_base_via_selenium
from .redirect_discovery import discover_snapshot_base_via_redirect
from .html_discovery import discover_snapshot_base_from_home

def discover_snapshot_base(settings, state,
                           prefer_selenium: bool = True) -> bool:
    """
    Intenta descubrir la URL base del snapshot (sin &r=).
    Orden: Selenium → Redirección → HTML (o sin Selenium si está desactivado).
    """
    set_base = lambda url: setattr(state, "snapshot_base", url)
    set_cookie = lambda ck: setattr(state, "snapshot_cookie", ck)

    ok = False
    if prefer_selenium and settings.USE_SELENIUM:
        ok = discover_snapshot_base_via_selenium(
            settings.SNAPSHOT_HOME, settings.SELENIUM_BROWSER, set_base, set_cookie
        )
    if not ok:
        ok = discover_snapshot_base_via_redirect(
            settings.SNAPSHOT_HOME, settings.SNAPSHOT_REFERER, state.snapshot_cookie, set_base, set_cookie
        )
    if not ok:
        ok = discover_snapshot_base_from_home(
            settings.SNAPSHOT_HOME, settings.SNAPSHOT_REFERER, state.snapshot_cookie, set_base, set_cookie
        )
    return ok
