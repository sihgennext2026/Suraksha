"""
qr_barcode.py

QR code and barcode detection -> location -> cropping module. This is a
LEAF of the pipeline -- it receives the same perspective-corrected image
that the OCR branch receives (no separate correction, no extra model
loading) and produces:

    - detected / not-detected booleans per code type
    - cropped images saved to disk
    - JSON-serializable metadata (type, crop path, position)

It does NOT decode, validate, or OCR the content of any detected code.
Successful decoding is not required for detection or cropping -- a QR
that OpenCV can locate but cannot decode is still saved. A teammate
module will process the crop images downstream.

Detection strategy (hybrid, fast):

    PRIMARY: ZXing-C++ (zxingcpp) -- fast (~tens of ms), supports QR
             codes AND all common 1D barcode formats in one call.

    FALLBACK: OpenCV's QRCodeDetector -- used ONLY when ZXing finds no
              QR code, because OpenCV can sometimes locate QR codes that
              ZXing misses (damaged/partial codes). OpenCV cannot detect
              barcodes, so barcodes are ZXing-only.

Cropping:
    - QR codes detected with 4-point corners (OpenCV fallback) get a
      perspective-corrected crop, not just an axis-aligned bounding box.
    - ZXing-detected codes use the returned position geometry.
    - A configurable margin is added around every crop.
"""
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from . import config

try:
    import zxingcpp
    _ZXING_AVAILABLE = True
except ImportError:
    _ZXING_AVAILABLE = False

_QR_FORMATS = {
    "QRCode", "QR Code", "MicroQRCode", "Micro QR Code",
    "RMQRCode", "rMQR Code", "QRCodeModel1", "QR Code Model 1",
    "QRCodeModel2", "QR Code Model 2",
}

_BARCODE_FORMATS = {
    "Codabar", "Code128", "Code39", "Code93", "DataBar", "DataBarExp",
    "DataBarExpStk", "DataBarLtd", "DataBarOmni", "DataBarStk",
    "DataBarStkOmni", "EAN13", "EAN8", "ITF", "PDF417", "MicroPDF417",
    "UPCA", "UPCE",
}


@dataclass
class CodeDetection:
    code_type: str          # "qr" or "barcode"
    format_name: str        # e.g. "QRCode", "Code128", "EAN13"
    position: Optional[List[List[float]]]  # corner points [[x,y], ...]
    crop_path: Optional[str] = None
    decoded_text: Optional[str] = None     # kept for debug/testing only
    detection_method: str = "zxing"        # "zxing" or "opencv_fallback"


@dataclass
class QRBarcodeResult:
    side: str                  # "front" or "back"
    qr_code: bool = False
    bar_code: bool = False
    qr_crops: List[str] = field(default_factory=list)
    barcode_crops: List[str] = field(default_factory=list)
    detections: List[CodeDetection] = field(default_factory=list)
    detection_ms: float = 0.0


def _expand_box(pts: np.ndarray, margin: int, img_h: int, img_w: int) -> Tuple[int, int, int, int]:
    x_min = max(0, int(pts[:, 0].min()) - margin)
    y_min = max(0, int(pts[:, 1].min()) - margin)
    x_max = min(img_w, int(pts[:, 0].max()) + margin)
    y_max = min(img_h, int(pts[:, 1].max()) + margin)
    return x_min, y_min, x_max, y_max


