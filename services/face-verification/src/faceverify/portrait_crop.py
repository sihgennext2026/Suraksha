
"""
Document portrait extraction.

Detects all faces in a document image and selects the
largest sufficiently-sized face as the document portrait.

This is an engineering POC rule.
"""

import cv2

from .detector import SCRFDDetector


def crop_portrait(
    image_path,
    detector: SCRFDDetector,
    output_path,
    min_face_width=50.0,
    min_face_height=70.0,
    padding_ratio=0.20,
    return_face=False,
):
    """
    Detect faces and select the largest suitable face.

    Returns:
        cropped_face
        selected_bbox
        crop_box

    With return_face=True a fourth value, the selected face object itself, is
    returned before the bbox. Quality scoring and five-point alignment need the
    detector's landmarks, which the bbox alone does not carry; re-detecting to
    recover them could select a different face than the one that was cropped.
    The flag defaults to False so existing three-value callers are unaffected.
    """

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Could not read image: {image_path}"
        )

    image_height, image_width = image.shape[:2]

    # ---------------------------------------------------------
    # FACE DETECTION
    # ---------------------------------------------------------

    faces = detector.detect(image_path)

    print(f"Faces detected: {len(faces)}")

    if len(faces) == 0:
        raise RuntimeError(
            "No face detected in document image."
        )

    # ---------------------------------------------------------
    # FIND SUITABLE FACE CANDIDATES
    # ---------------------------------------------------------

    candidates = []

    for index, face in enumerate(faces, start=1):

        x1, y1, x2, y2 = face.bbox

        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)
        area = width * height

        print()
        print(f"FACE {index}")
        print(f"Bounding box: {face.bbox}")
        print(f"Width:  {width:.2f}")
        print(f"Height: {height:.2f}")
        print(f"Area:   {area:.2f}")

        if (
            width >= min_face_width
            and height >= min_face_height
        ):
            print("Candidate: YES")
            candidates.append(
                (face, width, height, area)
            )
        else:
            print("Candidate: NO - too small")

    if not candidates:
        raise RuntimeError(
            "No suitable portrait face detected."
        )

    # ---------------------------------------------------------
    # SELECT LARGEST FACE
    # ---------------------------------------------------------

    selected_face, width, height, area = max(
        candidates,
        key=lambda item: item[3]
    )

    print()
    print("=" * 70)
    print("SELECTED DOCUMENT PORTRAIT")
    print("=" * 70)

    print(f"Bounding box: {selected_face.bbox}")
    print(f"Width:  {width:.2f}")
    print(f"Height: {height:.2f}")
    print(f"Area:   {area:.2f}")

    # ---------------------------------------------------------
    # ADD PADDING
    # ---------------------------------------------------------

    x1, y1, x2, y2 = selected_face.bbox

    face_width = x2 - x1
    face_height = y2 - y1

    padding_x = face_width * padding_ratio
    padding_y = face_height * padding_ratio

    crop_x1 = int(max(0, x1 - padding_x))
    crop_y1 = int(max(0, y1 - padding_y))
    crop_x2 = int(min(image_width, x2 + padding_x))
    crop_y2 = int(min(image_height, y2 + padding_y))

    if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
        raise RuntimeError(
            "Invalid crop coordinates."
        )

    cropped_face = image[
        crop_y1:crop_y2,
        crop_x1:crop_x2
    ]

    if cropped_face.size == 0:
        raise RuntimeError(
            "Portrait crop is empty."
        )

    # ---------------------------------------------------------
    # SAVE CROP
    # ---------------------------------------------------------

    if not cv2.imwrite(output_path, cropped_face):
        raise RuntimeError(
            f"Could not save portrait crop: {output_path}"
        )

    print()
    print(
        f"Crop box: "
        f"({crop_x1}, {crop_y1}, "
        f"{crop_x2}, {crop_y2})"
    )

    print(
        f"Cropped portrait shape: "
        f"{cropped_face.shape}"
    )

    print(
        f"Saved portrait crop: "
        f"{output_path}"
    )

    crop_box = (
        crop_x1,
        crop_y1,
        crop_x2,
        crop_y2
    )

    if return_face:
        return (
            cropped_face,
            selected_face,
            selected_face.bbox,
            crop_box
        )

    return (
        cropped_face,
        selected_face.bbox,
        crop_box
    )

