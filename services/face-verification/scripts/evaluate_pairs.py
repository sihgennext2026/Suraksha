"""
Stage 9: Genuine vs impostor face-verification experiment.

Purpose:
    Evaluate cosine similarity between:
      - genuine pairs: same person
      - impostor pairs: different people

This is a DEVELOPMENT EXPERIMENT only.
The resulting scores must NOT be used as production thresholds.
"""

import os
import sys
from itertools import combinations

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from faceverify.detector import SCRFDDetector
from faceverify.alignment import align_face
from faceverify.recognizer import ArcFaceRecognizer


MODEL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "models", "buffalo_m"
)

DETECTOR_PATH = os.path.join(MODEL_DIR, "det_2.5g.onnx")
RECOGNIZER_PATH = os.path.join(MODEL_DIR, "w600k_r50.onnx")


IMAGE_DIR = r"C:\Users\josep\OneDrive\Pictures\Camera Roll"

PEOPLE = {
    "YOU": [
        "Face Detection Test Image.jpg",
        "FDTI1.jpg",
        "FDTI2.jpg",
        "FDTI3.jpg",
    ],
    "FRIEND": [
        "FDTI4.jpeg",
        "FDTI5.jpeg",
        "FDTI6.jpeg",
        "FDTI7.jpeg",
    ],
}


def cosine_similarity(a, b):
    return float(np.dot(a, b))


def main():

    print("=" * 70)
    print("STAGE 9 — GENUINE VS IMPOSTOR EXPERIMENT")
    print("=" * 70)

    print("\nLoading SCRFD detector...")
    detector = SCRFDDetector(DETECTOR_PATH)

    print("Loading ArcFace R50...")
    recognizer = ArcFaceRecognizer(RECOGNIZER_PATH)

    embeddings = {}

    print("\nGenerating embeddings...")
    print("-" * 70)

    for person, filenames in PEOPLE.items():

        for filename in filenames:

            path = os.path.join(IMAGE_DIR, filename)

            print(f"\n{person}: {filename}")

            if not os.path.isfile(path):
                print("  ERROR: file not found")
                continue

            faces = detector.detect(path)

            print(f"  Faces detected: {len(faces)}")

            if len(faces) != 1:
                print("  SKIPPED: expected exactly one face")
                continue

            face = faces[0]

            image = cv2.imread(path)

            if image is None:
                print("  SKIPPED: could not read image")
                continue

            aligned = align_face(image, face)

            embedding = recognizer.get_embedding(aligned)

            embeddings[(person, filename)] = embedding

            print(f"  Embedding shape: {embedding.shape}")
            print(f"  L2 norm: {np.linalg.norm(embedding):.6f}")

    print("\n" + "=" * 70)
    print("GENUINE PAIRS — SAME PERSON")
    print("=" * 70)

    genuine_scores = []

    for person, filenames in PEOPLE.items():

        available = [
            (person, filename)
            for filename in filenames
            if (person, filename) in embeddings
        ]

        for a, b in combinations(available, 2):

            score = cosine_similarity(
                embeddings[a],
                embeddings[b],
            )

            genuine_scores.append(score)

            print(
                f"{person}: "
                f"{a[1]} <-> {b[1]}: "
                f"{score:.6f}"
            )

    print("\n" + "=" * 70)
    print("IMPOSTOR PAIRS — DIFFERENT PEOPLE")
    print("=" * 70)

    impostor_scores = []

    you_images = [
        key for key in embeddings
        if key[0] == "YOU"
    ]

    friend_images = [
        key for key in embeddings
        if key[0] == "FRIEND"
    ]

    for a in you_images:

        for b in friend_images:

            score = cosine_similarity(
                embeddings[a],
                embeddings[b],
            )

            impostor_scores.append(score)

            print(
                f"YOU: {a[1]} <-> "
                f"FRIEND: {b[1]}: "
                f"{score:.6f}"
            )

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if genuine_scores:
        print(f"Genuine pairs:  {len(genuine_scores)}")
        print(f"Genuine mean:   {np.mean(genuine_scores):.6f}")
        print(f"Genuine min:    {np.min(genuine_scores):.6f}")
        print(f"Genuine max:    {np.max(genuine_scores):.6f}")

    if impostor_scores:
        print(f"\nImpostor pairs:  {len(impostor_scores)}")
        print(f"Impostor mean:   {np.mean(impostor_scores):.6f}")
        print(f"Impostor min:    {np.min(impostor_scores):.6f}")
        print(f"Impostor max:    {np.max(impostor_scores):.6f}")

    print("\n" + "=" * 70)
    print("IMPORTANT")
    print("=" * 70)
    print(
        "These results are a development experiment only."
    )
    print(
        "They are NOT sufficient to define production thresholds."
    )
    print(
        "Production calibration requires a larger held-out"
    )
    print(
        "genuine/impostor evaluation dataset."
    )


if __name__ == "__main__":
    import cv2
    main()