def _perspective_crop_qr(image: np.ndarray, corners: np.ndarray, margin: int) -> np.ndarray:
    """Perspective-corrects a QR region using its 4 corner points, producing
    a clean square crop even when the QR is photographed at an angle.
    Falls back to axis-aligned crop when corners are degenerate."""
    h, w = image.shape[:2]
    corners = corners.astype(np.float32)
    if len(corners) != 4:
        x1, y1, x2, y2 = _expand_box(corners, margin, h, w)
        return image[y1:y2, x1:x2]

    s = corners.sum(axis=1)
    diff = np.diff(corners, axis=1).flatten()
    indices = [np.argmin(s), np.argmin(diff), np.argmax(s), np.argmax(diff)]
    if len(set(indices)) < 4:
        x1, y1, x2, y2 = _expand_box(corners, margin, h, w)
        return image[y1:y2, x1:x2]

    rect = np.zeros((4, 2), dtype=np.float32)
    rect[0] = corners[indices[0]]   # top-left
    rect[1] = corners[indices[1]]   # top-right
    rect[2] = corners[indices[2]]   # bottom-right
    rect[3] = corners[indices[3]]   # bottom-left

    for i in range(4):
        for j in range(i + 1, 4):
            if np.linalg.norm(rect[i] - rect[j]) < 10:
                x1, y1, x2, y2 = _expand_box(corners, margin, h, w)
                return image[y1:y2, x1:x2]

    w1 = np.linalg.norm(rect[1] - rect[0])
    w2 = np.linalg.norm(rect[2] - rect[3])
    h1 = np.linalg.norm(rect[3] - rect[0])
    h2 = np.linalg.norm(rect[2] - rect[1])
    side = int(max(w1, w2, h1, h2)) + 2 * margin
    side = max(side, 1)

    dst = np.array([
        [margin, margin],
        [side - margin - 1, margin],
        [side - margin - 1, side - margin - 1],
        [margin, side - margin - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (side, side))
    return warped


def _axis_aligned_crop(image: np.ndarray, pts: np.ndarray, margin: int) -> np.ndarray:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = _expand_box(pts, margin, h, w)
    return image[y1:y2, x1:x2]


def _zxing_position_to_points(pos) -> np.ndarray:
    """Extracts corner points from a zxingcpp Position object."""
    points = []
    for attr in ['top_left', 'top_right', 'bottom_right', 'bottom_left']:
        pt = getattr(pos, attr, None)
        if pt is not None:
            points.append([float(pt.x), float(pt.y)])
    if not points:
        return np.array([], dtype=np.float32)
    return np.array(points, dtype=np.float32)


def _classify_format(fmt_name: str) -> str:
    if fmt_name in _QR_FORMATS:
        return "qr"
    return "barcode"


def _detect_zxing(image_bgr: np.ndarray) -> List[CodeDetection]:
    if not _ZXING_AVAILABLE:
        return []

    candidates = [image_bgr]
    if len(image_bgr.shape) == 3:
        candidates.append(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY))

    for img in candidates:
        try:
            results = zxingcpp.read_barcodes(img)
        except Exception:
            continue
        if not results:
            continue

        detections = []
        for r in results:
            fmt_name = str(r.format).split(".")[-1] if hasattr(r, 'format') else "Unknown"
            pts = _zxing_position_to_points(r.position) if hasattr(r, 'position') else np.array([])
            code_type = _classify_format(fmt_name)
            detections.append(CodeDetection(
                code_type=code_type,
                format_name=fmt_name,
                position=pts.tolist() if pts.size > 0 else None,
                decoded_text=str(r.text) if r.text else None,
                detection_method="zxing",
            ))
        return detections
    return []


def _detect_opencv_qr(image_bgr: np.ndarray) -> List[CodeDetection]:
    """OpenCV QR fallback -- only for QR codes (OpenCV has no general
    barcode detector). Returns detections even when decoding fails, as long
    as the QR is located. Tries multiple preprocessing variants (matching
    the standalone qrbar.py approach) for robustness on real-world photos."""
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    detector = cv2.QRCodeDetector()

    upscale = 2.0
    enlarged = cv2.resize(gray, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5)

    attempts = [
        ("original", image_bgr, 1.0),
        ("grayscale", gray, 1.0),
        ("upscaled", enlarged, upscale),
        ("adaptive", adaptive, 1.0),
    ]

    for method_name, candidate, scale in attempts:
        try:
            data, points, _ = detector.detectAndDecode(candidate)
        except Exception:
            data, points = None, None

        if points is not None and len(points) > 0:
            pts = points.reshape(-1, 2).astype(np.float32)
            if scale > 1.0:
                pts = pts / scale
            return [CodeDetection(
                code_type="qr",
                format_name="QRCode",
                position=pts.tolist(),
                decoded_text=data if data else None,
                detection_method="opencv_fallback",
            )]

        try:
            retval, decoded_info, pts_arr, _ = detector.detectAndDecodeMulti(candidate)
        except Exception:
            retval = False
            pts_arr = None
            decoded_info = None

        if retval and pts_arr is not None and len(pts_arr) > 0:
            detections = []
            for i in range(len(pts_arr)):
                pts = pts_arr[i].reshape(-1, 2).astype(np.float32)
                if scale > 1.0:
                    pts = pts / scale
                decoded = decoded_info[i] if decoded_info is not None and i < len(decoded_info) else None
                detections.append(CodeDetection(
                    code_type="qr",
                    format_name="QRCode",
                    position=pts.tolist(),
                    decoded_text=decoded if decoded else None,
                    detection_method="opencv_fallback",
                ))
            return detections

        try:
            found, raw_pts = detector.detect(candidate)
            if found and raw_pts is not None:
                pts = raw_pts.reshape(-1, 2).astype(np.float32)
                if scale > 1.0:
                    pts = pts / scale
                return [CodeDetection(
                    code_type="qr",
                    format_name="QRCode",
                    position=pts.tolist(),
                    decoded_text=None,
                    detection_method="opencv_fallback",
                )]
        except Exception:
            pass

    return []


def _local_division(channel: np.ndarray, kernel_size: int) -> np.ndarray:
    """Divides each pixel by its Gaussian-blurred local mean, normalizing
    uneven illumination so faint QR modules stand out."""
    local_mean = cv2.GaussianBlur(channel.astype(np.float32),
                                  (kernel_size, kernel_size), 0)
    local_mean[local_mean < 1] = 1
    return (channel.astype(np.float32) / local_mean * 128).clip(0, 255).astype(np.uint8)


def _enhance_for_qr(gray: np.ndarray) -> list:
    """Build multiple enhanced image variants for robust QR detection."""
    variants = []
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    variants.append(clahe.apply(gray))
    clahe_strong = cv2.createCLAHE(clipLimit=6.0, tileGridSize=(4, 4))
    variants.append(clahe_strong.apply(gray))
    kernel_sharp = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(gray, -1, kernel_sharp)
    variants.append(clahe.apply(sharpened))
    for bs in (51, 31):
        variants.append(cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, bs, 10))
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)
    for ks in (51, 131):
        variants.append(_local_division(gray, ks))
    return variants


