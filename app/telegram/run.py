from __future__ import annotations
import time

from app.discovery.flow import discover_snapshot_base
from app.net.snapshot import get_frame_once
from app.video.viewer import create_window, show_frame, should_quit, destroy_all
from app.telegram.client import send_text, enabled


def run_viewer(settings, state):
    print("▶ Iniciando visor de webcam (solo vista).")

    # 1) Descubrir base si no viene
    if not state.snapshot_base:
        ok = discover_snapshot_base(settings, state, prefer_selenium=True)
        if not ok:
            print("❌ No se pudo descubrir la URL del snapshot (selenium/redir/html).")
            return

    # 2) Probar primer frame (si falla, re-descubrir una vez)
    print("Probando acceso a la URL…")
    ok, frame = get_frame_once(state.snapshot_base, settings.SNAPSHOT_REFERER, state.snapshot_cookie)
    if not ok or frame is None:
        print("[BOOT] Reintentando descubrimiento…")
        ok2 = discover_snapshot_base(settings, state, prefer_selenium=True)
        if ok2:
            ok, frame = get_frame_once(state.snapshot_base, settings.SNAPSHOT_REFERER, state.snapshot_cookie)

    if not ok or frame is None:
        print("❌ No se pudo obtener el primer frame.")
        return

    # ✅ Aviso Telegram: visor arrancado
    if enabled(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID):
        send_text(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID, "✅ Visor iniciado: primer frame OK.")

    h0, w0 = frame.shape[:2]
    print(f"[OK] Base snapshot:  {state.snapshot_base}")
    print(f"[OK] Resolución: {w0}x{h0}")

    if settings.SHOW_WINDOW:
        create_window(settings.WINDOW_TITLE)

    # 3) Bucle (mostrar + auto-recovery)
    fail_count = 0
    MAX_FAILS_BEFORE_REDISCOVER = 3
    last_ts = time.time()
    fps_est = 5.0
    alpha_fps = 0.2

    try:
        while True:
            ok, frame = get_frame_once(state.snapshot_base, settings.SNAPSHOT_REFERER, state.snapshot_cookie)
            if not ok or frame is None:
                fail_count += 1
                if fail_count >= MAX_FAILS_BEFORE_REDISCOVER:
                    print("[RECOVER] Fallos seguidos; re-descubriendo (selenium→redir→html)…")
                    okr = discover_snapshot_base(settings, state, prefer_selenium=True)
                    fail_count = 0
                    time.sleep(0.5)
                else:
                    time.sleep(0.2)
                continue
            fail_count = 0

            # FPS estimado (solo display)
            now_ts = time.time()
            dt = now_ts - last_ts
            last_ts = now_ts
            if 0 < dt < 1.0:
                fps_est = fps_est * (1 - alpha_fps) + (1.0 / dt) * alpha_fps

            if settings.SHOW_WINDOW:
                show_frame(settings.WINDOW_TITLE, frame, fps_est)
                if should_quit():
                    break
    finally:
        destroy_all()
        print("⏹ Visor cerrado.")
        # ✅ Aviso Telegram: visor detenido
        if enabled(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID):
            send_text(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID, "⏹ Visor detenido.")
