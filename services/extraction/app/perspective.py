"""
perspective.py

Perspective correction from the segmentation detector's quad, not ground
truth.

HISTORY: earlier versions of this file existed to compensate for the old
YOLO detector, which only produced a rectangular bounding box -- so this
module had to run its own classical-CV corner-finding (edge/brightness
quad detection, then a text-line-angle deskew fallback for cluttered
backgrounds where corner-finding failed) on the *crop* just to recover the
document's real 4 corners. That whole fallback chain is now unnecessary:
app/detector.py's U-Net segmentation model outputs a per-pixel document
mask, and its contour already IS the document's real boundary, corners
included. So correction here is just a single homography warp from that
quad -- see correct_from_quad() below.
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


def correct_from_quad(image_bgr: np.ndarray, quad: np.ndarray,
                       debug_prefix: Optional[str] = None):
    """
    quad = (4, 2) array of document corners in ORIGINAL image coordinates
    (from DocumentDetector.detect() -- a U-Net segmentation mask's
    contour, already the document's real corners, not a heuristic guess
    from a bounding box). Correction is therefore a single homography
    warp -- no crop-then-search-for-corners step needed.

    Returns (output_image, mode_used, quad_or_rect):
        "segmentation_quad_warp"     -- normal path; quad_or_rect is the
                                          ordered [tl, tr, br, bl] rect
                                          actually used for the warp, in
                                          original-image coordinates.
        "fallback_axis_aligned_crop" -- the quad was implausibly small
                                          relative to the full image (see
                                          config.MIN_QUAD_AREA_RATIO);
                                          falls back to the quad's own
                                          axis-aligned bounding box,
                                          uncorrected. quad_or_rect is
                                          None.
        "empty_crop"                 -- fallback crop was empty.
    """
    quad = np.asarray(quad, dtype=np.float32)
    h, w = image_bgr.shape[:2]

    area = cv2.contourArea(quad)
    if area < config.MIN_QUAD_AREA_RATIO * (w * h):
        x1 = max(0, int(quad[:, 0].min()))
        y1 = max(0, int(quad[:, 1].min()))
        x2 = min(w, int(quad[:, 0].max()))
        y2 = min(h, int(quad[:, 1].max()))
        crop = image_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None, "empty_crop", None
        if debug_prefix:
            cv2.imwrite(f"{debug_prefix}__fallback_crop.jpg", crop)
        return crop, "fallback_axis_aligned_crop", None

    warped, rect = four_point_transform(image_bgr, quad)

    if debug_prefix:
        overlay = image_bgr.copy()
        cv2.polylines(overlay, [quad.astype(np.int32)], True, (0, 255, 0), 3)
        cv2.imwrite(f"{debug_prefix}__quad.jpg", overlay)
        cv2.imwrite(f"{debug_prefix}__corrected.jpg", warped)

    return warped, "segmentation_quad_warp", rect
