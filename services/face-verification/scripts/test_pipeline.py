"""
Stage 8 — Reusable pipeline verification test.

Usage:
    python scripts\test_pipeline.py "IMAGE_A" "IMAGE_B"
"""

import os
import sys

# Add project root to Python import path.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from src.faceverify.pipeline import FaceVerificationPipeline


def main():

    if len(sys.argv) != 3:
        print()
        print("Usage:")
        print(
            '    python scripts\\test_pipeline.py "IMAGE_A" "IMAGE_B"'
        )
        print()
        sys.exit(1)

    image_a = sys.argv[1]
    image_b = sys.argv[2]

    print("=" * 70)
    print("STAGE 8 — REUSABLE PIPELINE TEST")
    print("=" * 70)

    print()
    print("Loading reusable verification pipeline...")

    pipeline = FaceVerificationPipeline()

    print("Pipeline loaded successfully.")

    print()
    print("Running verification...")
    print()

    result = pipeline.verify(
        image_a,
        image_b,
    )

    print()
    print("=" * 70)
    print("STAGE 8 RESULT")
    print("=" * 70)

    print()
    print(f"Image A:    {result.image_a}")
    print(f"Image B:    {result.image_b}")
    print(f"Similarity: {result.similarity:.6f}")

    print()
    print("STAGE 8 STATUS: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()