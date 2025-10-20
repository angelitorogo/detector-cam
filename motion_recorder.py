#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# archivo principal (mínimo)

from app.config import load_settings
from app.state import RuntimeState
from app.run import run_viewer

if __name__ == "__main__":
    try:
        settings = load_settings()
        state = RuntimeState(snapshot_base=settings.SNAPSHOT_URL_INIT,
                             snapshot_cookie=settings.SNAPSHOT_COOKIE)
        run_viewer(settings, state)
    except KeyboardInterrupt:
        pass
