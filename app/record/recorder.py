from __future__ import annotations
import os
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Deque, Tuple, List, Optional
from collections import deque
import cv2


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class CircularFrameBuffer:
    """Buffer circular por tiempo (segundos), guarda (ts, frame)."""
    max_seconds: float
    frames: Deque[Tuple[float, any]] = field(default_factory=deque)

    def push(self, ts: float, frame) -> None:
        self.frames.append((ts, frame.copy()))
        self._trim(ts)

    def _trim(self, now_ts: float) -> None:
        # Mantener solo frames dentro de la ventana (now - max_seconds, now]
        limit = now_ts - max(0.0, self.max_seconds)
        while self.frames and self.frames[0][0] < limit:
            self.frames.popleft()

    def get_since(self, ts_from: float) -> List[Tuple[float, any]]:
        """Devuelve una lista de (ts, frame) desde ts_from (incluido)."""
        return [(ts, f) for ts, f in self.frames if ts >= ts_from]


@dataclass
class DiskQuota:
    max_gb: float

    def enforce(self, dir_path: Path) -> None:
        """Borra ficheros .mp4 más antiguos hasta bajar de la cuota."""
        if self.max_gb <= 0:
            return
        total_bytes = 0
        mp4s = []
        for p in dir_path.glob("*.mp4"):
            try:
                st = p.stat()
                size = st.st_size
                total_bytes += size
                mp4s.append((st.st_mtime, size, p))
            except Exception:
                continue
        limit = int(self.max_gb * (1024**3))
        if total_bytes <= limit:
            return
        # Ordenar por más antiguo primero
        mp4s.sort(key=lambda x: x[0])
        for _, size, p in mp4s:
            try:
                p.unlink(missing_ok=True)
                total_bytes -= size
            except Exception:
                pass
            if total_bytes <= limit:
                break


@dataclass
class ClipSession:
    """Estado de una sesión de actividad (clip en curso)."""
    open_ts: float
    extend_until: float
    last_motion_ts: float
    writer: Optional[cv2.VideoWriter]
    frames_written: int = 0
    path: Optional[Path] = None
    reason: str = "motion"  # "motion" | "manual"

    def duration(self, now_ts: float) -> float:
        return max(0.0, now_ts - self.open_ts)


