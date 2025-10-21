from __future__ import annotations

# 0) Carga .env ANTES de leer variables
import os
from dotenv import load_dotenv
load_dotenv()

import sys
import time
import json
from pathlib import Path
import cv2

from app.discovery.flow import discover_snapshot_base
from app.net.snapshot import get_frame_once
from app.video.viewer import create_window, show_frame, should_quit, destroy_all
from app.telegram.client import send_text, enabled, send_photo_bgr
from app.vision.motion import preprocess_frame, diff_and_boxes, merge_boxes

# Estado armado / bot
from app.common.state import is_armed, ensure_initial_state
from app.bot.poller import start_poller

# Recorder de clips
from app.record.recorder import ClipRecorder

# === Opcional: envío de vídeo a Telegram (si existe esta función en tu cliente) ===
try:
    from app.telegram.client import send_video_file as tg_send_video_file  # (token, chat_id, file_path, caption=None)
except Exception:
    tg_send_video_file = None


# === Runtime (para snapshots y cola de órdenes) ===
def _runtime_dir() -> Path:
    raw = os.getenv("RUNTIME_DIR", "./runtime")
    p = Path(raw).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _latest_snapshot_path() -> Path:
    return _runtime_dir() / "latest.jpg"

def _commands_path() -> Path:
    return _runtime_dir() / "commands.json"

def _atomic_replace(path: Path, payload) -> None:
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

def _drain_commands() -> list[dict]:
    """
    Lee y vacía la cola de órdenes (lista de dicts) de forma atómica.
    Devuelve la lista (puede ser vacía).
    """
    path = _commands_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8")) or []
        # vaciar cola
        _atomic_replace(path, [])
        if isinstance(data, list):
            return data
        return []
    except Exception:
        # Si hay error de lectura, intenta vaciar para evitar repetición
        try:
            _atomic_replace(path, [])
        except Exception:
            pass
        return []

def _save_latest_frame_bgr(frame, jpeg_quality: int = 85) -> None:
    """
    Guardado ATÓMICO: imencode → .tmp → os.replace() a latest.jpg
    """
    dst = _latest_snapshot_path()
    tmp = dst.with_suffix(dst.suffix + ".tmp")

    if frame is None or frame.size == 0:
        return

    try:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)])
        if not ok:
            return
        with open(tmp, "wb") as f:
            f.write(buf.tobytes())
        os.replace(tmp, dst)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        except Exception:
            pass


# === Utilidad para preview con cajas ===
def _make_preview_with_boxes(frame, boxes, sx, sy, color_bgr, thick, max_w):
    vis = frame.copy()
    for (x, y, w, h) in boxes:
        X1 = int(x * sx); Y1 = int(y * sy)
        X2 = int((x + w) * sx); Y2 = int((y + h) * sy)
        cv2.rectangle(vis, (X1, Y1), (X2, Y2), color_bgr, max(1, thick))
    if max_w and vis.shape[1] > max_w:
        ratio = max_w / float(vis.shape[1])
        vis = cv2.resize(vis, (max_w, int(vis.shape[0] * ratio)), interpolation=cv2.INTER_AREA)
    return vis


