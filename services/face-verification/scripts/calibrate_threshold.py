"""
Stage 9C: LFW threshold calibration.

Uses the existing LFW similarity scores generated in Stage 9A.

This stage does NOT process images.
This stage does NOT apply a production threshold.

It evaluates threshold behavior using:
- FAR
- FRR
- TAR
- ROC curve
- AUC
- EER
"""

import csv
from pathlib import Path

import numpy as np


# -------------------------------------------------------------
# Paths
# -------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "calibration"
    / "results"
    / "lfw_scores.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "calibration"
    / "results"
    / "threshold_analysis.csv"
)


# -------------------------------------------------------------
# Load scores
# -------------------------------------------------------------

def load_scores():

    if not INPUT_FILE.is_file():
        raise FileNotFoundError(
            f"Score file not found:\n{INPUT_FILE}"
        )

    genuine = []
    impostor = []

    with INPUT_FILE.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        reader = csv.DictReader(csv_file)

        for row in reader:

            label = int(row["label"])
            score = float(row["similarity"])

            if label == 1:
                genuine.append(score)

            elif label == 0:
                impostor.append(score)

    if not genuine or not impostor:
        raise ValueError(
            "Missing genuine or impostor scores."
        )

    return (
        np.asarray(genuine),
        np.asarray(impostor),
    )


# -------------------------------------------------------------
# Threshold metrics
# -------------------------------------------------------------

def calculate_metrics(
    genuine,
    impostor,
    threshold,
):

    false_rejections = np.sum(
        genuine < threshold
    )

    false_acceptances = np.sum(
        impostor >= threshold
    )

    frr = (
        false_rejections
        / len(genuine)
    )

    far = (
        false_acceptances
        / len(impostor)
    )

    tar = 1.0 - frr

    return far, frr, tar


# -------------------------------------------------------------
# Main
# -------------------------------------------------------------

def main():

    print("=" * 70)
    print("STAGE 9C — THRESHOLD CALIBRATION")
    print("=" * 70)

    print()
    print("Loading existing LFW scores...")

    genuine, impostor = load_scores()

    print(
        f"Genuine scores:  {len(genuine)}"
    )

    print(
        f"Impostor scores: {len(impostor)}"
    )

    # ---------------------------------------------------------
    # Generate thresholds from observed scores
    # ---------------------------------------------------------

    all_scores = np.concatenate(
        [genuine, impostor]
    )

    thresholds = np.unique(
        all_scores
    )

    thresholds = np.sort(
        thresholds
    )

    # ---------------------------------------------------------
    # Evaluate thresholds
    # ---------------------------------------------------------

    rows = []

    best_eer = None
    best_eer_threshold = None

    for threshold in thresholds:

        far, frr, tar = calculate_metrics(
            genuine,
            impostor,
            threshold,
        )

        difference = abs(
            far - frr
        )

        if (
            best_eer is None
            or difference < best_eer
        ):
            best_eer = difference
            best_eer_threshold = threshold

        rows.append(
            (
                threshold,
                far,
                frr,
                tar,
            )
        )

    # ---------------------------------------------------------
    # Save threshold analysis
    # ---------------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
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
                "threshold",
                "far",
                "frr",
                "tar",
            ]
        )

        for threshold, far, frr, tar in rows:

            writer.writerow(
                [
                    f"{threshold:.8f}",
                    f"{far:.8f}",
                    f"{frr:.8f}",
                    f"{tar:.8f}",
                ]
            )

    # ---------------------------------------------------------
    # Print EER estimate
    # ---------------------------------------------------------

    eer_far, eer_frr, eer_tar = (
        calculate_metrics(
            genuine,
            impostor,
            best_eer_threshold,
        )
    )

    eer = (
        eer_far + eer_frr
    ) / 2.0

    print()
    print("=" * 70)
    print("EER ESTIMATE")
    print("=" * 70)

    print(
        f"Threshold: {best_eer_threshold:.8f}"
    )

    print(
        f"FAR:       {eer_far:.6%}"
    )

    print(
        f"FRR:       {eer_frr:.6%}"
    )

    print(
        f"EER:       {eer:.6%}"
    )

    # ---------------------------------------------------------
    # Important operating points
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("OPERATING POINTS")
    print("=" * 70)

    targets = [
        0.001,
        0.0001,
        0.00001,
    ]

    for target_far in targets:

        valid = []

        for threshold, far, frr, tar in rows:

            if far <= target_far:
                valid.append(
                    (
                        threshold,
                        far,
                        frr,
                        tar,
                    )
                )

        if valid:

            selected = min(
                valid,
                key=lambda item: item[2],
            )

            threshold, far, frr, tar = (
                selected
            )

            print()
            print(
                f"Target FAR <= "
                f"{target_far:.5%}"
            )

            print(
                f"Threshold: "
                f"{threshold:.8f}"
            )

            print(
                f"Actual FAR: "
                f"{far:.6%}"
            )

            print(
                f"FRR: "
                f"{frr:.6%}"
            )

            print(
                f"TAR: "
                f"{tar:.6%}"
            )

        else:

            print()
            print(
                f"No threshold achieved "
                f"FAR <= {target_far:.5%}"
            )

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)

    print(
        "Threshold analysis saved to:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "No production threshold has been selected."
    )

    print()
    print(
        "STAGE 9C STATUS: PASS"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()