def _validate_qr_quad(pts: np.ndarray, img_h: int, img_w: int) -> bool:
    """Check if 4 points form a plausible QR code quadrilateral."""
    if len(pts) != 4:
        return False
    area = cv2.contourArea(pts)
    img_area = img_h * img_w
    if area < img_area * 0.002 or area > img_area * 0.85:
        return False
    for p in pts:
        if p[0] < -10 or p[1] < -10 or p[0] > img_w + 10 or p[1] > img_h + 10:
            return False
    sides = [np.linalg.norm(pts[(i + 1) % 4] - pts[i]) for i in range(4)]
    if min(sides) < 5:
        return False
    if max(sides) / min(sides) > 3.5:
        return False
    _, _, bw, bh = cv2.boundingRect(pts)
    if max(bw, bh) / max(min(bw, bh), 1) > 3.0:
        return False
    return True


def _find_qr_by_finder_patterns(gray: np.ndarray, img_h: int, img_w: int) -> Optional[np.ndarray]:
    """Locate QR code by finding its 3 finder patterns (nested square contours)."""
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    for block_size in (51, 31, 71):
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, block_size, 10)
        contours, hierarchy = cv2.findContours(
            binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None or len(contours) == 0:
            continue
        hierarchy = hierarchy[0]
        candidates = []
        for i in range(len(contours)):
            child = hierarchy[i][2]
            if child < 0:
                continue
            if hierarchy[child][2] < 0:
                continue
            cnt = contours[i]
            area = cv2.contourArea(cnt)
            if area < img_h * img_w * 0.001 or area > img_h * img_w * 0.08:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if min(bw, bh) < 5 or max(bw, bh) / min(bw, bh) > 1.8:
                continue
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                candidates.append((cx, cy, area, cnt))
        if len(candidates) < 3:
            continue
        candidates.sort(key=lambda x: x[2], reverse=True)
        for start in range(min(len(candidates) - 2, 5)):
            ref_area = candidates[start][2]
            group = [candidates[start]]
            for j in range(start + 1, len(candidates)):
                if 0.2 < candidates[j][2] / ref_area < 5.0:
                    group.append(candidates[j])
                if len(group) == 3:
                    break
            if len(group) < 3:
                continue
            all_pts = np.vstack(
                [g[3].reshape(-1, 2) for g in group]).astype(np.float32)
            x, y, bw, bh = cv2.boundingRect(all_pts)
            expand = int(max(bw, bh) * 0.15)
            pts = np.array([
                [max(0, x - expand), max(0, y - expand)],
                [min(img_w, x + bw + expand), max(0, y - expand)],
                [min(img_w, x + bw + expand), min(img_h, y + bh + expand)],
                [max(0, x - expand), min(img_h, y + bh + expand)],
            ], dtype=np.float32)
            if _validate_qr_quad(pts, img_h, img_w):
                return pts
    return None


def _detect_zxing_enhanced(image_bgr: np.ndarray) -> List[CodeDetection]:
    """Try ZXing on contrast-enhanced image variants."""
    if not _ZXING_AVAILABLE:
        return []
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    clahe_strong = cv2.createCLAHE(clipLimit=6.0, tileGridSize=(4, 4))

    variants = [
        image_bgr,
        clahe.apply(gray),
        clahe_strong.apply(gray),
        cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10),
    ]
    if len(image_bgr.shape) == 3:
        variants.append(clahe.apply(image_bgr[:, :, 0]))

    for enhanced in variants:
        eh, ew = enhanced.shape[:2]
        for scale in (1, 2):
            img = cv2.resize(enhanced, (ew * scale, eh * scale),
                             interpolation=cv2.INTER_CUBIC) if scale > 1 else enhanced
            try:
                results = zxingcpp.read_barcodes(img)
            except Exception:
                continue
            if not results:
                continue
            detections = []
            for r in results:
                fmt_name = str(r.format).split(".")[-1] if hasattr(r, 'format') else "Unknown"
                pts = _zxing_position_to_points(r.position) if hasattr(r, 'position') else np.array([])
                if scale > 1 and pts.size > 0:
                    pts = pts / scale
                code_type = _classify_format(fmt_name)
                detections.append(CodeDetection(
                    code_type=code_type, format_name=fmt_name,
                    position=pts.tolist() if pts.size > 0 else None,
                    decoded_text=str(r.text) if r.text else None,
                    detection_method="zxing_enhanced",
                ))
            return detections
    return []


