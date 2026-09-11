"""
Stage 9A: LFW verification score generation.

Calibration-only path:

    LFW image
        -> SCRFD detection
        -> five-point alignment
        -> ArcFace R50 embedding
        -> L2-normalized embedding

Quality metrics are calculated and recorded but are NOT used as a
rejection gate during LFW calibration.

The production FaceVerificationPipeline remains unchanged.

No verification threshold is applied here.
"""

import csv
import os
import sys
import numpy as np
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.faceverify.detector import SCRFDDetector
from src.faceverify.quality import evaluate_quality
from src.faceverify.alignment import align_face
from src.faceverify.recognizer import ArcFaceRecognizer
from src.faceverify.similarity import cosine_similarity


LFW_ROOT = PROJECT_ROOT / "data" / "calibration" / "lfw" / "lfw"
PAIRS_FILE = PROJECT_ROOT / "data" / "calibration" / "pairs" / "pairs.txt"
RESULTS_DIR = PROJECT_ROOT / "data" / "calibration" / "results"
OUTPUT_FILE = RESULTS_DIR / "lfw_scores.csv"


def image_path(identity, image_number):
    """Construct and validate an LFW image path."""

    filename = f"{identity}_{int(image_number):04d}.jpg"

    path = LFW_ROOT / identity / filename

    if not path.is_file():
        raise FileNotFoundError(
            f"LFW image not found:\n{path}"
        )

    return path


def parse_pairs():
    """
    Parse the official LFW pairs.txt file.

    Returns:
        List of:
            (fold, image_a, image_b, label)

        label:
            1 = genuine
            0 = impostor
    """

    if not PAIRS_FILE.is_file():
        raise FileNotFoundError(
            f"Pairs file not found:\n{PAIRS_FILE}"
        )

    lines = PAIRS_FILE.read_text(
        encoding="utf-8"
    ).splitlines()

    if not lines:
        raise ValueError("pairs.txt is empty.")

    header = lines[0].split()

    if len(header) != 2:
        raise ValueError(
            f"Unexpected LFW header: {lines[0]}"
        )

    folds = int(header[0])
    pairs_per_fold = int(header[1])

    expected_pairs = folds * pairs_per_fold

    pair_lines = lines[1:]

    if len(pair_lines) != expected_pairs * 2:
        raise ValueError(
            f"Unexpected number of pair lines. "
            f"Expected {expected_pairs * 2}, "
            f"got {len(pair_lines)}."
        )

    pairs = []
    index = 0

    for fold in range(1, folds + 1):

        # ---------------------------------------------------------
        # Genuine pairs
        # ---------------------------------------------------------

        for _ in range(pairs_per_fold):

            parts = pair_lines[index].split()
            index += 1

            if len(parts) != 3:
                raise ValueError(
                    f"Invalid genuine pair line: "
                    f"{pair_lines[index - 1]}"
                )

            identity = parts[0]
            number_a = parts[1]
            number_b = parts[2]

            path_a = image_path(identity, number_a)
            path_b = image_path(identity, number_b)

            pairs.append(
                (
                    fold,
                    path_a,
                    path_b,
                    1,
                )
            )

        # ---------------------------------------------------------
        # Impostor pairs
        # ---------------------------------------------------------

        for _ in range(pairs_per_fold):

            parts = pair_lines[index].split()
            index += 1

            if len(parts) != 4:
                raise ValueError(
                    f"Invalid impostor pair line: "
                    f"{pair_lines[index - 1]}"
                )

            identity_a = parts[0]
            number_a = parts[1]

            identity_b = parts[2]
            number_b = parts[3]

            path_a = image_path(identity_a, number_a)
            path_b = image_path(identity_b, number_b)

            pairs.append(
                (
                    fold,
                    path_a,
                    path_b,
                    0,
                )
            )

    return pairs


def generate_embedding(
    image_path_value,
    detector,
    recognizer,
):
    """
    Generate an ArcFace embedding for one LFW image.

    IMPORTANT:
        LFW calibration does not enforce the production
        quality gate. Quality is measured and reported only.
    """

    image = cv2.imread(
        str(image_path_value)
    )

    if image is None:
        raise FileNotFoundError(
            f"Could not read image:\n{image_path_value}"
        )

    # -------------------------------------------------------------
    # Face detection
    # -------------------------------------------------------------

    faces = detector.detect(
        str(image_path_value)
    )

    if len(faces) == 0:
    	raise ValueError(
        	f"No face detected:\n{image_path_value}"
    )

    if len(faces) == 1:
    	face = faces[0]

    else:
    	# LFW calibration policy:
    	# select the largest detected face as the primary subject.
    	face = max(
        	faces,
        	key=lambda f: (
            	f.bbox[2] - f.bbox[0]
        	) * (
            	f.bbox[3] - f.bbox[1]
        	),
    )
    # -------------------------------------------------------------
    # Quality assessment
    # -------------------------------------------------------------

    quality = evaluate_quality(
        image,
        face,
    )

    # Quality is intentionally NOT used as a rejection gate here.

    # -------------------------------------------------------------
    # Alignment
    # -------------------------------------------------------------

    aligned = align_face(
        image,
        face,
    )

    # -------------------------------------------------------------
    # ArcFace embedding
    # -------------------------------------------------------------

    embedding = recognizer.get_embedding(
        aligned
    )

    return embedding, quality


