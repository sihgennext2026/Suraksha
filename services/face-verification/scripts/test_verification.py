"""
End-to-end face verification test.

Document:
    perspective-corrected document
        -> portrait extraction
        -> face detection
        -> 5-point alignment
        -> ArcFace embedding

Live:
    live image
        -> face detection
        -> 5-point alignment
        -> ArcFace embedding

Finally:
    document embedding
        -> live embedding
        -> cosine similarity
        -> threshold decision
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

from faceverify.detector import SCRFDDetector
from faceverify.document_portrait import DocumentPortraitExtractor
from faceverify.alignment import align_face
from faceverify.recognizer import ArcFaceRecognizer


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DETECTOR_MODEL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "models",
    "buffalo_m",
    "det_2.5g.onnx",
)

THRESHOLD = 0.225


# ---------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------

def generate_live_embedding(
    image_path,
    detector,
    recognizer,
):
    print()
    print("--- LIVE IMAGE ---")
    print("Image:", image_path)

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Could not load live image: {image_path}"
        )

    print("Original image shape:", image.shape)

    faces = detector.detect(image_path)

    print("Faces detected:", len(faces))

    if len(faces) != 1:
        raise ValueError(
            "Live image must contain exactly one face."
        )

    print("Running five-point alignment...")

    aligned = align_face(
        image,
        faces[0],
    )

    print("Aligned image shape:", aligned.shape)

    print("Generating ArcFace embedding...")

    embedding = recognizer.get_embedding(
        aligned
    )

    print(
        "Embedding shape:",
        embedding.shape,
    )

    print(
        "Embedding norm:",
        f"{np.linalg.norm(embedding):.6f}",
    )

    return embedding


def generate_document_embedding(
    image_path,
    detector,
    recognizer,
):
    print()
    print("--- DOCUMENT IMAGE ---")
    print("Image:", image_path)

    extractor = DocumentPortraitExtractor(
        detector
    )

    result = extractor.extract(
        image_path
    )

    print("Portrait extraction:", result.success)
    print("Reason:", result.reason)
    print("Candidates:", len(result.candidates))

    if not result.success:
        raise ValueError(
            f"Document portrait extraction failed: "
            f"{result.reason}"
        )

    selected = result.selected

    print(
        "Selected candidate:",
        selected.face_index,
    )

    print(
        "Crop shape:",
        selected.crop.shape,
    )

    # The portrait extractor has already produced
    # the cropped portrait. We now run face detection
    # on that crop before alignment and recognition.

    cropped = selected.crop

    # Save the extracted portrait temporarily because
    # SCRFDDetector.detect() expects an image path.
    temp_crop_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "test",
        "portrait_extraction",
        "_verification_portrait.jpg",
    )

    os.makedirs(
        os.path.dirname(temp_crop_path),
        exist_ok=True,
    )

    cv2.imwrite(
        temp_crop_path,
        cropped,
    )

    faces = detector.detect(
        temp_crop_path
    )
    print(
        "Faces detected in portrait crop:",
        len(faces),
    )

    if len(faces) != 1:
        raise ValueError(
            "Document portrait crop must contain exactly one face."
        )

    print("Running five-point alignment...")

    aligned = align_face(
        cropped,
        faces[0],
    )

    print(
        "Aligned image shape:",
        aligned.shape,
    )

    print("Generating ArcFace embedding...")

    embedding = recognizer.get_embedding(
        aligned
    )

    print(
        "Embedding shape:",
        embedding.shape,
    )

    print(
        "Embedding norm:",
        f"{np.linalg.norm(embedding):.6f}",
    )

    return embedding


# ---------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------

def cosine_similarity(
    a,
    b,
):
    return np.dot(a, b) / (
        np.linalg.norm(a)
        * np.linalg.norm(b)
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    if len(sys.argv) != 3:
        print(
            'Usage: python scripts\\test_verification.py '
            '"DOCUMENT_PATH" "LIVE_PATH"'
        )
        sys.exit(1)

    document_path = sys.argv[1]
    live_path = sys.argv[2]

    print("=" * 70)
    print("END-TO-END FACE VERIFICATION TEST")
    print("=" * 70)

    print()
    print("Loading SCRFD detector...")

    detector = SCRFDDetector(
        DETECTOR_MODEL
    )

    print("Loading ArcFace R50...")

    recognizer = ArcFaceRecognizer()

    # -----------------------------------------------------
    # Document
    # -----------------------------------------------------

    document_embedding = (
        generate_document_embedding(
            document_path,
            detector,
            recognizer,
        )
    )

    # -----------------------------------------------------
    # Live
    # -----------------------------------------------------

    live_embedding = (
        generate_live_embedding(
            live_path,
            detector,
            recognizer,
        )
    )

    # -----------------------------------------------------
    # Verification
    # -----------------------------------------------------

    print()
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    score = cosine_similarity(
        document_embedding,
        live_embedding,
    )

    print()
    print(
        f"Cosine similarity: {score:.6f}"
    )

    print(
        f"Threshold:         {THRESHOLD:.6f}"
    )

    if score >= THRESHOLD:
        decision = "MATCH"
    else:
        decision = "NO MATCH"

    print(
        f"Decision:           {decision}"
    )

    print()
    print("=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()