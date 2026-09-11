"""
Three-way verification decision layer.

PROVISIONAL THRESHOLDS - NOT PRODUCTION VALIDATED.

Threshold evidence comes from LFW calibration:
    EER        : threshold=0.1007  FAR=4.54%  FRR=4.55%
    FAR<=1%    : threshold=0.1407  FAR=0.97%  FRR=4.82%
    FAR<=0.1%  : threshold=0.2254  FAR=0.07%  FRR=5.09%

These thresholds are provisional because production use is
cross-domain: document portrait vs live capture.
"""

from enum import Enum


class VerificationDecision(str, Enum):
    MATCH = "MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"


# PROVISIONAL - NOT PRODUCTION VALIDATED
REVIEW_THRESHOLD = 0.14
MATCH_THRESHOLD = 0.30


if REVIEW_THRESHOLD >= MATCH_THRESHOLD:
    raise ValueError(
        "REVIEW_THRESHOLD must be < MATCH_THRESHOLD"
    )


def classify(
    similarity: float,
    match_threshold: float = MATCH_THRESHOLD,
    review_threshold: float = REVIEW_THRESHOLD,
) -> VerificationDecision:
    """
    Map a cosine similarity score to a three-way decision.

    similarity >= match_threshold
        -> MATCH

    review_threshold <= similarity < match_threshold
        -> REVIEW

    similarity < review_threshold
        -> NO_MATCH
    """

    if match_threshold <= review_threshold:
        raise ValueError(
            "match_threshold must be greater than review_threshold"
        )

    if similarity >= match_threshold:
        return VerificationDecision.MATCH

    if similarity >= review_threshold:
        return VerificationDecision.REVIEW

    return VerificationDecision.NO_MATCH