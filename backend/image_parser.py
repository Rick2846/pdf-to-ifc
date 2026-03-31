"""CubiCasa5K ベースの壁線検出モジュール (PoC).

セマンティックセグメンテーションで壁領域を推定し、
スケルトン化 → HoughLinesP で線分にベクトル化して返す。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2
import numpy as np
import torch
from skimage.morphology import skeletonize

if TYPE_CHECKING:
    from models.hg_furukawa import HGFurukawa

logger = logging.getLogger(__name__)

CUBICASA_INPUT_SIZE = 256
ROOM_CH_START = 21
ROOM_CH_END = 33
WALL_CLASS = 2

SNAP_TOLERANCE_DEG = 5.0
MERGE_PERP_DIST = 10
MERGE_PARA_GAP = 20


def _preprocess(bgr: np.ndarray) -> tuple[torch.Tensor, tuple[int, int]]:
    """BGR 画像を CubiCasa5K 推論用テンソルに変換する。

    Returns:
        (tensor [1,3,256,256], (orig_h, orig_w))
    """
    orig_h, orig_w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (CUBICASA_INPUT_SIZE, CUBICASA_INPUT_SIZE))

    img = resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img = (img - mean) / std

    tensor = torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0)
    return tensor, (orig_h, orig_w)


def _extract_wall_mask(output: torch.Tensor) -> np.ndarray:
    """モデル出力から壁クラスの 2 値マスクを取り出す (uint8, 0/255)。"""
    room_logits = output[0, ROOM_CH_START:ROOM_CH_END]
    room_pred = room_logits.argmax(dim=0).cpu().numpy()
    wall_mask = (room_pred == WALL_CLASS).astype(np.uint8) * 255
    return wall_mask


# ── Feature 1: 高解像度化 ──────────────────────────────────


def _vectorize(mask: np.ndarray, orig_size: tuple[int, int]) -> list[dict]:
    """256x256 マスクをスケルトン化 → HoughLinesP → スケールバック → スナップ → マージ。"""
    orig_h, orig_w = orig_size

    skeleton = skeletonize(mask > 0).astype(np.uint8) * 255

    min_dim = min(mask.shape[:2])
    min_line_length = max(5, min_dim // 20)

    lines = cv2.HoughLinesP(
        skeleton,
        rho=1,
        theta=np.pi / 180,
        threshold=15,
        minLineLength=min_line_length,
        maxLineGap=8,
    )
    if lines is None:
        return []

    scale_x = orig_w / CUBICASA_INPUT_SIZE
    scale_y = orig_h / CUBICASA_INPUT_SIZE

    raw: list[tuple[int, int, int, int]] = []
    for ln in lines:
        x1, y1, x2, y2 = ln[0]
        raw.append((
            int(x1 * scale_x), int(y1 * scale_y),
            int(x2 * scale_x), int(y2 * scale_y),
        ))

    snapped = _snap_lines(raw)
    merged = _merge_lines(snapped)

    result: list[dict] = []
    for x1, y1, x2, y2 in merged:
        result.append(
            {
                "start_point": {"x": float(x1), "y": float(y1)},
                "end_point": {"x": float(x2), "y": float(y2)},
            }
        )
    return result


# ── Feature 2: 水平・垂直スナップ ──────────────────────────


def _snap_lines(
    lines: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    """±SNAP_TOLERANCE_DEG 以内の線分を水平/垂直にスナップし、斜め線は破棄する。"""
    tol = SNAP_TOLERANCE_DEG
    result: list[tuple[int, int, int, int]] = []

    for x1, y1, x2, y2 in lines:
        angle = np.degrees(np.arctan2(abs(y2 - y1), abs(x2 - x1)))

        if angle <= tol:
            mid_y = (y1 + y2) // 2
            result.append((x1, mid_y, x2, mid_y))
        elif angle >= 90 - tol:
            mid_x = (x1 + x2) // 2
            result.append((mid_x, y1, mid_x, y2))
        # else: 斜め線 → 破棄

    return result


# ── Feature 3: 近接線分マージ ──────────────────────────────


def _merge_lines(
    lines: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    """同方向・近接・重複する線分を繰り返し統合する。"""
    h_lines: list[tuple[int, int, int, int]] = []
    v_lines: list[tuple[int, int, int, int]] = []

    for x1, y1, x2, y2 in lines:
        if y1 == y2:
            lx, rx = (x1, x2) if x1 <= x2 else (x2, x1)
            h_lines.append((lx, y1, rx, y2))
        else:
            ty, by = (y1, y2) if y1 <= y2 else (y2, y1)
            tx = x1 if y1 <= y2 else x2
            v_lines.append((tx, ty, tx, by))

    h_lines = _merge_group(h_lines, axis="h")
    v_lines = _merge_group(v_lines, axis="v")

    return h_lines + v_lines


def _merge_group(
    lines: list[tuple[int, int, int, int]],
    axis: str,
) -> list[tuple[int, int, int, int]]:
    """同一軸グループの線分を統合できなくなるまで繰り返す。"""
    changed = True
    while changed:
        changed = False
        merged: list[tuple[int, int, int, int]] = []
        used = [False] * len(lines)

        for i in range(len(lines)):
            if used[i]:
                continue
            cur = lines[i]
            for j in range(i + 1, len(lines)):
                if used[j]:
                    continue
                m = _try_merge(cur, lines[j], axis)
                if m is not None:
                    cur = m
                    used[j] = True
                    changed = True
            merged.append(cur)
            used[i] = True

        lines = merged

    return lines


def _try_merge(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
    axis: str,
) -> tuple[int, int, int, int] | None:
    """2 線分が統合可能なら統合後の線分を返す。不可なら None。"""
    if axis == "h":
        if abs(a[1] - b[1]) > MERGE_PERP_DIST:
            return None
        a_min, a_max = min(a[0], a[2]), max(a[0], a[2])
        b_min, b_max = min(b[0], b[2]), max(b[0], b[2])
        if a_min > b_max + MERGE_PARA_GAP or b_min > a_max + MERGE_PARA_GAP:
            return None
        new_y = (a[1] + b[1]) // 2
        return (min(a_min, b_min), new_y, max(a_max, b_max), new_y)

    # axis == "v"
    if abs(a[0] - b[0]) > MERGE_PERP_DIST:
        return None
    a_min, a_max = min(a[1], a[3]), max(a[1], a[3])
    b_min, b_max = min(b[1], b[3]), max(b[1], b[3])
    if a_min > b_max + MERGE_PARA_GAP or b_min > a_max + MERGE_PARA_GAP:
        return None
    new_x = (a[0] + b[0]) // 2
    return (new_x, min(a_min, b_min), new_x, max(a_max, b_max))


def detect_walls_from_bgr(
    bgr: np.ndarray,
    model: HGFurukawa | None = None,
) -> list[dict]:
    """BGR 画像から壁の線分を検出して返す。

    *model* が渡された場合は CubiCasa5K 推論を使用し、
    ``None`` の場合は従来の Canny + HoughLinesP にフォールバックする。
    """
    if bgr is None or bgr.size == 0:
        return []

    if model is None:
        return _fallback_detect(bgr)

    tensor, orig_size = _preprocess(bgr)
    device = next(model.parameters()).device
    tensor = tensor.to(device)

    with torch.no_grad():
        output = model(tensor)

    wall_mask = _extract_wall_mask(output)
    walls = _vectorize(wall_mask, orig_size)
    logger.info("CubiCasa5K: detected %d wall segments", len(walls))
    return walls


def _fallback_detect(bgr: np.ndarray) -> list[dict]:
    """OpenCV ルールベースのフォールバック検出（モデル未ロード時用）。"""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    min_dim = min(bgr.shape[:2])
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
