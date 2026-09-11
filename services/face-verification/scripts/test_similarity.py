"""
Stage 7 experiment:
Compare three face captures using ArcFace embeddings.

This is a sanity experiment only.
It does NOT establish production thresholds.

Usage:
    python scripts\test_similarity.py
"""

import os
import sys

import cv2
import numpy as np

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
    ),
)

from faceverify.detector import SCRFDDetector
from faceverify.alignment import align_face
from faceverify.recognizer import ArcFaceRecognizer
from faceverify.similarity import cosine_similarity


DETECTOR_MODEL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)


IMAGES = {
    "FDTI1": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI1.jpg",
    "FDTI2": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI2.jpg",
    "FDTI3": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI3.jpg",
}


def get_embedding(image_path, detector, recognizer):

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Could not load image: {image_path}"
        )

    faces = detector.detect(image_path)

    if len(faces) != 1:
        raise ValueError(
            f"Expected exactly one face in {image_path}, "
            f"found {len(faces)}"
        )

    aligned = align_face(
        image,
        faces[0],
    )

    return recognizer.get_embedding(
        aligned
    )


def main():

    print("Loading models...")

    detector = SCRFDDetector(
        DETECTOR_MODEL
    )

    recognizer = ArcFaceRecognizer()

    embeddings = {}

    print("\nGenerating embeddings...\n")

    for name, path in IMAGES.items():

        print(f"{name}: {path}")

        embeddings[name] = get_embedding(
            path,
            detector,
            recognizer,
        )

        print(
            f"  Embedding shape: "
            f"{embeddings[name].shape}"
        )

        print(
            f"  L2 norm: "
            f"{np.linalg.norm(embeddings[name]):.6f}"
        )

    print("\n" + "=" * 60)
    print("COSINE SIMILARITY RESULTS")
    print("=" * 60)

    pairs = [
        ("FDTI1", "FDTI2"),
        ("FDTI1", "FDTI3"),
        ("FDTI2", "FDTI3"),
    ]

    for a, b in pairs:

        score = cosine_similarity(
            embeddings[a],
            embeddings[b],
        )

        print(
            f"{a} <-> {b}: "
            f"{score:.6f}"
        )

    print("\nIMPORTANT:")
    print(
        "These scores are a pipeline sanity check only."
    )
    print(
        "They are NOT production match thresholds."
    )


if __name__ == "__main__":
    main()