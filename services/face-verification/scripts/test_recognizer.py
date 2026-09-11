"""
Stage 6 experiment:
SCRFD -> alignment -> ArcFace R50 -> 512-D embedding.

Usage:
    python scripts\test_recognizer.py "PATH_TO_IMAGE"
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

from faceverify.detector import (
    SCRFDDetector,
    ImageLoadError,
)
from faceverify.alignment import align_face
from faceverify.recognizer import ArcFaceRecognizer


DETECTOR_MODEL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)


def main():

    if len(sys.argv) != 2:
        print(
            'Usage: python scripts\\test_recognizer.py "PATH_TO_IMAGE"'
        )
        sys.exit(1)

    image_path = sys.argv[1]

    print("Loading SCRFD detector...")
    detector = SCRFDDetector(DETECTOR_MODEL)

    print("Loading ArcFace R50...")
    recognizer = ArcFaceRecognizer()

    print("Reading image...")
    image = cv2.imread(image_path)

    if image is None:
        print(
            f"ERROR: Could not load image: {image_path}"
        )
        sys.exit(1)

    print(
        f"Original image shape: {image.shape}"
    )

    print("Running face detection...")

    try:
        faces = detector.detect(image_path)
    except ImageLoadError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(
        f"Faces detected: {len(faces)}"
    )

    if len(faces) != 1:
        print(
            "ERROR: Recognition test requires exactly one face."
        )
        sys.exit(1)

    face = faces[0]

    print("Running five-point alignment...")

    aligned = align_face(
        image,
        face,
    )

    print(
        f"Aligned image shape: {aligned.shape}"
    )

    print("Generating ArcFace embedding...")

    embedding = recognizer.get_embedding(
        aligned
    )
        # Save complete 512-D embedding
    embedding_dir = os.path.join(
        os.path.dirname(__file__),
        "..",
        "embeddings",
    )

    os.makedirs(embedding_dir, exist_ok=True)

    image_name = os.path.splitext(
        os.path.basename(image_path)
    )[0]

    embedding_path = os.path.join(
        embedding_dir,
        f"{image_name}.npy",
    )

    np.save(
        embedding_path,
        embedding,
    )

    print(
        f"Embedding saved to: {embedding_path}"
    )

    print("\n--- ARCFACE RESULTS ---")
    print(
        f"Embedding shape: {embedding.shape}"
    )
    print(
        f"Embedding dtype: {embedding.dtype}"
    )
    print(
        f"Embedding L2 norm: {np.linalg.norm(embedding):.6f}"
    )

    print("\nFirst 10 embedding values:")

    for i, value in enumerate(
        embedding[:10]
    ):
        print(
            f"  [{i}] {value:.8f}"
        )

    if embedding.shape == (512,):
        shape_status = "PASS"
    else:
        shape_status = "FAIL"

    norm = np.linalg.norm(embedding)

    if abs(norm - 1.0) < 1e-5:
        norm_status = "PASS"
    else:
        norm_status = "FAIL"

    print(
        f"\nEmbedding shape check: {shape_status}"
    )

    print(
        f"L2 normalization check: {norm_status}"
    )

    if (
        shape_status == "PASS"
        and norm_status == "PASS"
    ):
        print(
            "\nARCFACE EMBEDDING STATUS: PASS"
        )
    else:
        print(
            "\nARCFACE EMBEDDING STATUS: FAIL"
        )


if __name__ == "__main__":
    main()