class ClipRecorder:
    """
    Gestiona:
      - Preroll (buffer circular de frames)
      - Apertura de clip con frames de preroll
      - Extensión del fin con nuevos eventos
      - Cierre por quiet gap, fin provisional o MAX_CLIP_SEC
      - Cuota de disco
      - Forzado de clip manual (/clip N)
    """
    def __init__(
        self,
        base_dir: Path,
        clip_dir: Path,
        pre_roll_sec: float = 3.0,
        post_roll_sec: float = 5.0,
        quiet_gap_sec: float = 2.0,
        max_clip_sec: float = 60.0,
        video_fps: Optional[float] = None,
        video_codec: str = "mp4v",
        quota_gb: float = 2.0,
    ):
        self.base_dir = _ensure_dir(base_dir)
        self.clip_dir = _ensure_dir(clip_dir if clip_dir.is_absolute() else (self.base_dir / clip_dir))
        self.pre_roll_sec = max(0.0, float(pre_roll_sec))
        self.post_roll_sec = max(0.0, float(post_roll_sec))
        self.quiet_gap_sec = max(0.0, float(quiet_gap_sec))
        self.max_clip_sec = max(1.0, float(max_clip_sec))
        self.video_fps = video_fps  # si None, se estimará en caliente
        self.video_codec = video_codec
        self.quota = DiskQuota(quota_gb)
        self.buffer = CircularFrameBuffer(self.pre_roll_sec)
        self.session: Optional[ClipSession] = None

    # -------- API principal llamada desde run.py --------

    def notify_frame(self, ts: float, frame, fps_hint: Optional[float] = None) -> None:
        """Se llama en CADA frame del bucle principal."""
        self.buffer.push(ts, frame)
        # Si hay sesión abierta, escribe el frame
        if self.session and self.session.writer is not None:
            self._write_frame_to_session(frame)

    def notify_motion(self, ts: float, frame) -> None:
        """Se llama en eventos de movimiento detectado (cuando está armado)."""
        if self.session is None:
            # Abrir nueva sesión con preroll
            self._open_session(ts, frame, reason="motion")
        # Extiende la ventana de cierre
        self.session.last_motion_ts = ts
        self.session.extend_until = ts + self.post_roll_sec

    def force_clip(self, ts: float, frame, duration_sec: float) -> None:
        """
        Forzar un clip 'manual' de duración N segundos desde ahora (incluye preroll).
        Si ya hay una sesión abierta, la extiende hasta al menos ts + N.
        """
        duration = max(1.0, float(duration_sec))
        if self.session is None:
            self._open_session(ts, frame, reason="manual")
        # “Mantener viva” la sesión hasta al menos ts + duration
        self.session.last_motion_ts = ts  # evita quiet-gap prematuro
        target_end = ts + duration
        if self.session.extend_until < target_end:
            self.session.extend_until = target_end
        print(f"[REC] force_clip: reason={self.session.reason} extend_until={self.session.extend_until:.3f}")

    def tick(self, ts: float) -> Optional[Path]:
        """Llamar periódicamente: decide cierres por quiet gap o límites. Devuelve la ruta del clip cerrado (si lo hay)."""
        if not self.session:
            return None

        # Cierre por MAX_CLIP_SEC
        if self.session.duration(ts) >= self.max_clip_sec:
            path = self._close_session(ts)
            self._after_close_cleanup()
            return path

        # Cierre por quiet gap (si no hubo "keepalive") y hemos pasado extend_until
        if (ts - self.session.last_motion_ts) >= self.quiet_gap_sec and ts >= self.session.extend_until:
            path = self._close_session(ts)
            self._after_close_cleanup()
            return path

        return None

    # -------------------- Internos --------------------

    def _open_session(self, ts: float, frame, reason: str) -> None:
        # Target fps
        fps = float(self.video_fps) if self.video_fps and self.video_fps > 0 else 12.0
        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*self.video_codec)
        # nombre de archivo
        suffix = "man" if reason == "manual" else "mov"
        fname = time.strftime(f"clip_%Y%m%d_%H%M%S_{suffix}.mp4", time.localtime(ts))
        out_path = self.clip_dir / fname

        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
        if not writer or not writer.isOpened():
            # fallback a mp4v si el codec no abre
            if self.video_codec.lower() != "mp4v":
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
        if not writer or not writer.isOpened():
            print(f"[REC] ERROR: No se pudo abrir VideoWriter para {out_path}")
            self.session = None
            return

        self.session = ClipSession(
            open_ts=ts,
            extend_until=ts + self.post_roll_sec,
            last_motion_ts=ts,
            writer=writer,
            frames_written=0,
            path=out_path,
            reason=reason,
        )

        # Escribir preroll (desde ts - pre_roll_sec)
        start_from = ts - self.pre_roll_sec
        for _ts, _frame in self.buffer.get_since(start_from):
            self._write_frame_to_session(_frame)

        print(f"[REC] Sesión ABIERTA ({reason}) → {out_path}  (fps={fps}, size={w}x{h})")

    def _write_frame_to_session(self, frame) -> None:
        try:
            self.session.writer.write(frame)
            self.session.frames_written += 1
        except Exception as e:
            print(f"[REC] ERROR al escribir frame: {e}")

    def _close_session(self, ts: float) -> Optional[Path]:
        if not self.session:
            return None
        path = self.session.path
        try:
            if self.session.writer:
                self.session.writer.release()
            print(f"[REC] Sesión CERRADA → {path} (frames={self.session.frames_written}, reason={self.session.reason})")
        except Exception as e:
            print(f"[REC] ERROR al cerrar sesión: {e}")
        self.session = None
        return path

    def _after_close_cleanup(self) -> None:
        # Enforce quota
        try:
            self.quota.enforce(self.clip_dir)
        except Exception as e:
            print(f"[REC] ERROR en limpieza de cuota: {e}")
