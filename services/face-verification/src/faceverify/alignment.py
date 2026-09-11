"""
Stage 5: Five-point face alignment for ArcFace.

Input:
    Original BGR image
    DetectedFace containing five SCRFD landmarks

Output:
    112x112 aligned face suitable for ArcFace preprocessing.

This module performs geometric alignment only.
It does not perform face detection, quality assessment,
recognition, similarity calculation, or decision making.
"""

from typing import Tuple

import cv2
import numpy as np


# Standard ArcFace 112x112 five-point reference landmarks.
#
# Order:
#   left eye
#   right eye
#   nose
#   left mouth
#   right mouth
#
# Coordinates are expressed in the 112x112 output image.
ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def _get_landmarks(face) -> np.ndarray:
    """
    Extract SCRFD landmarks in ArcFace template order.

    Returns:
        Shape (5, 2):
        [left_eye, right_eye, nose, left_mouth, right_mouth]
    """

    return np.array(
        [
            face.left_eye,
            face.right_eye,
            face.nose,
            face.left_mouth,
            face.right_mouth,
        ],
        dtype=np.float32,
    )


def align_face(
    image: np.ndarray,
    face,
    output_size: Tuple[int, int] = (112, 112),
) -> np.ndarray:
    """
    Align one detected face using its five SCRFD landmarks.

    Args:
        image:
            Original BGR image.

        face:
            DetectedFace returned by SCRFDDetector.detect().

        output_size:
            Output size as (width, height).

    Returns:
        Aligned BGR face image.

    Raises:
        ValueError:
            If the image or landmarks are invalid.
    """

    if image is None or image.size == 0:
        raise ValueError("Input image is empty.")

    if output_size != (112, 112):
        raise ValueError(
            "ArcFace alignment currently expects output_size=(112, 112)."
        )

    source_points = _get_landmarks(face)

    if source_points.shape != (5, 2):
        raise ValueError(
            f"Expected five 2D landmarks, got shape {source_points.shape}."
        )

    if not np.isfinite(source_points).all():
        raise ValueError("Landmarks contain invalid numeric values.")

    # Estimate similarity transformation from detected landmarks
    # to the canonical ArcFace landmark template.
    transform, _ = cv2.estimateAffinePartial2D(
        source_points,
        ARCFACE_TEMPLATE,
        method=cv2.LMEDS,
    )

    if transform is None:
        raise ValueError("Could not estimate face alignment transform.")

    aligned = cv2.warpAffine(
        image,
        transform,
        output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )

    return aligned