def _verify_qr_crop(crop: np.ndarray) -> bool:
    """Reject false positives (photos, text) by checking QR-specific patterns."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    h, w = gray.shape[:2]
    if h < 15 or w < 15:
        return False

    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.count_nonzero(edges) / (h * w)

    if edge_density > 0.08:
        return True

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    densities = []
    for frac in (0.25, 0.5, 0.75):
        row = binary[int(h * frac), :]
        densities.append(np.sum(np.abs(np.diff(row.astype(np.int16))) > 127) / w)
        col = binary[:, int(w * frac)]
        densities.append(np.sum(np.abs(np.diff(col.astype(np.int16))) > 127) / h)
    median_td = float(np.median(densities))

    if median_td < 0.08 and edge_density < 0.05:
        return False
    return True


def _refine_qr_crop(crop: np.ndarray, pad: int = 8) -> np.ndarray:
    """Tighten a QR crop by finding the dense module pattern via local variance."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop.copy()
    h, w = gray.shape[:2]
    if h < 30 or w < 30:
        return crop

    ks = 15
    mean = cv2.blur(gray.astype(np.float32), (ks, ks))
    sq_mean = cv2.blur(gray.astype(np.float32) ** 2, (ks, ks))
    std = np.sqrt(np.maximum(sq_mean - mean ** 2, 0))

    _, mask = cv2.threshold(std.astype(np.uint8), 15, 255, cv2.THRESH_BINARY)
    kern = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kern, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kern, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_area = None, 0
    for cnt in contours:
        a = cv2.contourArea(cnt)
        if a < h * w * 0.1:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        if max(bw, bh) / max(min(bw, bh), 1) > 2.0:
            continue
        if a > best_area:
            best_area = a
            best = (x, y, bw, bh)

    if best is None:
        return crop
    x, y, bw, bh = best
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
    return crop[y1:y2, x1:x2]


