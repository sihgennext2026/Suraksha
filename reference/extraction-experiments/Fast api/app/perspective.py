"""
perspective.py

Perspective correction from a detector box, not ground truth. Logic copied
unchanged from your step3_perspective_correction_from_detection(target).py
(the "v3" brightness-segmentation version) -- only the debug-image-saving
side effect is made optional so the API can skip it on production requests.
"""
from typing import Optional, Tuple

import cv2
import numpy as np

from . import config


def order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1).flatten()
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image: np.ndarray, pts: np.ndarray):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    max_width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    max_height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    max_width, max_height = max(max_width, 1), max(max_height, 1)
    dst = np.array([[0, 0], [max_width - 1, 0],
                     [max_width - 1, max_height - 1], [0, max_height - 1]], dtype=np.float32)
    transform_matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, transform_matrix, (max_width, max_height))
    return warped, rect


def find_document_quad_in_crop(crop_bgr: np.ndarray, debug_prefix: Optional[str] = None):
    """Brightness-based segmentation to find the document's 4 real corners
    inside a detector crop. See the original step3 script's docstring for
    the full v1->v3 reasoning; unchanged here."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    open_kernel = np.ones((25, 25), np.uint8)
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, open_kernel)
    close_kernel = np.ones((15, 15), np.uint8)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, close_kernel)

    if debug_prefix:
        cv2.imwrite(f"{debug_prefix}__threshold.jpg", closed)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    crop_area = crop_bgr.shape[0] * crop_bgr.shape[1]
    largest = max(contours, key=cv2.contourArea)
    largest_area = cv2.contourArea(largest)

    if largest_area < config.MIN_QUAD_AREA_RATIO * crop_area:
        return None
    if largest_area > config.MAX_QUAD_AREA_RATIO * crop_area:
        return None

    rect = cv2.minAreaRect(largest)
    quad = cv2.boxPoints(rect).astype(np.float32)
    h, w = crop_bgr.shape[:2]
    quad[:, 0] = np.clip(quad[:, 0], 0, w - 1)
    quad[:, 1] = np.clip(quad[:, 1], 0, h - 1)

    if debug_prefix:
        overlay = crop_bgr.copy()
        cv2.drawContours(overlay, [quad.astype(int)], -1, (0, 255, 0), 3)
        cv2.imwrite(f"{debug_prefix}__chosen_contour.jpg", overlay)

    return quad


def correct_from_detection(image_bgr: np.ndarray, box: Tuple[float, float, float, float, float],
                            debug_prefix: Optional[str] = None):
    """
    box = (x1, y1, x2, y2, conf) from the detector, NOT ground truth.
    Returns (output_image, mode_used, quad_or_None_in_original_image_coords).
    mode_used is one of: "cv_contour_warp", "fallback_axis_aligned_crop", "empty_crop".
    """
    x1, y1, x2, y2, conf = box
    h, w = image_bgr.shape[:2]
    bw, bh = x2 - x1, y2 - y1
    mx, my = bw * config.MARGIN_RATIO, bh * config.MARGIN_RATIO

    cx1, cy1 = int(max(0, x1 - mx)), int(max(0, y1 - my))
    cx2, cy2 = int(min(w, x2 + mx)), int(min(h, y2 + my))
    crop = image_bgr[cy1:cy2, cx1:cx2]

    if crop.size == 0:
        return None, "empty_crop", None

    quad_local = find_document_quad_in_crop(crop, debug_prefix=debug_prefix)
    if quad_local is None:
        return crop, "fallback_axis_aligned_crop", None

    warped, rect = four_point_transform(crop, quad_local)
    quad_global = rect + np.array([cx1, cy1], dtype=np.float32)
    return warped, "cv_contour_warp", quad_global