def main():

    print("=" * 70)
    print("STAGE 9A — LFW SCORE GENERATION")
    print("=" * 70)

    print()
    print(f"LFW directory: {LFW_ROOT}")
    print(f"Pairs file:    {PAIRS_FILE}")

    # -------------------------------------------------------------
    # Parse pairs
    # -------------------------------------------------------------

    print()
    print("Parsing LFW verification pairs...")

    pairs = parse_pairs()

    genuine_count = sum(
        1 for pair in pairs if pair[3] == 1
    )

    impostor_count = sum(
        1 for pair in pairs if pair[3] == 0
    )

    print(f"Pairs loaded: {len(pairs)}")
    print(f"Genuine pairs:  {genuine_count}")
    print(f"Impostor pairs: {impostor_count}")

    # -------------------------------------------------------------
    # Unique images
    # -------------------------------------------------------------

    unique_images = set()

    for _, image_a, image_b, _ in pairs:
        unique_images.add(image_a)
        unique_images.add(image_b)

    print()
    print(
        f"Unique images requiring processing: "
        f"{len(unique_images)}"
    )

    # -------------------------------------------------------------
    # Load calibration components
    # -------------------------------------------------------------

    print()
    print("Loading calibration components...")

    detector = SCRFDDetector(
        os.path.join(
            PROJECT_ROOT,
            "models",
            "buffalo_m",
            "det_2.5g.onnx",
        )
    )

    recognizer = ArcFaceRecognizer()

    print("SCRFD detector loaded.")
    print("ArcFace R50 loaded.")

    # -------------------------------------------------------------
    # Generate embeddings
    # -------------------------------------------------------------
    EMBEDDINGS_DIR = RESULTS_DIR / "embeddings"

    EMBEDDINGS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    embedding_cache = {}
    failed_images = {}

    print()
    print("Generating embeddings...")

    total_images = len(unique_images)

    for index, image_path_value in enumerate(
        sorted(unique_images),
        start=1,
    ):

        print(
            f"[{index}/{total_images}] "
            f"{image_path_value.name}"
        )
        cache_file = (
            EMBEDDINGS_DIR
            / f"{image_path_value.stem}.npy"
        )

        if cache_file.exists():
            embedding_cache[image_path_value] = np.load(
                cache_file
            )

            continue

        try:
            embedding, _ = generate_embedding(
                image_path_value,
                detector,
                recognizer,
            )

            embedding_cache[image_path_value] = embedding
            np.save(
                cache_file,
                embedding,
            )

        except (ValueError, FileNotFoundError) as exc:
            failed_images[image_path_value] = str(exc)

            print(
                f"  SKIPPED: {exc}"
            )

    print()
    print(
        f"Embeddings generated: {len(embedding_cache)}"
    )

    print(
        f"Images skipped: {len(failed_images)}"
    )
    
    # -------------------------------------------------------------
    # Calculate similarities
    # -------------------------------------------------------------

    print()
    print("Calculating pair similarities...")

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow(
            [
                "fold",
                "image_a",
                "image_b",
                "label",
                "similarity",
            ]
        )

        skipped_pairs = 0
        scored_pairs = 0

        for fold, image_a, image_b, label in pairs:

            if (
                image_a not in embedding_cache
                or image_b not in embedding_cache
            ):
                skipped_pairs += 1
                continue

            embedding_a = embedding_cache[image_a]
            embedding_b = embedding_cache[image_b]

            similarity = cosine_similarity(
                embedding_a,
                embedding_b,
            )

            writer.writerow(
                [
                    fold,
                    str(image_a.relative_to(PROJECT_ROOT)),
                    str(image_b.relative_to(PROJECT_ROOT)),
                    label,
                    f"{similarity:.8f}",
                ]
            )

            scored_pairs += 1
    # -------------------------------------------------------------
    # Final result
    # -------------------------------------------------------------

    print()
    print("=" * 70)
    print("STAGE 9A RESULT")
    print("=" * 70)

    print(f"Total pairs:        {len(pairs)}")
    print(f"Genuine pairs:      {genuine_count}")
    print(f"Impostor pairs:     {impostor_count}")
    print(f"Unique images:      {total_images}")
    print(f"Embeddings created: {len(embedding_cache)}")
    print(f"Images skipped:     {len(failed_images)}")
    print(f"Pairs scored:       {scored_pairs}")
    print(f"Pairs skipped:      {skipped_pairs}")
    print()
    print("Results saved to:")
    print(OUTPUT_FILE)

    print()
    print("STAGE 9A STATUS: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()