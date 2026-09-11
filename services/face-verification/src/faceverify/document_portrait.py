from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .detector import SCRFDDetector, DetectedFace


@dataclass
class PortraitCandidate:
    face_index: int
    face_bbox: List[float]
    face_area: float
    confidence: float
    crop_bbox: Tuple[int, int, int, int]
    crop: np.ndarray


@dataclass
class PortraitExtractionResult:
    success: bool
    selected: Optional[PortraitCandidate]
    candidates: List[PortraitCandidate]
    reason: str


class DocumentPortraitExtractor:
    """
    Generic first-stage document portrait extractor.

    Strategy:
        Document image
            -> SCRFD detects all faces
            -> rank faces by detected face area
            -> select the largest face
            -> create a padded portrait crop

    Important:
        This module does NOT assume:
            - passport layout
            - voter ID layout
            - portrait position
            - document type
            - fixed coordinates

        The largest detected face is only a baseline heuristic.
        It must be evaluated against multiple document types.
    """

    def __init__(
        self,
        detector: SCRFDDetector,
        horizontal_padding: float = 2.50,
        vertical_padding: float = 3.00,
    ):
        self.detector = detector
        self.horizontal_padding = horizontal_padding
        self.vertical_padding = vertical_padding

    @staticmethod
    def _face_area(face: DetectedFace) -> float:
        x1, y1, x2, y2 = face.bbox

        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)

        return width * height

    def _make_crop(
        self,
        image: np.ndarray,
        face: DetectedFace,
    ) -> Tuple[int, int, int, int, np.ndarray]:

        image_height, image_width = image.shape[:2]

        x1, y1, x2, y2 = face.bbox

        face_width = x2 - x1
        face_height = y2 - y1

        # Expand around the detected face.
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        crop_width = face_width * self.horizontal_padding
        crop_height = face_height * self.vertical_padding

        crop_x1 = int(round(cx - crop_width / 2.0))
        crop_y1 = int(round(cy - crop_height / 2.0))
        crop_x2 = int(round(cx + crop_width / 2.0))
        crop_y2 = int(round(cy + crop_height / 2.0))

        # Keep crop inside document boundaries.
        crop_x1 = max(0, crop_x1)
        crop_y1 = max(0, crop_y1)
        crop_x2 = min(image_width, crop_x2)
        crop_y2 = min(image_height, crop_y2)

        crop = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()

        return (
            crop_x1,
            crop_y1,
            crop_x2,
            crop_y2,
            crop,
        )

    def extract(
        self,
        image_path: str,
    ) -> PortraitExtractionResult:

        image = cv2.imread(image_path)

        if image is None:
            return PortraitExtractionResult(
                success=False,
                selected=None,
                candidates=[],
                reason=f"Could not read image: {image_path}",
            )

        faces = self.detector.detect(image_path)

        if len(faces) == 0:
            return PortraitExtractionResult(
                success=False,
                selected=None,
                candidates=[],
                reason="No face detected in document.",
            )

        candidates: List[PortraitCandidate] = []

        for index, face in enumerate(faces):

            area = self._face_area(face)

            (
                crop_x1,
                crop_y1,
                crop_x2,
                crop_y2,
                crop,
            ) = self._make_crop(image, face)

            candidates.append(
                PortraitCandidate(
                    face_index=index,
                    face_bbox=face.bbox,
                    face_area=area,
                    confidence=face.confidence,
                    crop_bbox=(
                        crop_x1,
                        crop_y1,
                        crop_x2,
                        crop_y2,
                    ),
                    crop=crop,
                )
            )

        # Baseline selection rule:
        # largest detected face wins.
        candidates.sort(
            key=lambda candidate: candidate.face_area,
            reverse=True,
        )

        selected = candidates[0]

        return PortraitExtractionResult(
            success=True,
            selected=selected,
            candidates=candidates,
            reason="Largest detected face selected as primary portrait candidate.",
        )