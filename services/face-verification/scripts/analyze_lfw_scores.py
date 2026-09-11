"""
Stage 9B: Analyze LFW verification scores.

Reads the Stage 9A LFW score CSV and reports:
- genuine/impostor counts
- minimum, maximum, mean, median
- percentile statistics
- score overlap
- candidate threshold performance

No production threshold is selected automatically.
"""

import csv
import os
import sys
from pathlib import Path

import numpy as np


# -------------------------------------------------------------
# Project paths
# -------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESULTS_DIR = (
    PROJECT_ROOT
    / "data"
    / "calibration"
    / "results"
)

INPUT_FILE = (
    RESULTS_DIR
    / "lfw_scores.csv"
)


# -------------------------------------------------------------
# Load scores
# -------------------------------------------------------------

def load_scores():
    """Load genuine and impostor cosine similarity scores."""

    if not INPUT_FILE.is_file():
        raise FileNotFoundError(
            f"LFW score file not found:\n{INPUT_FILE}"
        )

    genuine = []
    impostor = []

    with INPUT_FILE.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        required_columns = {
            "label",
            "similarity",
        }

        if not required_columns.issubset(
            reader.fieldnames or []
        ):
            raise ValueError(
                "CSV is missing required columns: "
                "label, similarity"
            )

        for row in reader:

            label = int(row["label"])
            similarity = float(
                row["similarity"]
            )

            if label == 1:
                genuine.append(similarity)

            elif label == 0:
                impostor.append(similarity)

    if not genuine:
        raise ValueError(
            "No genuine scores found."
        )

    if not impostor:
        raise ValueError(
            "No impostor scores found."
        )

    return (
        np.asarray(genuine, dtype=np.float64),
        np.asarray(impostor, dtype=np.float64),
    )


# -------------------------------------------------------------
# Statistics
# -------------------------------------------------------------

def print_statistics(
    name,
    scores,
):
    """Print descriptive statistics."""

    percentiles = [
        1,
        5,
        10,
        25,
        50,
        75,
        90,
        95,
        99,
    ]

    print()
    print(name)
    print("-" * 70)

    print(f"Count:  {len(scores)}")
    print(f"Min:    {np.min(scores):.6f}")
    print(f"Max:    {np.max(scores):.6f}")
    print(f"Mean:   {np.mean(scores):.6f}")
    print(f"Median: {np.median(scores):.6f}")
    print(f"Std:    {np.std(scores):.6f}")

    print()
    print("Percentiles:")

    for percentile in percentiles:

        value = np.percentile(
            scores,
            percentile,
        )

        print(
            f"  P{percentile:02d}: "
            f"{value:.6f}"
        )


# -------------------------------------------------------------
# Threshold analysis
# -------------------------------------------------------------

def threshold_metrics(
    genuine,
    impostor,
    threshold,
):
    """
    Evaluate a similarity threshold.

    similarity >= threshold
        -> predicted MATCH

    similarity < threshold
        -> predicted NO MATCH
    """

    genuine_rejected = np.sum(
        genuine < threshold
    )

    impostor_accepted = np.sum(
        impostor >= threshold
    )

    false_rejection_rate = (
        genuine_rejected
        / len(genuine)
    )

    false_acceptance_rate = (
        impostor_accepted
        / len(impostor)
    )

    true_acceptance_rate = (
        1.0
        - false_rejection_rate
    )

    return (
        false_acceptance_rate,
        false_rejection_rate,
        true_acceptance_rate,
    )


def analyze_thresholds(
    genuine,
    impostor,
):
    """Evaluate a range of candidate thresholds."""

    print()
    print("=" * 70)
    print("CANDIDATE THRESHOLD ANALYSIS")
    print("=" * 70)

    print()
    print(
        "Threshold    FAR        FRR        TAR"
    )
    print("-" * 70)

    thresholds = np.arange(
        0.20,
        0.951,
        0.05,
    )

    for threshold in thresholds:

        far, frr, tar = threshold_metrics(
            genuine,
            impostor,
            threshold,
        )

        print(
            f"{threshold:9.2f}    "
            f"{far:8.4%}   "
            f"{frr:8.4%}   "
            f"{tar:8.4%}"
        )


# -------------------------------------------------------------
# Main
# -------------------------------------------------------------

def main():

    print("=" * 70)
    print("STAGE 9B — LFW SCORE ANALYSIS")
    print("=" * 70)

    print()
    print(f"Input file:")
    print(INPUT_FILE)

    print()
    print("Loading scores...")

    genuine, impostor = load_scores()

    print(
        f"Genuine scores:  {len(genuine)}"
    )

    print(
        f"Impostor scores: {len(impostor)}"
    )

    print_statistics(
        "GENUINE SCORES",
        genuine,
    )

    print_statistics(
        "IMPOSTOR SCORES",
        impostor,
    )

    analyze_thresholds(
        genuine,
        impostor,
    )

    print()
    print("=" * 70)
    print("STAGE 9B STATUS: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()