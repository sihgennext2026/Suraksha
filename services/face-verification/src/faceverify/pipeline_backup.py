"""
Reusable end-to-end face verification pipeline.

Pipeline:
    Image
      -> Face Detection
      -> Face Quality
      -> Five-point Alignment
      -> ArcFace R50 Embedding
      -> Cosine Similarity

This module orchestrates the existing face verification components.
It does NOT apply a production verification threshold.
"""

from dataclasses import dataclass
from typing import Optional
import os

import cv2
import numpy as np

from .detector import SCRFDDetector
from .quality import evaluate_quality
from .alignment import align_face
from .recognizer import ArcFaceRecognizer
from .similarity import cosine_similarity
from .decision import VerificationDecision, classify


# ---------------------------------------------------------
# PROJECT ROOT
# ---------------------------------------------------------

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
    )
)


# ---------------------------------------------------------
# DEFAULT MODEL PATHS
# ---------------------------------------------------------

DEFAULT_DETECTOR_MODEL = os.path.join(
    PROJECT_ROOT,
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)

DEFAULT_RECOGNIZER_MODEL = os.path.join(
    PROJECT_ROOT,
    "models",
    "buffalo_m",
    "w600k_r50.onnx",
)


@dataclass
class FaceProcessingResult:
    """
    Result of processing one image through the pipeline.
    """

    image_path: str
    embedding: np.ndarray
    quality: object


@dataclass
class VerificationResult:
    """
    Result of comparing two face images.
    """

    image_a: str
    image_b: str
    similarity: float
    decision: VerificationDecision
    quality_a: object
    quality_b: object


class FaceVerificationPipeline:
    """
    Reusable end-to-end face verification pipeline.
    """

    def __init__(
        self,
        detector_model_path: Optional[str] = None,
        recognizer_model_path: Optional[str] = None,
    ):

        # -----------------------------------------------------
        # Resolve model paths
        # -----------------------------------------------------

        if detector_model_path is None:
            detector_model_path = DEFAULT_DETECTOR_MODEL

        if recognizer_model_path is None:
            recognizer_model_path = DEFAULT_RECOGNIZER_MODEL

        # -----------------------------------------------------
        # Validate model paths
        # -----------------------------------------------------

        if not os.path.isfile(detector_model_path):
            raise FileNotFoundError(
                f"SCRFD detector model not found: "
                f"{detector_model_path}"
            )

        if not os.path.isfile(recognizer_model_path):
            raise FileNotFoundError(
                f"ArcFace recognizer model not found: "
                f"{recognizer_model_path}"
            )

        # -----------------------------------------------------
        # Load detector
        # -----------------------------------------------------

        print("Loading SCRFD detector...")

        self.detector = SCRFDDetector(
            detector_model_path
        )

        print("SCRFD detector loaded.")

        # -----------------------------------------------------
        # Load recognizer
        # -----------------------------------------------------

        print("Loading ArcFace R50...")

        self.recognizer = ArcFaceRecognizer(
            recognizer_model_path
        )

        print("ArcFace R50 loaded.")

    def process_image(
        self,
        image_path: str,
    ) -> FaceProcessingResult:
        """
        Process one image through detection, quality,
        alignment and ArcFace embedding generation.

        Returns:
            FaceProcessingResult
        """

        print()
        print("=" * 70)
        print("PROCESSING IMAGE")
        print("=" * 70)
        print(f"Image: {image_path}")

        # -----------------------------------------------------
        # 1. IMAGE LOADING
        # -----------------------------------------------------

        image = cv2.imread(image_path)

        if image is None:
            raise FileNotFoundError(
                f"Could not read image: {image_path}"
            )

        print(f"Image shape: {image.shape}")

        # -----------------------------------------------------
        # 2. FACE DETECTION
        # -----------------------------------------------------

        print()
        print("[1] FACE DETECTION")

        faces = self.detector.detect(image_path)

        print(f"Faces detected: {len(faces)}")

        if len(faces) == 0:
            raise ValueError(
                f"No face detected in image: {image_path}"
            )

        if len(faces) > 1:
            raise ValueError(
                f"Multiple faces detected in image: "
                f"{image_path}. Exactly one face is required."
            )

        face = faces[0]

        print("Single face accepted.")

        # -----------------------------------------------------
        # 3. FACE QUALITY
        # -----------------------------------------------------

        print()
        print("[2] FACE QUALITY")

        quality = evaluate_quality(
            image,
            face,
        )

        print(f"Quality result: {quality}")

        if not quality.quality_ok:
            raise ValueError(
                f"Image failed quality checks: "
                f"{image_path}"
            )

        print("Quality: PASS")

        # -----------------------------------------------------
        # 4. FIVE-POINT ALIGNMENT
        # -----------------------------------------------------

        print()
        print("[3] FIVE-POINT ALIGNMENT")

        aligned = align_face(
            image,
            face,
        )

        if aligned.shape != (112, 112, 3):
            raise RuntimeError(
                f"Unexpected aligned image shape: "
                f"{aligned.shape}"
            )

        print(f"Aligned image shape: {aligned.shape}")
        print("Alignment: PASS")

        # -----------------------------------------------------
        # 5. ARCFACE EMBEDDING
        # -----------------------------------------------------

        print()
        print("[4] ARCFACE R50 EMBEDDING")

        embedding = self.recognizer.get_embedding(
            aligned
        )

        if embedding.shape != (512,):
            raise RuntimeError(
                f"Unexpected embedding shape: "
                f"{embedding.shape}"
            )

        norm = np.linalg.norm(embedding)

        print(f"Embedding shape: {embedding.shape}")
        print(f"Embedding L2 norm: {norm:.6f}")

        if not np.isclose(
            norm,
            1.0,
            atol=1e-5,
        ):
            raise RuntimeError(
                f"Embedding is not properly L2 normalized. "
                f"Norm={norm}"
            )

        print("Embedding: PASS")

        return FaceProcessingResult(
            image_path=image_path,
            embedding=embedding,
            quality=quality,
        )

    def verify(
        self,
        image_a: str,
        image_b: str,
    ) -> VerificationResult:
        """
        Verify two face images by comparing their
        ArcFace embeddings.

        IMPORTANT:
            This method only produces a similarity score.
            It does not decide MATCH / REVIEW / NO MATCH.
        """

        result_a = self.process_image(
            image_a
        )

        result_b = self.process_image(
            image_b
        )

        print()
        print("=" * 70)
        print("[5] COSINE SIMILARITY")
        print("=" * 70)

        similarity = cosine_similarity(
            result_a.embedding,
            result_b.embedding,
        )

        print(
            f"Cosine similarity: "
            f"{similarity:.6f}"
        )

        decision = classify(similarity)

        print()
        print("=" * 70)
        print("VERIFICATION RESULT")
        print("=" * 70)

        print(f"Image A: {image_a}")
        print(f"Image B: {image_b}")
        print(f"Similarity: {similarity:.6f}")
        print(f"Decision: {decision.value}")

        print()
        print("IMPORTANT:")
        print(
            "Thresholds are PROVISIONAL (derived from LFW "
            "calibration evidence) and are NOT production "
            "validated. See src/faceverify/decision.py."
        )

        return VerificationResult(
            image_a=image_a,
            image_b=image_b,
            similarity=similarity,
            decision=decision,
            quality_a=result_a.quality,
            quality_b=result_b.quality,
        )