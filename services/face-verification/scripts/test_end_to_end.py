"""
End-to-end face verification pipeline test.

Pipeline:
Image
  -> SCRFD detection
  -> Face quality
  -> Five-point alignment
  -> ArcFace R50 embedding
  -> Cosine similarity

This script is an engineering validation tool.
It does NOT apply production MATCH/REVIEW/NO MATCH thresholds.
"""

import os
import sys

# Allow imports from the project root when this script is executed
# as: python scripts\test_end_to_end.py ...
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import cv2
import numpy as np

from src.faceverify.detector import SCRFDDetector
from src.faceverify.quality import evaluate_quality
from src.faceverify.alignment import align_face
from src.faceverify.recognizer import ArcFaceRecognizer
from src.faceverify.similarity import cosine_similarity


DETECTOR_MODEL = os.path.join(
    PROJECT_ROOT,
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)

RECOGNIZER_MODEL = os.path.join(
    PROJECT_ROOT,
    "models",
    "buffalo_m",
    "w600k_r50.onnx",
)


def process_image(image_path, detector, recognizer, label):
    print()
    print("=" * 70)
    print(f"PROCESSING: {label}")
    print("=" * 70)

    print(f"Image: {image_path}")

    if not os.path.isfile(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    print(f"Original image shape: {image.shape}")

    # ---------------------------------------------------------
    # 1. FACE DETECTION
    # ---------------------------------------------------------
    print()
    print("[1] FACE DETECTION")

    faces = detector.detect(image_path)

    print(f"Faces detected: {len(faces)}")

    if len(faces) == 0:
        raise RuntimeError("No face detected.")

    if len(faces) > 1:
        raise RuntimeError(
            "Multiple faces detected. Verification requires exactly one face."
        )

    face = faces[0]

    print("Single face accepted.")

    print("Landmarks:")
    print(f"  Left eye:    {face.left_eye}")
    print(f"  Right eye:   {face.right_eye}")
    print(f"  Nose:        {face.nose}")
    print(f"  Left mouth:  {face.left_mouth}")
    print(f"  Right mouth: {face.right_mouth}")

    # ---------------------------------------------------------
    # 2. FACE QUALITY
    # ---------------------------------------------------------
    print()
    print("[2] FACE QUALITY")

    quality = evaluate_quality(
        image,
        face,
    )

    print(f"Quality result: {quality}")

    # Try to display common quality attributes if available.
    for attribute in [
        "quality_score",
        "status",
        "face_width",
        "face_height",
        "brightness",
        "blur_score",
    ]:
        if hasattr(quality, attribute):
            print(
                f"  {attribute}: "
                f"{getattr(quality, attribute)}"
            )

    # ---------------------------------------------------------
    # 3. ALIGNMENT
    # ---------------------------------------------------------
    print()
    print("[3] FIVE-POINT ALIGNMENT")

    aligned = align_face(
        image,
        face,
    )

    print(f"Aligned image shape: {aligned.shape}")

    if aligned.shape != (112, 112, 3):
        raise RuntimeError(
            f"Unexpected alignment output: {aligned.shape}"
        )

    print("Alignment: PASS")

    # Save aligned face for visual inspection.
    experiments_dir = os.path.join(
        PROJECT_ROOT,
        "experiments",
    )

    os.makedirs(
        experiments_dir,
        exist_ok=True,
    )

    safe_label = label.lower().replace(" ", "_")

    aligned_path = os.path.join(
        experiments_dir,
        f"aligned_{safe_label}.jpg",
    )

    cv2.imwrite(
        aligned_path,
        aligned,
    )

    print(f"Saved aligned face: {aligned_path}")

    # ---------------------------------------------------------
    # 4. ARCFACE EMBEDDING
    # ---------------------------------------------------------
    print()
    print("[4] ARCFACE R50 EMBEDDING")

    embedding = recognizer.get_embedding(
        aligned
    )

    print(f"Embedding shape: {embedding.shape}")
    print(f"Embedding dtype: {embedding.dtype}")
    print(
        f"Embedding L2 norm: "
        f"{np.linalg.norm(embedding):.6f}"
    )

    if embedding.shape != (512,):
        raise RuntimeError(
            f"Unexpected embedding shape: {embedding.shape}"
        )

    print("Embedding: PASS")

    return embedding


def main():

    if len(sys.argv) != 3:
        print(
            "Usage:\n"
            'python scripts\\test_end_to_end.py '
            '"IMAGE_A" "IMAGE_B"'
        )
        sys.exit(1)

    image_a = sys.argv[1]
    image_b = sys.argv[2]

    print("=" * 70)
    print("END-TO-END FACE VERIFICATION PIPELINE")
    print("=" * 70)

    print()
    print("Loading SCRFD detector...")

    detector = SCRFDDetector(
        DETECTOR_MODEL
    )

    print("SCRFD: LOADED")

    print()
    print("Loading ArcFace R50...")

    recognizer = ArcFaceRecognizer(
        RECOGNIZER_MODEL
    )

    print("ArcFace R50: LOADED")

    # ---------------------------------------------------------
    # PROCESS BOTH IMAGES
    # ---------------------------------------------------------

    embedding_a = process_image(
        image_a,
        detector,
        recognizer,
        "IMAGE_A",
    )

    embedding_b = process_image(
        image_b,
        detector,
        recognizer,
        "IMAGE_B",
    )

    # ---------------------------------------------------------
    # 5. COSINE SIMILARITY
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("[5] COSINE SIMILARITY")
    print("=" * 70)

    similarity = cosine_similarity(
        embedding_a,
        embedding_b,
    )

    print(
        f"Cosine similarity: {similarity:.6f}"
    )

    print()
    print("=" * 70)
    print("END-TO-END PIPELINE STATUS")
    print("=" * 70)

    print("Detection:       PASS")
    print("Quality:         COMPLETED")
    print("Alignment:       PASS")
    print("ArcFace:         PASS")
    print("Embedding:       PASS")
    print("Similarity:      PASS")

    print()
    print(
        "IMPORTANT: This similarity score is an "
        "engineering measurement only."
    )

    print(
        "No production MATCH/REVIEW/NO MATCH "
        "threshold is applied."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()