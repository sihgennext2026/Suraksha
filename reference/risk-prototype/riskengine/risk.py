"""
risk.py
=======

HYBRID RISK SCORING ENGINE.

INPUTS:
    validateout.json
    tampering.json
    faceout.json

OUTPUT:
    riskout.json

FLOW:

    Validation Output
           |
           v
    Validation Risk
           |
           |
    Tampering Output
           |
           v
     Tampering Risk
           |
           |
      Face Output
           |
           v
       Face Risk
           |
           v
    HYBRID RISK SCORE
           |
           v
       riskout.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

VALIDATION_FILE = BASE_DIR / "validateout.json"
TAMPERING_FILE = BASE_DIR / "tampering.json"
FACE_FILE = BASE_DIR / "faceout.json"

OUTPUT_FILE = BASE_DIR / "riskout.json"


# ============================================================
# RISK WEIGHTS
# ============================================================

VALIDATION_WEIGHT = 0.25
TAMPERING_WEIGHT = 0.45
FACE_WEIGHT = 0.30


# ============================================================
# RISK THRESHOLDS
# ============================================================

GENUINE_MAX = 24
SUSPICIOUS_MAX = 49
HIGH_RISK_MAX = 74


# ============================================================
# LOAD JSON
# ============================================================

def load_json(
    file_path: Path
) -> Dict[str, Any]:

    if not file_path.exists():

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if not isinstance(
        data,
        dict
    ):

        raise ValueError(
            f"{file_path.name} must contain a JSON object."
        )

    return data


# ============================================================
# CLAMP
# ============================================================

def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0
) -> float:

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


# ============================================================
# VALIDATION RISK
# ============================================================

def calculate_validation_risk(
    data: Dict[str, Any]
) -> float:
    """
    Convert validation result into a 0-100 risk score.

    validation_passed = true
        -> low validation risk

    validation_passed = false
        -> high validation risk
    """

    validation_passed = data.get(
        "validation_passed"
    )

    if validation_passed is True:

        return 0.0

    if validation_passed is False:

        return 100.0

    return 50.0


# ============================================================
# TAMPERING RISK
# ============================================================

def calculate_tampering_risk(
    data: Dict[str, Any]
) -> float:
    """
    Convert tampering output into a 0-100 risk score.

    tamper_score is treated as the primary signal.

    Photo replacement and maximum suspicious-region
    scores are used as supporting signals.
    """

    tamper_score = data.get(
        "tamper_score",
        0.0
    )

    photo_replacement_score = data.get(
        "photo_replacement_score",
        0.0
    )

    max_region_score = data.get(
        "max_region_score",
        0.0
    )

    if not isinstance(
        tamper_score,
        (int, float)
    ):

        tamper_score = 0.0

    if not isinstance(
        photo_replacement_score,
        (int, float)
    ):

        photo_replacement_score = 0.0

    if not isinstance(
        max_region_score,
        (int, float)
    ):

        max_region_score = 0.0

    risk = (

        (tamper_score * 0.65)

        +

        (photo_replacement_score * 0.25)

        +

        (max_region_score * 0.10)
    )

    return clamp(
        risk * 100
    )


# ============================================================
# FACE RISK
# ============================================================

def calculate_face_risk(
    data: Dict[str, Any]
) -> float:
    """
    Convert face verification output into a 0-100
    identity mismatch risk.

    The face verification system uses:

        cosine_similarity
        threshold
        decision

    Example:

        cosine_similarity = 0.587370
        threshold = 0.225000
        decision = MATCH

    A MATCH produces low face risk.

    A NO MATCH produces high face risk.
    """

    cosine_similarity = data.get(
        "cosine_similarity"
    )

    threshold = data.get(
        "threshold",
        0.225
    )

    decision = data.get(
        "decision"
    )

    # --------------------------------------------------------
    # Validate cosine similarity
    # --------------------------------------------------------

    if not isinstance(
        cosine_similarity,
        (int, float)
    ):

        cosine_similarity = None

    # --------------------------------------------------------
    # Validate threshold
    # --------------------------------------------------------

    if not isinstance(
        threshold,
        (int, float)
    ):

        threshold = 0.225

    # --------------------------------------------------------
    # NO MATCH
    # --------------------------------------------------------

    if decision == "NO MATCH":

        return 90.0

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    if decision == "MATCH":

        if cosine_similarity is None:

            return 10.0

        # ----------------------------------------------------
        # Similarity is above threshold.
        #
        # The closer the similarity is to 1.0,
        # the lower the identity risk.
        # ----------------------------------------------------

        if cosine_similarity >= threshold:

            similarity_range = (
                1.0 - threshold
            )

            similarity_above_threshold = (
                cosine_similarity - threshold
            )

            match_strength = (
                similarity_above_threshold
                / similarity_range
            )

            match_strength = clamp(
                match_strength,
                0.0,
                1.0
            )

            return clamp(
                50.0
                - (
                    match_strength
                    * 40.0
                )
            )

        return 90.0

    # --------------------------------------------------------
    # Unknown decision
    # --------------------------------------------------------

    return 50.0


# ============================================================
# RISK CATEGORY
# ============================================================

def determine_category(
    risk_score: float
) -> str:

    if risk_score <= GENUINE_MAX:

        return "Genuine"

    if risk_score <= SUSPICIOUS_MAX:

        return "Suspicious"

    if risk_score <= HIGH_RISK_MAX:

        return "High-Risk Fake"

    return "Critical Fraud"


# ============================================================
# ESCALATION RULES
# ============================================================

def apply_escalation_rules(
    base_risk: float,
    validation_risk: float,
    tampering_risk: float,
    face_risk: float,
    tampering_data: Dict[str, Any]
) -> tuple[float, list[str]]:
    """
    Apply strong-signal escalation rules.

    These rules prevent a strong fraud signal
    from being hidden by other modules.
    """

    final_risk = base_risk

    reasons = []

    photo_replacement_score = tampering_data.get(
        "photo_replacement_score",
        0.0
    )

    max_region_score = tampering_data.get(
        "max_region_score",
        0.0
    )

    suspicious_area_ratio = tampering_data.get(
        "suspicious_area_ratio",
        0.0
    )

    # --------------------------------------------------------
    # Strong tampering
    # --------------------------------------------------------

    if tampering_risk >= 85:

        final_risk = max(
            final_risk,
            50.0
        )

        reasons.append(
            "Strong document tampering signal detected."
        )

    # --------------------------------------------------------
    # Photo replacement
    # --------------------------------------------------------

    if (
        isinstance(
            photo_replacement_score,
            (int, float)
        )
        and photo_replacement_score >= 0.85
    ):

        final_risk = max(
            final_risk,
            55.0
        )

        reasons.append(
            "High photo replacement probability detected."
        )

    # --------------------------------------------------------
    # Severe suspicious region
    # --------------------------------------------------------

    if (
        isinstance(
            max_region_score,
            (int, float)
        )
        and max_region_score >= 0.90
        and isinstance(
            suspicious_area_ratio,
            (int, float)
        )
        and suspicious_area_ratio >= 0.05
    ):

        final_risk = max(
            final_risk,
            55.0
        )

        reasons.append(
            "Severe suspicious document region detected."
        )

    # --------------------------------------------------------
    # Multiple strong signals
    # --------------------------------------------------------

    if (
        tampering_risk >= 90
        and face_risk >= 75
    ):

        final_risk = max(
            final_risk,
            75.0
        )

        reasons.append(
            "Strong tampering and face mismatch detected."
        )

    # --------------------------------------------------------
    # Validation + tampering conflict
    # --------------------------------------------------------

    if (
        validation_risk >= 80
        and tampering_risk >= 80
    ):

        final_risk = max(
            final_risk,
            75.0
        )

        reasons.append(
            "Validation failure and strong tampering detected together."
        )

    # --------------------------------------------------------
    # Validation + face conflict
    # --------------------------------------------------------

    if (
        validation_risk >= 80
        and face_risk >= 85
    ):

        final_risk = max(
            final_risk,
            75.0
        )

        reasons.append(
            "Validation failure and strong face mismatch detected together."
        )

    return (
        clamp(final_risk),
        reasons
    )


# ============================================================
# RISK ENGINE
# ============================================================

def calculate_risk() -> Dict[str, Any]:

    # --------------------------------------------------------
    # Load JSON files separately
    # --------------------------------------------------------

    validation_data = load_json(
        VALIDATION_FILE
    )

    tampering_data = load_json(
        TAMPERING_FILE
    )

    face_data = load_json(
        FACE_FILE
    )

    # --------------------------------------------------------
    # Calculate individual risks
    # --------------------------------------------------------

    validation_risk = calculate_validation_risk(
        validation_data
    )

    tampering_risk = calculate_tampering_risk(
        tampering_data
    )

    face_risk = calculate_face_risk(
        face_data
    )

    # --------------------------------------------------------
    # Weighted hybrid score
    # --------------------------------------------------------

    base_risk = (

        validation_risk
        * VALIDATION_WEIGHT

        +

        tampering_risk
        * TAMPERING_WEIGHT

        +

        face_risk
        * FACE_WEIGHT
    )

    # --------------------------------------------------------
    # Apply escalation rules
    # --------------------------------------------------------

    final_risk, escalation_reasons = apply_escalation_rules(

        base_risk,

        validation_risk,

        tampering_risk,

        face_risk,

        tampering_data
    )

    # --------------------------------------------------------
    # Category
    # --------------------------------------------------------

    category = determine_category(
        final_risk
    )

    # --------------------------------------------------------
    # Reasons
    # --------------------------------------------------------

    reasons = []

    if validation_risk >= 80:

        reasons.append(
            "Document validation produced a high-risk result."
        )

    if tampering_risk >= 80:

        reasons.append(
            "Document tampering risk is high."
        )

    if face_risk >= 75:

        reasons.append(
            "Face verification indicates a possible identity mismatch."
        )

    reasons.extend(
        escalation_reasons
    )

    # Remove duplicate reasons

    reasons = list(
        dict.fromkeys(
            reasons
        )
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    result = {

        "risk_score":
            round(
                final_risk,
                2
            ),

        "risk_category":
            category,

        "module_scores": {

            "validation_risk":
                round(
                    validation_risk,
                    2
                ),

            "tampering_risk":
                round(
                    tampering_risk,
                    2
                ),

            "face_risk":
                round(
                    face_risk,
                    2
                ),
        },

        "weights": {

            "validation":
                VALIDATION_WEIGHT,

            "tampering":
                TAMPERING_WEIGHT,

            "face":
                FACE_WEIGHT,
        },

        "reasons":
            reasons,
    }

    return result


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(
    result: Dict[str, Any]
) -> None:

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:

        result = calculate_risk()

        save_result(
            result
        )

        print(
            json.dumps(
                result,
                indent=4
            )
        )

    except Exception as exc:

        error_result = {

            "risk_score": None,

            "risk_category": "Error",

            "error":
                str(exc)
        }

        save_result(
            error_result
        )

        print(
            json.dumps(
                error_result,
                indent=4
            )
        )