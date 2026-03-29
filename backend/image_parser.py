"""OpenCV を用いた画像からの壁線自動検出モジュール (PoC)."""

from __future__ import annotations

import cv2
import numpy as np


def detect_walls_from_image(image_bytes: bytes) -> list[dict]:
    """画像バイト列から直線を検出し、壁の始点・終点リストを返す。

    太い線（壁の大枠）のみを残し、細い線（寸法線・文字）は
    モルフォロジー演算で除去する PoC 仕様。
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)

    edges = cv2.Canny(opened, 50, 150, apertureSize=3)

    min_dim = min(img.shape[:2])
    min_line_length = max(50, min_dim // 15)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=min_line_length,
        maxLineGap=10,
    )

    if lines is None:
        return []

    result: list[dict] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        result.append(
            {
                "start_point": {"x": float(x1), "y": float(y1)},
                "end_point": {"x": float(x2), "y": float(y2)},
            }
        )

    return result
