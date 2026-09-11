"""
Test automatic portrait extraction from a
perspective-corrected document.
"""

import os
import sys

import cv2

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.faceverify.detector import SCRFDDetector
from src.faceverify.portrait_crop import crop_portrait


DETECTOR_MODEL = os.path.join(
    PROJECT_ROOT,
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)


def main():

    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            'python scripts\\test_portrait_crop.py "DOCUMENT_IMAGE"'
        )
        sys.exit(1)

    image_path = sys.argv[1]

    print("=" * 70)
    print("PORTRAIT CROPPING TEST")
    print("=" * 70)

    print()
    print("Document image:")
    print(image_path)

    print()
    print("Loading SCRFD detector...")

    detector = SCRFDDetector(
        DETECTOR_MODEL
    )

    print("SCRFD: LOADED")

    # ---------------------------------------------------------
    # READ ORIGINAL IMAGE
    # ---------------------------------------------------------

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    print()
    print(f"Original image shape: {image.shape}")

    # ---------------------------------------------------------
    # AUTOMATIC PORTRAIT CROP
    # ---------------------------------------------------------

    print()
    print("[1] FACE DETECTION + PORTRAIT CROPPING")

    output_path = os.path.join(
    	PROJECT_ROOT,
    	"experiments",
    	"auto_portrait_crop.jpg",
    )

    cropped_face, bbox, crop_box = crop_portrait(
    	image_path,
    	detector,
    	output_path,
    	padding_ratio=0.20,
    )

    print()
    print(f"Detected face bbox: {bbox}")
    print(f"Final crop box:      {crop_box}")
    print(f"Cropped image shape: {cropped_face.shape}")

    # ---------------------------------------------------------
    # SAVE RESULT
    # ---------------------------------------------------------

    experiments_dir = os.path.join(
        PROJECT_ROOT,
        "experiments",
    )

    os.makedirs(
        experiments_dir,
        exist_ok=True,
    )

    
    print()
    print(f"Saved automatic portrait crop:")
    print(output_path)

    print()
    print("=" * 70)
    print("PORTRAIT CROPPING STATUS: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()