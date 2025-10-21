from __future__ import annotations
from typing import List, Tuple
import cv2
import numpy as np

def preprocess_frame(frame, proc_width: int) -> tuple[np.ndarray, float, float]:
    """
    Reescala a proc_width y convierte a gris.
    Devuelve (gray, sx, sy) donde sx/sy son factores para mapear coords procesadas → original.
    """
    h0, w0 = frame.shape[:2]
    if proc_width <= 0 or proc_width >= w0:
        # Sin reescalar: útil si quieres procesar a resolución completa
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return gray, 1.0, 1.0

    ratio = proc_width / float(w0)
    resized = cv2.resize(frame, (proc_width, int(h0 * ratio)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    sx = w0 / float(resized.shape[1])
    sy = h0 / float(resized.shape[0])
    return gray, sx, sy

def diff_and_boxes(prev_gray: np.ndarray, gray: np.ndarray,
                   thresh: int, min_area: int, dilate_iters: int) -> List[Tuple[int, int, int, int]]:
    """Diferencia + blur + threshold + dilate → contornos → boxes (en coords del frame procesado)."""
    diff = cv2.absdiff(prev_gray, gray)
    blur = cv2.GaussianBlur(diff, (5, 5), 0)
    _, t = cv2.threshold(blur, thresh, 255, cv2.THRESH_BINARY)
    dil = cv2.dilate(t, None, iterations=max(0, dilate_iters))
    cnts, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: List[Tuple[int, int, int, int]] = []
    for c in cnts:
        if cv2.contourArea(c) < max(1, min_area):
            continue
        x, y, w, h = cv2.boundingRect(c)
        boxes.append((x, y, w, h))
    return boxes

def merge_boxes(boxes: List[Tuple[int, int, int, int]], padding: int = 15
               ) -> List[Tuple[int, int, int, int]]:
    """Fusiona cajas solapadas o cercanas (padding en coords del frame procesado)."""
    if len(boxes) <= 1:
        return boxes[:]
    work = boxes[:]
    changed = True
    while changed:
        changed = False
        used = [False] * len(work)
        nxt: List[Tuple[int, int, int, int]] = []
        for i in range(len(work)):
            if used[i]:
                continue
            x, y, w, h = work[i]
            base = (x, y, w, h)
            for j in range(i + 1, len(work)):
                if used[j]:
                    continue
                x2, y2, w2, h2 = work[j]
                if (x2 < x + w + padding and x2 + w2 + padding > x and
                    y2 < y + h + padding and y2 + h2 + padding > y):
                    nx1, ny1 = min(x, x2), min(y, y2)
                    nx2, ny2 = max(x + w, x2 + w2), max(y + h, y2 + h2)
                    base = (nx1, ny1, nx2 - nx1, ny2 - ny1)
                    x, y, w, h = base
                    used[j] = True
                    changed = True
            used[i] = True
            nxt.append(base)
        work = nxt
    return work
