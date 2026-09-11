"""
Stage 4 test: SCRFD detection followed by face quality evaluation.
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

from faceverify.detector import SCRFDDetector
from faceverify.quality import evaluate_quality


MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)

IMAGE_PATH = (
    r"C:\Users\josep\OneDrive\Pictures\Camera Roll"
    r"\Face Detection Test Image.jpg"
)


def main():
    print("Loading SCRFD detector...")
    detector = SCRFDDetector(MODEL_PATH)

    print("Reading image...")
    image = cv2.imread(IMAGE_PATH)

    if image is None:
        raise RuntimeError(
            f"Could not read image: {IMAGE_PATH}"
        )

    print("Running face detection...")
    faces = detector.detect(IMAGE_PATH)

    print(f"\nFaces detected: {len(faces)}")

    if len(faces) != 1:
        print("\nQUALITY STATUS: RECAPTURE")
        return

    face = faces[0]

    print("Evaluating face quality...")
    result = evaluate_quality(image, face)

    print("\n--- FACE QUALITY RESULTS ---")

    print(
        f"Face width:       "
        f"{result.face_width:.2f} px"
    )

    print(
        f"Face height:      "
        f"{result.face_height:.2f} px"
    )

    print(
        f"Brightness:       "
        f"{result.brightness:.2f}"
    )

    print(
        f"Blur score:       "
        f"{result.blur_score:.2f}"
    )

    if result.yaw_proxy is not None:
    	print(f"Yaw proxy:        {result.yaw_proxy:.4f}")
    	print(f"Roll:             {result.roll:.2f}°")
    else:
    	print("Pose estimation:  FAILED")
    print("\nIndividual checks:")

    print(
        f"  Face size:      "
        f"{'PASS' if result.face_size_ok else 'FAIL'}"
    )

    print(
        f"  Brightness:     "
        f"{'PASS' if result.brightness_ok else 'FAIL'}"
    )

    print(
        f"  Blur:           "
        f"{'PASS' if result.blur_ok else 'FAIL'}"
    )

    print(
        f"  Pose:           "
        f"{'PASS' if result.pose_ok else 'FAIL'}"
    )

    status = (
        "ACCEPT_FOR_NEXT_STAGE"
        if result.quality_ok
        else "RECAPTURE"
    )

    print(f"\nQUALITY STATUS: {status}")


if __name__ == "__main__":
    main()