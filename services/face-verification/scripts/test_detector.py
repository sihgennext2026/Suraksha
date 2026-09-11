"""
Stage 3 test: run SCRFD detector on a user-supplied image.
"""

import os
import sys

# Make src/ importable when this script is run directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from faceverify.detector import (
    SCRFDDetector,
    get_capture_status,
    ImageLoadError,
)


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)


def main():
    if len(sys.argv) != 2:
        print('Usage: python scripts\\test_detector.py "PATH_TO_IMAGE"')
        sys.exit(1)

    image_path = sys.argv[1]

    print("Loading SCRFD detector...")
    detector = SCRFDDetector(MODEL_PATH)

    print("Detector loaded successfully.")
    print(f"Testing image: {image_path}")

    try:
        faces = detector.detect(image_path)
    except ImageLoadError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"\nNumber of faces detected: {len(faces)}")

    for i, face in enumerate(faces):
        print(f"\nFace {i + 1}:")
        print(f"  bbox: {face.bbox}")
        print(f"  confidence: {face.confidence:.4f}")
        print(f"  left_eye:   {face.left_eye}")
        print(f"  right_eye:  {face.right_eye}")
        print(f"  nose:       {face.nose}")
        print(f"  left_mouth: {face.left_mouth}")
        print(f"  right_mouth:{face.right_mouth}")

    status = get_capture_status(len(faces))

    print(f"\nCAPTURE STATUS: {status}")


if __name__ == "__main__":
    main()