from __future__ import annotations

from typing import List, Optional

import cv2
import numpy as np
import segno

from . import config


def make_qr_array(
    payload: str,
    scale: int = config.DEFAULT_SCALE,
    border: int = config.DEFAULT_BORDER,
    fg: int = config.DEFAULT_COLOR_FG,
    bg: int = config.DEFAULT_COLOR_BG,
) -> np.ndarray:
    qr = segno.make(payload, error="h", micro=False)
    matrix = np.array(qr.matrix, dtype=np.uint8)
    matrix = np.pad(matrix, border, constant_values=0)
    arr = np.repeat(np.repeat(matrix, scale, axis=0), scale, axis=1)
    arr = np.where(arr > 0, fg, bg).astype(np.uint8)
    return arr


def compose_grid(
    qr_arrays: List[np.ndarray],
    rows: int,
    cols: int,
    gap: int = config.DEFAULT_GAP,
    bg: int = config.DEFAULT_COLOR_BG,
) -> np.ndarray:
    total_cells = rows * cols
    if len(qr_arrays) < total_cells:
        blank = np.full_like(qr_arrays[0], bg)
        qr_arrays = qr_arrays + [blank] * (total_cells - len(qr_arrays))
    elif len(qr_arrays) > total_cells:
        qr_arrays = qr_arrays[:total_cells]

    h, w = qr_arrays[0].shape[:2]
    canvas_h = rows * h + (rows - 1) * gap
    canvas_w = cols * w + (cols - 1) * gap
    canvas = np.full((canvas_h, canvas_w), bg, dtype=np.uint8)

    idx = 0
    for r in range(rows):
        for c in range(cols):
            y = r * (h + gap)
            x = c * (w + gap)
            canvas[y : y + h, x : x + w] = qr_arrays[idx]
            idx += 1
    return canvas


def overlay_text(
    image: np.ndarray,
    text: str,
    pos: tuple[int, int] = (10, 30),
    color: int = 128,
    scale: float = 0.7,
    thickness: int = 2,
) -> np.ndarray:
    """Overlay small status text on the composed image."""
    img = image.copy()
    cv2.putText(
        img,
        text,
        pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        int(color),
        thickness,
        lineType=cv2.LINE_AA,
    )
    return img