def _enhance_crop(crop: np.ndarray) -> np.ndarray:
    """Apply contrast enhancement to make QR modules clearly visible."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop.copy()
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)


def _detect_low_contrast_qr(image_bgr: np.ndarray) -> List[CodeDetection]:
    """Robust fallback for QR codes missed by primary detectors.

    Uses multiple preprocessing strategies (CLAHE, adaptive threshold,
    local division), validates candidates to reject false positives,
    and falls back to contour-based finder pattern detection."""
    h, w = image_bgr.shape[:2] if len(image_bgr.shape) == 3 else image_bgr.shape
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    detector = cv2.QRCodeDetector()

    channels = [gray]
    if len(image_bgr.shape) == 3:
        channels.append(image_bgr[:, :, 0])

    best = None
    best_score = 0

    for ch in channels:
        variants = _enhance_for_qr(ch)
        for enhanced in variants:
            for scale in (2, 3):
                up = cv2.resize(enhanced, (w * scale, h * scale),
                                interpolation=cv2.INTER_CUBIC)
                try:
                    ok, infos, pts_arr, _ = detector.detectAndDecodeMulti(up)
                    if ok and pts_arr is not None:
                        for i in range(len(pts_arr)):
                            pts = pts_arr[i].reshape(-1, 2).astype(np.float32) / scale
                            if not _validate_qr_quad(pts, h, w):
                                continue
                            decoded = infos[i] if infos and i < len(infos) and infos[i] else None
                            area_ratio = cv2.contourArea(pts) / (h * w)
                            area_bonus = min(area_ratio * 300, 30)
                            sc = (100 if decoded else 50) + area_bonus
                            if sc > best_score:
                                best_score = sc
                                best = (pts, decoded)
                            if decoded:
                                return [CodeDetection(
                                    code_type="qr", format_name="QRCode",
                                    position=pts.tolist(), decoded_text=decoded,
                                    detection_method="opencv_enhanced",
                                )]
                except Exception:
                    pass
                try:
                    found, raw_pts = detector.detect(up)
                    if found and raw_pts is not None:
                        pts = raw_pts.reshape(-1, 2).astype(np.float32) / scale
                        if not _validate_qr_quad(pts, h, w):
                            continue
                        area_ratio = cv2.contourArea(pts) / (h * w)
                        sc = 40 + min(area_ratio * 300, 30)
                        if sc > best_score:
                            best_score = sc
                            best = (pts, None)
                except Exception:
                    pass

    if best is None:
        contour_pts = _find_qr_by_finder_patterns(gray, h, w)
        if contour_pts is not None:
            best = (contour_pts, None)

    if best is None:
        return []

    pts, decoded = best
    return [CodeDetection(
        code_type="qr", format_name="QRCode",
        position=pts.tolist(), decoded_text=decoded,
        detection_method="opencv_enhanced",
    )]


def detect_and_crop(
    image_bgr: np.ndarray,
    side: str,
    output_dir: str,
    margin: int = None,
) -> QRBarcodeResult:
    """Main entry point. Detects all QR codes and barcodes in the given
    perspective-corrected image, crops each, saves to output_dir, and
    returns structured metadata.

    This function is safe to call from a thread (no global mutable state,
    no model loading -- ZXing and OpenCV detectors are stateless)."""
    if margin is None:
        margin = config.QR_BARCODE_CROP_MARGIN

    t0 = time.perf_counter()

    zxing_detections = _detect_zxing(image_bgr)

    has_zxing_qr = any(d.code_type == "qr" for d in zxing_detections)
    opencv_detections = []
    if not has_zxing_qr:
        opencv_detections = _detect_opencv_qr(image_bgr)

    all_detections = zxing_detections + opencv_detections

    if not all_detections:
        all_detections = _detect_zxing_enhanced(image_bgr)

    if not all_detections:
        all_detections = _detect_low_contrast_qr(image_bgr)

    detection_ms = (time.perf_counter() - t0) * 1000.0

    if not all_detections:
        return QRBarcodeResult(
            side=side,
            qr_code=False,
            bar_code=False,
            detection_ms=detection_ms,
        )

    os.makedirs(output_dir, exist_ok=True)

    qr_crops = []
    barcode_crops = []
    qr_idx = 0
    barcode_idx = 0
    h, w = image_bgr.shape[:2]

    for det in all_detections:
        if det.position is None or len(det.position) == 0:
            continue

        pts = np.array(det.position, dtype=np.float32)

        use_perspective = (det.code_type == "qr" and len(pts) == 4)
        if use_perspective:
            crop = _perspective_crop_qr(image_bgr, pts, margin)
        else:
            crop = _axis_aligned_crop(image_bgr, pts, margin)

        if crop.size == 0:
            continue

        if det.detection_method == "opencv_enhanced":
            crop = _refine_qr_crop(crop)
            crop = _enhance_crop(crop)

        if det.code_type == "qr" and det.decoded_text is None:
            if not _verify_qr_crop(crop):
                continue

        if det.code_type == "qr":
            qr_idx += 1
            filename = f"qr_{qr_idx}.png"
        else:
            barcode_idx += 1
            filename = f"barcode_{barcode_idx}.png"

        filepath = os.path.join(output_dir, filename)
        cv2.imwrite(filepath, crop)
        det.crop_path = filepath

        if det.code_type == "qr":
            qr_crops.append(filepath)
        else:
            barcode_crops.append(filepath)

    return QRBarcodeResult(
        side=side,
        qr_code=len(qr_crops) > 0,
        bar_code=len(barcode_crops) > 0,
        qr_crops=qr_crops,
        barcode_crops=barcode_crops,
        detections=all_detections,
        detection_ms=detection_ms,
    )


def result_to_json(result: QRBarcodeResult) -> dict:
    """Converts a QRBarcodeResult to the JSON metadata dict saved alongside
    crop images. Keeps backward compatibility with the single-crop schema
    while supporting multiple detections."""
    out = {
        "side": result.side,
        "qr_code": result.qr_code,
        "bar_code": result.bar_code,
        "qr_crop": result.qr_crops[0] if result.qr_crops else None,
        "barcode_crop": result.barcode_crops[0] if result.barcode_crops else None,
        "detection_ms": round(result.detection_ms, 1),
    }
    if len(result.qr_crops) > 1:
        out["qr_crops"] = result.qr_crops
    if len(result.barcode_crops) > 1:
        out["barcode_crops"] = result.barcode_crops
    if result.detections:
        out["detections"] = [
            {
                "code_type": d.code_type,
                "format": d.format_name,
                "crop_path": d.crop_path,
                "detection_method": d.detection_method,
            }
            for d in result.detections
        ]
    return out
