"""
Stage 4: Basic face quality gate.

Purpose:
    Determine whether a detected face is suitable for the next stage.

Checks:
    1. Face size
    2. Brightness
    3. Blur/sharpness
    4. Approximate head pose

Important:
    These thresholds are engineering defaults, not biometric standards.
    They must be calibrated against representative data before production use.
"""

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np


@dataclass
class QualityResult:
    face_size_ok: bool
    brightness_ok: bool
    blur_ok: bool
    pose_ok: bool
    quality_ok: bool

    face_width: float
    face_height: float
    brightness: float
    blur_score: float

    yaw_proxy: Optional[float]
    roll: Optional[float]

def _face_dimensions(bbox: List[float]):
    x1, y1, x2, y2 = bbox

    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)

    return width, height


def _crop_face(image, bbox):
    image_height, image_width = image.shape[:2]

    x1, y1, x2, y2 = [int(round(v)) for v in bbox]

    x1 = max(0, min(x1, image_width - 1))
    y1 = max(0, min(y1, image_height - 1))
    x2 = max(0, min(x2, image_width))
    y2 = max(0, min(y2, image_height))

    if x2 <= x1 or y2 <= y1:
        return None

    return image[y1:y2, x1:x2]


def _brightness(face):
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


def _blur_score(face):
    """
    Variance of Laplacian.

    Higher generally means sharper local image structure.
    This is a relative image-quality measure, not a universal
    biometric blur standard.
    """
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _estimate_pose(face):
    """
    Estimate simple 2D pose indicators from SCRFD landmarks.

    This is intentionally NOT a full 3D head-pose estimator.

    Returns:
        yaw_proxy: horizontal nose displacement relative to eye midpoint.
        roll: eye-line angle in degrees.

    Pitch is not estimated here because five 2D landmarks with a
    generic 3D model are insufficient for a reliable pitch estimate.
    """

    left_eye = np.asarray(face.left_eye, dtype=np.float64)
    right_eye = np.asarray(face.right_eye, dtype=np.float64)
    nose = np.asarray(face.nose, dtype=np.float64)

    eye_vector = right_eye - left_eye
    eye_distance = float(np.linalg.norm(eye_vector))

    if eye_distance < 1e-6:
        return None, None

    eye_midpoint = (left_eye + right_eye) / 2.0

    # Horizontal displacement of the nose from the midpoint
    # between the eyes, normalized by inter-eye distance.
    yaw_proxy = float(
        (nose[0] - eye_midpoint[0]) / eye_distance
    )

    # Rotation of the eye line relative to horizontal.
    roll = float(
        np.degrees(
            np.arctan2(
                eye_vector[1],
                eye_vector[0],
            )
        )
    )

    return yaw_proxy, roll


def evaluate_quality(
    image,
    face,
    min_face_width=70.0,
    min_face_height=100.0,
    min_brightness=40.0,
    max_brightness=220.0,
    min_blur_score=15.0,
    max_yaw_proxy=0.20,
    max_roll=15.0,):
    """
    Evaluate one detected face.

    The default blur threshold of 15.0 is intentionally conservative
    for this initial laptop-camera calibration and should be revisited
    with a larger representative dataset.
    """

    face_width, face_height = _face_dimensions(face.bbox)

    face_size_ok = (
        face_width >= min_face_width
        and face_height >= min_face_height
    )

    face_crop = _crop_face(image, face.bbox)

    if face_crop is None or face_crop.size == 0:
        return QualityResult(
            face_size_ok=False,
            brightness_ok=False,
            blur_ok=False,
            pose_ok=False,
            quality_ok=False,
            face_width=face_width,
            face_height=face_height,
            brightness=0.0,
            blur_score=0.0,
            yaw_proxy=None,
	    roll=None,        )

    brightness = _brightness(face_crop)
    blur_score = _blur_score(face_crop)

    brightness_ok = (
        min_brightness <= brightness <= max_brightness
    )

    blur_ok = blur_score >= min_blur_score

    yaw_proxy, roll = _estimate_pose(face)

    pose_ok = (
    	yaw_proxy is not None
    	and roll is not None
    	and abs(yaw_proxy) <= max_yaw_proxy
    	and abs(roll) <= max_roll
    )
    quality_ok = (
        face_size_ok
        and brightness_ok
        and blur_ok
        and pose_ok
    )

    return QualityResult(
        face_size_ok=face_size_ok,
        brightness_ok=brightness_ok,
        blur_ok=blur_ok,
        pose_ok=pose_ok,
        quality_ok=quality_ok,
        face_width=face_width,
        face_height=face_height,
        brightness=brightness,
        blur_score=blur_score,
        yaw_proxy=yaw_proxy,
	roll=roll,    )