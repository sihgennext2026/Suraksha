import os
import sys

import cv2

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.faceverify.detector import SCRFDDetector


DETECTOR_MODEL = os.path.join(
    PROJECT_ROOT,
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)


def main():

    if len(sys.argv) != 2:
        print(
            'Usage: python scripts\\visualize_document_faces.py "IMAGE"'
        )
        sys.exit(1)

    image_path = sys.argv[1]

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    detector = SCRFDDetector(
        DETECTOR_MODEL
    )

    faces = detector.detect(image_path)

    print(f"Faces detected: {len(faces)}")

    for i, face in enumerate(faces, start=1):

        x1, y1, x2, y2 = [
            int(round(v))
            for v in face.bbox
        ]

        print()
        print(f"FACE {i}")
        print(f"Bounding box: {[x1, y1, x2, y2]}")
        print(f"Width:  {x2 - x1}")
        print(f"Height: {y2 - y1}")

        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            4,
        )

        cv2.putText(
            image,
            f"FACE {i}",
            (x1, max(30, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            3,
        )

    output_path = os.path.join(
        PROJECT_ROOT,
        "experiments",
        "document_face_detections.jpg",
    )

    cv2.imwrite(
        output_path,
        image,
    )

    print()
    print(f"Saved visualization:")
    print(output_path)


if __name__ == "__main__":
    main()