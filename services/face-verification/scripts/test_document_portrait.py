import sys
from pathlib import Path

import cv2

sys.path.insert(0, "src")

from faceverify.detector import SCRFDDetector
from faceverify.document_portrait import DocumentPortraitExtractor


IMAGE_PATH = None
MODEL_PATH = r"models\buffalo_m\det_2.5g.onnx"

OUTPUT_DIR = Path("data/test/portrait_extraction")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    if len(sys.argv) != 2:
        print(
            'Usage: python scripts\\test_document_portrait.py "PATH_TO_IMAGE"'
        )
        sys.exit(1)

    image_path = sys.argv[1]
    print("=" * 60)
    print("DOCUMENT PORTRAIT EXTRACTION TEST")
    print("=" * 60)
    print("TEST IMAGE:", image_path)

    detector = SCRFDDetector(MODEL_PATH)

    extractor = DocumentPortraitExtractor(detector)
    
    result = extractor.extract(image_path)

    

    print()
    print("Success:", result.success)
    print("Reason:", result.reason)
    print("Candidates:", len(result.candidates))

    if not result.success:
        return

    print()

    for candidate in result.candidates:
        print(
            f"Candidate {candidate.face_index}: "
            f"face_area={candidate.face_area:.2f}, "
            f"confidence={candidate.confidence:.4f}, "
            f"face_bbox={candidate.face_bbox}, "
            f"crop_bbox={candidate.crop_bbox}"
        )

    print()

    # Save every candidate for visual inspection.
    for rank, candidate in enumerate(result.candidates):
        output_path = OUTPUT_DIR / f"candidate_{rank}.jpg"
        cv2.imwrite(str(output_path), candidate.crop)

        print(
            f"Saved candidate {rank}: "
            f"{output_path}"
        )

    selected_path = OUTPUT_DIR / "SELECTED_PRIMARY_PORTRAIT.jpg"

    cv2.imwrite(
        str(selected_path),
        result.selected.crop,
    )

    print()
    print("SELECTED CANDIDATE:", result.selected.face_index)
    print("SELECTED PORTRAIT:", selected_path)
    print()
    print("Open SELECTED_PRIMARY_PORTRAIT.jpg and inspect it.")


if __name__ == "__main__":
    main()