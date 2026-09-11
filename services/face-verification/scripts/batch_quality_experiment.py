"""
Stage 7: Batch Face Quality Experiment

Purpose:
    Evaluate the current face-quality gate across all test images.

This experiment reports:
    - Face detection
    - Face dimensions
    - Brightness
    - Blur score
    - Quality checks
    - Final quality status

Important:
    This is an engineering experiment only.
    It is NOT production threshold calibration.
"""

import sys
from pathlib import Path

import cv2

# Allow imports from src/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from faceverify.detector import SCRFDDetector
from faceverify.quality import evaluate_quality


# ---------------------------------------------------------
# MODEL PATH
# ---------------------------------------------------------

DETECTOR_MODEL = (
    PROJECT_ROOT
    / "models"
    / "buffalo_m"
    / "det_2.5g.onnx"
)


# ---------------------------------------------------------
# TEST IMAGES
# ---------------------------------------------------------

IMAGE_PATHS = {
    "YOU_ORDINARY": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\Face Detection Test Image.jpg",

    "YOU_ORDINARY_2": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI1.jpg",

    "YOU_LEFT": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI2.jpg",

    "YOU_CLOSEUP": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI3.jpg",

    "FRIEND_CLOSEUP": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI4.jpeg",

    "FRIEND_ORDINARY": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI5.jpeg",

    "FRIEND_LEFT": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI6.jpeg",

    "FRIEND_RIGHT": r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI7.jpeg",
}


# ---------------------------------------------------------
# MAIN EXPERIMENT
# ---------------------------------------------------------

def main():

    print("=" * 80)
    print("STAGE 7 — BATCH FACE QUALITY ANALYSIS")
    print("=" * 80)

    print()
    print("Loading SCRFD detector...")

    detector = SCRFDDetector(str(DETECTOR_MODEL))

    print("Detector loaded.")

    print()
    print("=" * 80)

    results = []

    for name, image_path in IMAGE_PATHS.items():

        print()
        print("=" * 80)
        print(f"IMAGE: {name}")
        print("=" * 80)

        # -------------------------------------------------
        # Check file exists
        # -------------------------------------------------

        path = Path(image_path)

        if not path.exists():

            print("ERROR: Image file not found.")
            print(f"Path: {image_path}")

            results.append(
                {
                    "name": name,
                    "status": "FILE_NOT_FOUND",
                }
            )

            continue

        # -------------------------------------------------
        # Read image
        # -------------------------------------------------

        image = cv2.imread(str(path))

        if image is None:

            print("ERROR: OpenCV could not read image.")

            results.append(
                {
                    "name": name,
                    "status": "READ_ERROR",
                }
            )

            continue

        print(f"Image shape: {image.shape}")

        # -------------------------------------------------
        # Face detection
        # -------------------------------------------------

        faces = detector.detect(str(path))

        print(f"Faces detected: {len(faces)}")

        # -------------------------------------------------
        # Detection validation
        # -------------------------------------------------

        if len(faces) == 0:

            print("QUALITY STATUS: RECAPTURE")

            results.append(
                {
                    "name": name,
                    "status": "NO_FACE",
                }
            )

            continue

        if len(faces) > 1:

            print("QUALITY STATUS: INVALID_CAPTURE")

            results.append(
                {
                    "name": name,
                    "status": "MULTIPLE_FACES",
                }
            )

            continue

        # Exactly one face
        face = faces[0]

        # -------------------------------------------------
        # Quality evaluation
        # -------------------------------------------------

        result = evaluate_quality(
            image,
            face
        )

        print()
        print("Quality measurements:")
        print(f"  Face width:   {result.face_width:.2f} px")
        print(f"  Face height:  {result.face_height:.2f} px")
        print(f"  Brightness:   {result.brightness:.2f}")
        print(f"  Blur score:   {result.blur_score:.2f}")

        print()
        print("Quality checks:")

        print(
            f"  Face size:    "
            f"{'PASS' if result.face_size_ok else 'FAIL'}"
        )

        print(
            f"  Brightness:   "
            f"{'PASS' if result.brightness_ok else 'FAIL'}"
        )

        print(
            f"  Blur:         "
            f"{'PASS' if result.blur_ok else 'FAIL'}"
        )

        print(
            f"  Pose:         "
            f"{'PASS' if result.pose_ok else 'FAIL'}"
        )

        status = (
            "ACCEPT_FOR_NEXT_STAGE"
            if result.quality_ok
            else "RECAPTURE"
        )

        print()
        print(f"QUALITY STATUS: {status}")

        results.append(
            {
                "name": name,
                "status": status,
                "face_width": result.face_width,
                "face_height": result.face_height,
                "brightness": result.brightness,
                "blur_score": result.blur_score,
                "face_size_ok": result.face_size_ok,
                "brightness_ok": result.brightness_ok,
                "blur_ok": result.blur_ok,
                "pose_ok": result.pose_ok,
            }
        )

    # -----------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------

    print()
    print()
    print("=" * 80)
    print("STAGE 7 SUMMARY")
    print("=" * 80)

    total = len(results)

    accepted = sum(
        1
        for r in results
        if r.get("status") == "ACCEPT_FOR_NEXT_STAGE"
    )

    recapture = sum(
        1
        for r in results
        if r.get("status") == "RECAPTURE"
    )

    multiple_faces = sum(
        1
        for r in results
        if r.get("status") == "MULTIPLE_FACES"
    )

    no_face = sum(
        1
        for r in results
        if r.get("status") == "NO_FACE"
    )

    file_errors = sum(
        1
        for r in results
        if r.get("status") in {
            "FILE_NOT_FOUND",
            "READ_ERROR",
        }
    )

    print()
    print(f"Total images tested:       {total}")
    print(f"Accepted:                  {accepted}")
    print(f"Recapture required:        {recapture}")
    print(f"Multiple faces:            {multiple_faces}")
    print(f"No face:                   {no_face}")
    print(f"File/read errors:          {file_errors}")

    print()
    print("=" * 80)

    if total > 0 and accepted == total:

        print("STAGE 7 STATUS: PASS")

    else:

        print("STAGE 7 STATUS: REVIEW")

    print("=" * 80)

    print()
    print("IMPORTANT:")
    print(
        "These results are an engineering experiment only."
    )
    print(
        "They are NOT sufficient for production quality-threshold calibration."
    )
    print(
        "Production calibration requires a representative evaluation dataset."
    )


if __name__ == "__main__":
    main()