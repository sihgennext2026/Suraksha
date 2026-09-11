"""
Reusable end-to-end face verification pipeline.

Pipeline:

    Document image
      -> Portrait extraction
      -> Face Detection
      -> Face Quality
      -> Five-point Alignment
      -> ArcFace R50 Embedding
      -> Cosine Similarity
      -> Decision

    Live image
      -> Face Detection
      -> Face Quality
      -> Five-point Alignment
      -> ArcFace R50 Embedding
      -> Cosine Similarity
      -> Decision

This module orchestrates the existing face verification components.

IMPORTANT:
    The verification threshold is currently provisional and must
    be calibrated and validated before production use.
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
from .portrait_crop import crop_portrait


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


# ---------------------------------------------------------
# RESULT CLASSES
# ---------------------------------------------------------

@dataclass
class FaceProcessingResult:
    """
    Result of processing one face image.
    """

    image_path: str
    embedding: np.ndarray
    quality: object


@dataclass
class VerificationResult:
    """
    Result of comparing a document portrait with
    a live face image.
    """

    image_a: str
    image_b: str
    similarity: float
    decision: VerificationDecision
    quality_a: object
    quality_b: object


# ---------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------

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

    # =========================================================
    # PROCESS NORMAL FACE IMAGE
    # =========================================================

    def process_image(
        self,
        image_path: str,
    ) -> FaceProcessingResult:
        """
        Process one image containing exactly one face.

        Pipeline:

            Image
              -> Face Detection
              -> Face Quality
              -> Five-point Alignment
              -> ArcFace R50 Embedding
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

        faces = self.detector.detect(
            image_path
        )

        print(f"Faces detected: {len(faces)}")

        if len(faces) == 0:
            raise ValueError(
                f"No face detected in image: "
                f"{image_path}"
            )

        if len(faces) > 1:
            raise ValueError(
                f"Multiple faces detected in image: "
                f"{image_path}. "
                f"Exactly one face is required."
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

        print(
            f"Quality result: {quality}"
        )

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

        print(
            f"Aligned image shape: "
            f"{aligned.shape}"
        )

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

        norm = np.linalg.norm(
            embedding
        )

        print(
            f"Embedding shape: "
            f"{embedding.shape}"
        )

        print(
            f"Embedding L2 norm: "
            f"{norm:.6f}"
        )

        if not np.isclose(
            norm,
            1.0,
            atol=1e-5,
        ):
            raise RuntimeError(
                f"Embedding is not properly "
                f"L2 normalized. Norm={norm}"
            )

        print("Embedding: PASS")

        return FaceProcessingResult(
            image_path=image_path,
            embedding=embedding,
            quality=quality,
        )

    # =========================================================
    # PROCESS DOCUMENT IMAGE
    # =========================================================

    def process_document_image(
        self,
        document_image_path: str,
    ) -> FaceProcessingResult:
        """
        Process a perspective-corrected document image.

        Pipeline:

            Document image
              -> Portrait extraction
              -> Single-face processing
              -> ArcFace embedding

        The portrait_crop module detects all faces and selects
        the largest sufficiently-sized face.
        """

        print()
        print("=" * 70)
        print("PROCESSING DOCUMENT IMAGE")
        print("=" * 70)

        print(
            f"Document: "
            f"{document_image_path}"
        )

        # -----------------------------------------------------
        # 1. DOCUMENT PORTRAIT EXTRACTION
        # -----------------------------------------------------

        print()
        print(
            "[1] DOCUMENT PORTRAIT EXTRACTION"
        )

        experiments_dir = os.path.join(
            PROJECT_ROOT,
            "experiments",
        )

        os.makedirs(
            experiments_dir,
            exist_ok=True,
        )

        portrait_path = os.path.join(
            experiments_dir,
            "pipeline_document_portrait.jpg",
        )

        cropped_face, selected_face, bbox, crop_box = crop_portrait(
            document_image_path,
            self.detector,
            portrait_path,
            padding_ratio=0.20,
            return_face=True,
        )

        print()
        print(
            f"Selected portrait bbox: "
            f"{bbox}"
        )

        print(
            f"Portrait crop box: "
            f"{crop_box}"
        )

        print(
            f"Portrait shape: "
            f"{cropped_face.shape}"
        )

        print(
            f"Portrait saved to: "
            f"{portrait_path}"
        )

        # -----------------------------------------------------
        # 2. PROCESS EXTRACTED PORTRAIT
        # -----------------------------------------------------

        print()
        print(
            "[2] PROCESSING EXTRACTED "
            "DOCUMENT PORTRAIT"
        )

        image = cv2.imread(document_image_path)

        if image is None:
            raise FileNotFoundError(
                f"Could not load document image: {document_image_path}"
            )

        print("Using original document image + existing SCRFD landmarks.")

        quality = evaluate_quality(image, selected_face)
        print(f"Document portrait quality: {quality}")

        if not quality.quality_ok:
            raise ValueError(
                f"Document portrait quality failed: {quality}"
            )

        print("Document portrait quality: PASS")

        print("[3] FIVE-POINT ALIGNMENT")
        aligned = align_face(image, selected_face)
        print(f"Aligned face shape: {aligned.shape}")

        print("[4] ARCFACE EMBEDDING")
        embedding = self.recognizer.get_embedding(aligned)
        print(f"Embedding shape: {embedding.shape}")
        print(f"Embedding norm: {np.linalg.norm(embedding):.6f}")

        return FaceProcessingResult(
            image_path=portrait_path,
            embedding=embedding,
            quality=quality,
        )

    # =========================================================
    # VERIFY DOCUMENT AGAINST LIVE IMAGE
    # =========================================================

    def verify(
        self,
        image_a: str,
        image_b: str,
    ) -> VerificationResult:
        """
        Verify a document image against a live face image.

        Image A:
            Perspective-corrected document image.

        Image B:
            Live face image.

        Image A automatically goes through portrait extraction.

        Image B is processed directly as a single-face image.

        Both images ultimately produce 512-dimensional
        ArcFace embeddings which are compared using cosine
        similarity.
        """

        # -----------------------------------------------------
        # DOCUMENT IMAGE
        # -----------------------------------------------------

        result_a = self.process_document_image(
            image_a
        )

        # -----------------------------------------------------
        # LIVE IMAGE
        # -----------------------------------------------------

        result_b = self.process_image(
            image_b
        )

        # -----------------------------------------------------
        # COSINE SIMILARITY
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # DECISION
        # -----------------------------------------------------

        decision = classify(
            similarity
        )

        print()
        print("=" * 70)
        print("VERIFICATION RESULT")
        print("=" * 70)

        print(
            f"Image A: "
            f"{image_a}"
        )

        print(
            f"Image B: "
            f"{image_b}"
        )

        print(
            f"Similarity: "
            f"{similarity:.6f}"
        )

        print(
            f"Decision: "
            f"{decision.value}"
        )

        print()
        print("IMPORTANT:")

        print(
            "Thresholds are PROVISIONAL "
            "(derived from LFW calibration evidence) "
            "and are NOT production validated. "
            "See src/faceverify/decision.py."
        )

        return VerificationResult(
            image_a=image_a,
            image_b=image_b,
            similarity=similarity,
            decision=decision,
            quality_a=result_a.quality,
            quality_b=result_b.quality,
        )
