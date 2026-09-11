import sys
from pathlib import Path

import cv2
import numpy as np

# Allow imports from src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from faceverify.detector import SCRFDDetector
from faceverify.alignment import align_face
from faceverify.recognizer import ArcFaceRecognizer
from faceverify.similarity import cosine_similarity


# ============================================================
# MODEL PATHS
# ============================================================

DETECTOR_PATH = PROJECT_ROOT / "models" / "buffalo_m" / "det_2.5g.onnx"
RECOGNIZER_PATH = PROJECT_ROOT / "models" / "buffalo_m" / "w600k_r50.onnx"


# ============================================================
# IMAGE PATHS
# ============================================================

IMAGES = {
    "YOU_ORDINARY": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\Face Detection Test Image.jpg",
    "YOU_ORDINARY_2": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI1.jpg",
    "YOU_LEFT": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI2.jpg",
    "YOU_CLOSEUP": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI3.jpg",

    "FRIEND_CLOSEUP": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI4.jpeg",
    "FRIEND_ORDINARY": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI5.jpeg",
    "FRIEND_LEFT": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI6.jpeg",
    "FRIEND_RIGHT": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI7.jpeg",
}


# ============================================================
# GENERATE ONE EMBEDDING
# ============================================================

def generate_embedding(detector, recognizer, image_path):
    image_path = str(image_path)

    image = cv2.imread(image_path)

    if image is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    faces = detector.detect(image_path)

    if len(faces) != 1:
        raise RuntimeError(
            f"Expected exactly 1 face in {image_path}, "
            f"but detected {len(faces)}"
        )

    face = faces[0]

    aligned = align_face(image, face)

    embedding = recognizer.get_embedding(aligned)

    return embedding
# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("STAGE 6 — GENUINE VS IMPOSTOR EXPERIMENT")
    print("=" * 70)

    print("\nLoading models...")

    detector = SCRFDDetector(str(DETECTOR_PATH))
    recognizer = ArcFaceRecognizer(str(RECOGNIZER_PATH))

    print("Models loaded successfully.")

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    embeddings = {}

    print("\nGenerating embeddings...\n")

    for name, path in IMAGES.items():

        print(f"Processing: {name}")

        embedding = generate_embedding(
            detector,
            recognizer,
            path
        )

        embeddings[name] = embedding

        print(f"  Shape: {embedding.shape}")
        print(f"  L2 norm: {np.linalg.norm(embedding):.6f}")

    # --------------------------------------------------------
    # Genuine pairs
    # --------------------------------------------------------

    genuine_pairs = [
        ("YOU_ORDINARY", "YOU_ORDINARY_2"),
        ("YOU_ORDINARY", "YOU_LEFT"),
        ("YOU_ORDINARY", "YOU_CLOSEUP"),
        ("YOU_ORDINARY_2", "YOU_LEFT"),
        ("YOU_ORDINARY_2", "YOU_CLOSEUP"),
        ("YOU_LEFT", "YOU_CLOSEUP"),

        ("FRIEND_CLOSEUP", "FRIEND_ORDINARY"),
        ("FRIEND_CLOSEUP", "FRIEND_LEFT"),
        ("FRIEND_CLOSEUP", "FRIEND_RIGHT"),
        ("FRIEND_ORDINARY", "FRIEND_LEFT"),
        ("FRIEND_ORDINARY", "FRIEND_RIGHT"),
        ("FRIEND_LEFT", "FRIEND_RIGHT"),
    ]

    # --------------------------------------------------------
    # Impostor pairs
    # --------------------------------------------------------

    impostor_pairs = [
        ("YOU_ORDINARY", "FRIEND_ORDINARY"),
        ("YOU_ORDINARY", "FRIEND_CLOSEUP"),
        ("YOU_ORDINARY", "FRIEND_LEFT"),
        ("YOU_ORDINARY", "FRIEND_RIGHT"),

        ("YOU_ORDINARY_2", "FRIEND_ORDINARY"),
        ("YOU_ORDINARY_2", "FRIEND_CLOSEUP"),
        ("YOU_ORDINARY_2", "FRIEND_LEFT"),
        ("YOU_ORDINARY_2", "FRIEND_RIGHT"),

        ("YOU_LEFT", "FRIEND_ORDINARY"),
        ("YOU_LEFT", "FRIEND_CLOSEUP"),
        ("YOU_LEFT", "FRIEND_LEFT"),
        ("YOU_LEFT", "FRIEND_RIGHT"),

        ("YOU_CLOSEUP", "FRIEND_ORDINARY"),
        ("YOU_CLOSEUP", "FRIEND_CLOSEUP"),
        ("YOU_CLOSEUP", "FRIEND_LEFT"),
        ("YOU_CLOSEUP", "FRIEND_RIGHT"),
    ]

    # --------------------------------------------------------
    # Calculate similarities
    # --------------------------------------------------------

    genuine_scores = []
    impostor_scores = []

    print("\n")
    print("=" * 70)
    print("GENUINE PAIRS — SAME PERSON")
    print("=" * 70)

    for a, b in genuine_pairs:

        score = cosine_similarity(
            embeddings[a],
            embeddings[b]
        )

        genuine_scores.append(score)

        print(f"{a:20s} <-> {b:20s} : {score:.6f}")

    print("\n")
    print("=" * 70)
    print("IMPOSTOR PAIRS — DIFFERENT PEOPLE")
    print("=" * 70)

    for a, b in impostor_pairs:

        score = cosine_similarity(
            embeddings[a],
            embeddings[b]
        )

        impostor_scores.append(score)

        print(f"{a:20s} <-> {b:20s} : {score:.6f}")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    genuine_scores = np.array(genuine_scores)
    impostor_scores = np.array(impostor_scores)

    print("\n")
    print("=" * 70)
    print("EXPERIMENT SUMMARY")
    print("=" * 70)

    print("\nGENUINE SCORES:")
    print(f"  Count : {len(genuine_scores)}")
    print(f"  Min   : {genuine_scores.min():.6f}")
    print(f"  Mean  : {genuine_scores.mean():.6f}")
    print(f"  Max   : {genuine_scores.max():.6f}")

    print("\nIMPOSTOR SCORES:")
    print(f"  Count : {len(impostor_scores)}")
    print(f"  Min   : {impostor_scores.min():.6f}")
    print(f"  Mean  : {impostor_scores.mean():.6f}")
    print(f"  Max   : {impostor_scores.max():.6f}")

    separation = genuine_scores.mean() - impostor_scores.mean()

    print("\nMEAN SCORE SEPARATION:")
    print(f"  Genuine mean - Impostor mean = {separation:.6f}")

    print("\nIMPORTANT:")
    print("These results are a small engineering experiment.")
    print("They are NOT sufficient for production threshold calibration.")
    print("Production thresholds require a representative evaluation dataset.")

    print("\nSTAGE 6 STATUS: EXPERIMENT COMPLETE")


if __name__ == "__main__":
    main()