def run_viewer(settings, state):
    print("▶ Iniciando visor de webcam (vista + detección opcional).")
    print(f"[INIT] RUNTIME_DIR={_runtime_dir()}  SNAPSHOT={_latest_snapshot_path()}  CMDS={_commands_path()}")

    # 0) Estado inicial y poller
    ensure_initial_state()         # aplica ARMED_ON_BOOT cada arranque
    start_poller(settings)

    # === Configuración de grabación ===
    record_on_motion = (os.getenv("RECORD_ON_MOTION", str(getattr(settings, "RECORD_ON_MOTION", "false"))).lower() == "true")
    clip_dir_env = os.getenv("CLIP_DIR", getattr(settings, "CLIP_DIR", "clips"))
    pre_roll_sec = float(os.getenv("PRE_ROLL_SEC", getattr(settings, "PRE_ROLL_SEC", 3)))
    post_roll_sec = float(os.getenv("POST_ROLL_SEC", getattr(settings, "POST_ROLL_SEC", 5)))
    quiet_gap_sec = float(os.getenv("QUIET_GAP_SEC", getattr(settings, "QUIET_GAP_SEC", 2)))
    max_clip_sec = float(os.getenv("MAX_CLIP_SEC", getattr(settings, "MAX_CLIP_SEC", 60)))
    max_disk_gb = float(os.getenv("MAX_DISK_GB", getattr(settings, "MAX_DISK_GB", 2)))
    video_fps_cfg = os.getenv("VIDEO_FPS", getattr(settings, "VIDEO_FPS", None))
    video_fps = float(video_fps_cfg) if str(video_fps_cfg).strip() not in ("", "None") else None
    video_codec = str(os.getenv("VIDEO_CODEC", getattr(settings, "VIDEO_CODEC", "mp4v"))).strip() or "mp4v"

    tg_send_clips = (os.getenv("TG_SEND_CLIPS", str(getattr(settings, "TG_SEND_CLIPS", "false"))).lower() == "true")
    tg_clip_cooldown = float(os.getenv("TG_CLIP_COOLDOWN_SEC", getattr(settings, "TG_CLIP_COOLDOWN_SEC", 30)))

    # Inicializa recorder
    runtime = _runtime_dir()
    clip_dir = Path(clip_dir_env) if os.path.isabs(clip_dir_env) else (runtime / clip_dir_env)
    recorder = ClipRecorder(
        base_dir=runtime,
        clip_dir=clip_dir,
        pre_roll_sec=pre_roll_sec,
        post_roll_sec=post_roll_sec,
        quiet_gap_sec=quiet_gap_sec,
        max_clip_sec=max_clip_sec,
        video_fps=video_fps,
        video_codec=video_codec,
        quota_gb=max_disk_gb,
    )

    # 1) Descubrir base si no viene
    if not state.snapshot_base:
        ok = discover_snapshot_base(settings, state, prefer_selenium=True)
        if not ok:
            print("❌ No se pudo descubrir la URL del snapshot (selenium/redir/html).")
            return

    # 2) Primer frame
    print("Probando acceso a la URL…")
    ok, frame = get_frame_once(state.snapshot_base, settings.SNAPSHOT_REFERER, state.snapshot_cookie)
    if not ok or frame is None:
        print("[BOOT] Reintentando descubrimiento…", file=sys.stderr)
        ok2 = discover_snapshot_base(settings, state, prefer_selenium=True)
        if ok2:
            ok, frame = get_frame_once(state.snapshot_base, settings.SNAPSHOT_REFERER, state.snapshot_cookie)

    if not ok or frame is None:
        print("❌ No se pudo obtener el primer frame.")
        return

    # ✅ Telegram: inicio
    if enabled(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID):
        ok_tg = send_text(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID, "✅ Visor iniciado: primer frame OK.")
        if not ok_tg:
            print("[TG] Aviso de inicio NO enviado. Revisa logs anteriores.", file=sys.stderr)
    else:
        print("[TG] Deshabilitado: define TG_BOT_TOKEN y TG_CHAT_ID en .env", file=sys.stderr)

    h0, w0 = frame.shape[:2]
    print(f"[OK] Base snapshot:  {state.snapshot_base}")
    print(f"[OK] Resolución: {w0}x{h0}")

    if settings.SHOW_WINDOW:
        create_window(settings.WINDOW_TITLE)

    # --- Estado para motion ---
    prev_gray = None
    sx = sy = 1.0
    if settings.ENABLE_MOTION:
        prev_gray, sx, sy = preprocess_frame(frame, settings.PROC_WIDTH)

    # Alertas TG movimiento
    last_motion_alert_ts = 0.0

    # FPS estimado para UI (no crítico). El recorder usa video_fps si está definido.
    last_ts = time.time()
    fps_est = 5.0
    alpha_fps = 0.2

    # Bucle principal
    fail_count = 0
    MAX_FAILS_BEFORE_REDISCOVER = 3

    # Cooldown para envío de clips a TG
    last_clip_sent_ts = 0.0

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

        # === Snapshot (atómico) para /snapshot
        _save_latest_frame_bgr(frame, jpeg_quality=getattr(settings, "PHOTO_JPEG_QUALITY", 90))

        # Timestamps y FPS est.
        now_ts = time.time()
        dt = now_ts - last_ts
        last_ts = now_ts
        if 0 < dt < 1.0:
            fps_est = fps_est * (1 - alpha_fps) + (1.0 / dt) * alpha_fps

        vis = frame

        # Notificar frame al recorder SIEMPRE (para mantener preroll)
        recorder.notify_frame(now_ts, frame, fps_hint=fps_est)

        # ---- CONSUMIR ÓRDENES DEL BOT (p.ej. /clip N) ----
        for cmd in _drain_commands():
            if not isinstance(cmd, dict):
                continue
            if cmd.get("type") == "force_clip":
                try:
                    dur = float(cmd.get("duration_sec", 10.0))
                except Exception:
                    dur = 10.0
                # Forzamos clip de 'dur' segundos desde AHORA (con preroll)
                recorder.force_clip(now_ts, frame, duration_sec=dur)
                print(f"[CMD] force_clip recibido → {dur:.1f} s")

        # --- Detección de movimiento (opcional) ---
        boxes = []
        motion_now = False
        if settings.ENABLE_MOTION:
            gray, sx, sy = preprocess_frame(frame, settings.PROC_WIDTH)
            min_area_eff = settings.MIN_AREA if settings.MIN_AREA > 0 else max(300, int(0.003 * gray.size))
            if prev_gray is None:
                prev_gray = gray
            boxes = diff_and_boxes(prev_gray, gray, settings.THRESH, min_area_eff, settings.DILATE_ITERS)
            boxes = merge_boxes(boxes, settings.MERGE_PADDING)
            prev_gray = gray
            motion_now = bool(boxes)

            # Dibujo cajas
            if boxes:
                for (x, y, w, h) in boxes:
                    X1 = int(x * sx); Y1 = int(y * sy)
                    X2 = int((x + w) * sx); Y2 = int((y + h) * sy)
                    cv2.rectangle(vis, (X1, Y1), (X2, Y2), settings.BOX_COLOR_BGR, max(1, settings.BOX_THICKNESS))

            # 📣 ALERTA TG (foto) SOLO SI ARMADO
            if motion_now and is_armed() and settings.SEND_TG_ON_MOTION and enabled(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID):
                if (now_ts - last_motion_alert_ts) >= max(1, settings.MOTION_ALERT_COOLDOWN_SEC):
                    preview = _make_preview_with_boxes(
                        frame, boxes, sx, sy,
                        settings.BOX_COLOR_BGR, settings.BOX_THICKNESS,
                        settings.PREVIEW_MAX_WIDTH
                    )
                    caption = "🚨 Movimiento detectado"
                    okp = send_photo_bgr(
                        settings.TG_BOT_TOKEN, settings.TG_CHAT_ID,
                        preview, caption=caption, jpeg_quality=getattr(settings, "PHOTO_JPEG_QUALITY", 90)
                    )
                    if not okp:
                        print("[TG] No se pudo enviar la foto de movimiento.", file=sys.stderr)
                    last_motion_alert_ts = now_ts

        # 🎥 LÓGICA DE CLIPS (por movimiento o por /clip N)
        # - Por movimiento solo actúa si ARMADO
        if (record_on_motion and is_armed()) and motion_now:
            recorder.notify_motion(now_ts, frame)

        # Tick: puede cerrar clip si toca; si lo cierra, devuelve la ruta
        closed_path = recorder.tick(now_ts)
        if closed_path:
            print(f"[REC] Clip finalizado: {closed_path}")
            # Envío opcional a Telegram (si hay función disponible)
            if (os.getenv("TG_SEND_CLIPS", "false").lower() == "true") and tg_send_video_file and enabled(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID):
                # cooldown
                if (now_ts - last_clip_sent_ts) >= max(1.0, float(os.getenv("TG_CLIP_COOLDOWN_SEC", 30))):
                    try:
                        okv = tg_send_video_file(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID, str(closed_path), caption="🎥 Clip")
                        if not okv:
                            print("[TG] No se pudo enviar el clip de vídeo.", file=sys.stderr)
                        else:
                            last_clip_sent_ts = now_ts
                    except Exception as e:
                        print(f"[TG] Error enviando clip: {e}", file=sys.stderr)
            elif (os.getenv("TG_SEND_CLIPS", "false").lower() == "true") and not tg_send_video_file:
                print("[TG] Aviso: TG_SEND_CLIPS=true pero no hay send_video_file() en app.telegram.client. Se omite el envío.")

        # Ventana
        if settings.SHOW_WINDOW:
            show_frame(settings.WINDOW_TITLE, vis, fps_est)
            if should_quit():
                break

    destroy_all()
    print("⏹ Visor cerrado.")

    # ✅ Telegram: fin
    if enabled(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID):
        ok_tg_end = send_text(settings.TG_BOT_TOKEN, settings.TG_CHAT_ID, "⏹ Visor detenido.")
        if not ok_tg_end:
            print("[TG] Aviso de parada NO enviado. Revisa logs anteriores.", file=sys.stderr)
