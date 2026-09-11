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

IMAGE_PATHS = [
    r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI1.jpg",
    r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI2.jpg",
    r"C:\Users\josep\OneDrive\Pictures\Camera Roll\FDTI3.jpg",
]


def main():
    print("Loading SCRFD detector...")
    detector = SCRFDDetector(MODEL_PATH)

    for image_path in IMAGE_PATHS:

        print("\n" + "=" * 70)
        print(f"IMAGE: {os.path.basename(image_path)}")
        print("=" * 70)

        image = cv2.imread(image_path)

        if image is None:
            print("ERROR: Could not read image")
            continue

        faces = detector.detect(image_path)

        print(f"Faces detected: {len(faces)}")

        if len(faces) != 1:
            print("Skipping quality measurement.")
            continue

        face = faces[0]

        result = evaluate_quality(image, face)

        print("\nQuality measurements:")
        print(f"  Face width:   {result.face_width:.2f} px")
        print(f"  Face height:  {result.face_height:.2f} px")
        print(f"  Brightness:   {result.brightness:.2f}")
        print(f"  Blur score:   {result.blur_score:.2f}")
        print(f"  Yaw proxy:    {result.yaw_proxy:.4f}")
        print(f"  Roll:         {result.roll:.2f}°")

        print("\nQuality checks:")
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

        print(
            "\nQUALITY STATUS: "
            f"{'ACCEPT_FOR_NEXT_STAGE' if result.quality_ok else 'RECAPTURE'}"
        )


if __name__ == "__main__":
    main()