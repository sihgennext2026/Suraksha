"""
detector.py

Wraps document_detector.onnx -- a U-Net/ResNet34 binary segmentation model
that outputs a per-pixel "is this the document" probability mask -- behind
a small class so the FastAPI app can load it once at startup and reuse it
for every request.

This REPLACES the previous YOLOv12s bounding-box detector. The key
difference: YOLO only gave a rectangular bounding box, so perspective.py
had to run a whole second round of classical-CV corner-finding /
text-line-deskew heuristics on the *crop* just to recover the document's
actual 4 corners for a proper perspective warp. The segmentation model
sidesteps that entirely -- its mask boundary IS the document's silhouette,
so we extract the 4 corners directly from the mask's largest contour and
hand those straight to perspective.four_point_transform.

Preprocessing/postprocessing (resize to model input size, sigmoid
activation, 0.5 threshold, morphological close+open, largest external
contour, epsilon-sweep polygon approximation with a minAreaRect fallback)
is copied unchanged from the verified prototype script (test.py /
step3_perspective_correction_from_detection(target).py), since that was
already checked against the model's real output shape (1, 1, 512, 512).
"""
from typing import NamedTuple, Optional

import cv2
import numpy as np
import onnxruntime as ort

from . import config
from .perspective import order_points


class Detection(NamedTuple):
    """Result of DocumentDetector.detect().

    quad        -- (4, 2) float32 array of document corners in ORIGINAL
                    image coordinates, ordered [top_left, top_right,
                    bottom_right, bottom_left].
    confidence  -- mean mask probability under the detected region, 0..1.
                    Not directly comparable to the old YOLO objectness
                    score, but serves the same purpose: a rough "how sure
                    was the model" signal.
    bbox        -- (x1, y1, x2, y2) axis-aligned box around the quad, kept
                    only so API responses / logging that expect a simple
                    bounding box still have something sensible to show.
    """
    quad: np.ndarray
    confidence: float
    bbox: tuple


def _get_document_corners(contour: np.ndarray, epsilon_min: float, epsilon_max: float,
                           epsilon_steps: int) -> np.ndarray:
    """Approximates a contour down to exactly 4 points, sweeping epsilon
    values (more robust than a single fixed epsilon). Falls back to
    cv2.minAreaRect() if no epsilon in the sweep lands on exactly 4
    points."""
    perimeter = cv2.arcLength(contour, True)
    for epsilon_factor in np.linspace(epsilon_min, epsilon_max, epsilon_steps):
        approx = cv2.approxPolyDP(contour, epsilon_factor * perimeter, True)
        if len(approx) == 4:
            return approx.reshape(4, 2).astype(np.float32)
    rect = cv2.minAreaRect(contour)
    return cv2.boxPoints(rect).astype(np.float32)


def _preprocess(image_bgr, input_size):
    resized = cv2.resize(image_bgr, (input_size, input_size), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    chw = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


class DocumentDetector:
    """Loads document_detector.onnx (U-Net segmentation) once; call
    .detect(image_bgr) per request."""

    def __init__(self, onnx_path=None, input_size=None, threshold=None):
        self.onnx_path = onnx_path or config.SEGMENTATION_ONNX_PATH
        self.input_size = input_size or config.SEGMENTATION_INPUT_SIZE
        self.threshold = threshold if threshold is not None else config.SEGMENTATION_THRESHOLD

        self.session = ort.InferenceSession(self.onnx_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

        k = config.SEGMENTATION_MORPH_KERNEL_SIZE
        self._morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    def detect(self, image_bgr) -> Optional[Detection]:
        """Runs the segmentation model and returns the document's 4
        corners in original-image coordinates, or None if no
        document-sized region was found."""
        orig_h, orig_w = image_bgr.shape[:2]
        input_tensor = _preprocess(image_bgr, self.input_size)
        raw_output = self.session.run(None, {self.input_name: input_tensor})[0]

        raw_mask = raw_output[0, 0]  # drop batch + channel dims -> (H, W)
        probability_mask = 1.0 / (1.0 + np.exp(-raw_mask))  # sigmoid: logits -> 0..1

        mask_bool = probability_mask > self.threshold
        binary_mask = (mask_bool.astype(np.uint8)) * 255
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, self._morph_kernel,
                                        iterations=config.SEGMENTATION_MORPH_CLOSE_ITERATIONS)
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, self._morph_kernel,
                                        iterations=config.SEGMENTATION_MORPH_OPEN_ITERATIONS)

        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest_contour = max(contours, key=cv2.contourArea)
        contour_area = cv2.contourArea(largest_contour)
        mask_area = self.input_size * self.input_size
        if contour_area < config.SEGMENTATION_MIN_CONTOUR_AREA_RATIO * mask_area:
            return None  # region too small to plausibly be the document

        corners_model_space = _get_document_corners(
            largest_contour,
            config.SEGMENTATION_CORNER_EPSILON_MIN,
            config.SEGMENTATION_CORNER_EPSILON_MAX,
            config.SEGMENTATION_CORNER_EPSILON_STEPS,
        )

        scale_x, scale_y = orig_w / self.input_size, orig_h / self.input_size
        corners_original = corners_model_space.copy()
        corners_original[:, 0] *= scale_x
        corners_original[:, 1] *= scale_y
        quad = order_points(corners_original)

        confidence = float(probability_mask[mask_bool].mean()) if mask_bool.any() else 0.0

        x1, y1 = float(quad[:, 0].min()), float(quad[:, 1].min())
        x2, y2 = float(quad[:, 0].max()), float(quad[:, 1].max())

        return Detection(quad=quad, confidence=confidence, bbox=(x1, y1, x2, y2))
