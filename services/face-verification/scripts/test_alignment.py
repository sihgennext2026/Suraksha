"""
Stage 5 experiment:
Verify SCRFD -> five-point alignment -> 112x112 output.

Usage:
    python scripts\test_alignment.py "PATH_TO_IMAGE"
"""

import os
import sys

import cv2

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
    ),
)

from faceverify.detector import SCRFDDetector, ImageLoadError
from faceverify.alignment import align_face


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)


def main():

    if len(sys.argv) != 2:
        print(
            'Usage: python scripts\\test_alignment.py "PATH_TO_IMAGE"'
        )
        sys.exit(1)

    image_path = sys.argv[1]

    print("Loading SCRFD detector...")
    detector = SCRFDDetector(MODEL_PATH)

    print("Reading image...")
    image = cv2.imread(image_path)

    if image is None:
        print(f"ERROR: Could not load image: {image_path}")
        sys.exit(1)

    print(f"Original image shape: {image.shape}")

    print("Running face detection...")

    try:
        faces = detector.detect(image_path)
    except ImageLoadError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Faces detected: {len(faces)}")

    if len(faces) != 1:
        print("ERROR: Alignment experiment requires exactly one face.")
        sys.exit(1)

    face = faces[0]

    print("\nSCRFD landmarks:")
    print(f"  Left eye:   {face.left_eye}")
    print(f"  Right eye:  {face.right_eye}")
    print(f"  Nose:       {face.nose}")
    print(f"  Left mouth: {face.left_mouth}")
    print(f"  Right mouth:{face.right_mouth}")

    print("\nRunning five-point alignment...")

    try:
        aligned = align_face(image, face)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("\n--- ALIGNMENT RESULTS ---")
    print(f"Aligned image shape: {aligned.shape}")
    print(f"Aligned height:      {aligned.shape[0]}")
    print(f"Aligned width:       {aligned.shape[1]}")
    print(f"Aligned channels:    {aligned.shape[2]}")

    output_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "experiments",
        "aligned_face.jpg",
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cv2.imwrite(output_path, aligned)

    print(f"\nSaved aligned face to:")
    print(os.path.abspath(output_path))

    if aligned.shape == (112, 112, 3):
        print("\nALIGNMENT STATUS: PASS")
    else:
        print("\nALIGNMENT STATUS: FAIL")


if __name__ == "__main__":
    main()