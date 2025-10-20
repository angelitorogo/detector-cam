# utilidades de ventana

from __future__ import annotations
import cv2

def create_window(title: str):
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)

def show_frame(title: str, frame, fps: float):
    cv2.imshow(title, frame)
    try:
        cv2.setWindowTitle(title, f"{title}  |  {fps:.1f} fps (ESC para salir)")
    except Exception:
        pass

def should_quit() -> bool:
    return (cv2.waitKey(1) & 0xFF) == 27  # ESC

def destroy_all():
    cv2.destroyAllWindows()
