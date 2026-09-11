"""
Per-field evaluation logic.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.evaluation.similarity import compare_text, character_error_rate


# Field type classification for matching rules
DATE_FIELDS = {
    "date_of_birth",
    "date_of_issue",
    "date_of_expiry",
}
NUMBER_FIELDS = {
    "license_number",
    "passport_number",
    "visa_number",
    "national_id_number",
    "permit_number",
}
NAME_FIELDS = {"name", "parent_name"}
TEXT_FIELDS = {"address", "nationality", "visa_type", "permit_type", "gender", "blood_group"}


def _field_type(field_name: str) -> str:
    if field_name in DATE_FIELDS:
        return "date"
    if field_name in NUMBER_FIELDS:
        return "number"
    if field_name in NAME_FIELDS:
        return "name"
    return "text"


def evaluate_field(
    field_name: str,
    expected: Any,
    extracted: Any,
    source_text: Optional[str] = None,
    ocr_confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluate a single field.

    Status rules:
    - extracted is None  → REVIEW (missing / could not extract)
    - extracted is ""    → FAIL  (empty)
    - matches expected   → PASS
    - does not match     → FAIL
    """
    result: Dict[str, Any] = {
        "field": field_name,
        "expected": expected,
        "extracted": extracted,
        "status": "FAIL",
        "match_type": "none",
        "accuracy": 0.0,
        "cer": 1.0,
        "reason": "",
        "source_text": source_text,
        "ocr_confidence": ocr_confidence,
    }

    # Missing extraction
    if extracted is None:
        result["status"] = "REVIEW"
        result["match_type"] = "none"
        result["accuracy"] = 0.0
        result["cer"] = 1.0
        result["reason"] = f"{field_name} could not be extracted from OCR"
        return result

    # Empty string
    if isinstance(extracted, str) and extracted.strip() == "":
        result["status"] = "FAIL"
        result["match_type"] = "none"
        result["accuracy"] = 0.0
        result["cer"] = 1.0
        result["reason"] = f"{field_name} field is empty"
        return result

    # Both present — compare
    ftype = _field_type(field_name)

    if ftype == "date":
        # Dates already normalized to YYYY-MM-DD by extractor
        exp_s = str(expected).strip() if expected is not None else ""
        ext_s = str(extracted).strip() if extracted is not None else ""
        if exp_s == ext_s:
            result["status"] = "PASS"
            result["match_type"] = "exact"
            result["accuracy"] = 1.0
            result["cer"] = 0.0
            result["reason"] = "Normalized date match"
        else:
            # Try normalized comparison (should already be ISO)
            result["status"] = "FAIL"
            result["match_type"] = "none"
            result["accuracy"] = 0.0
            result["cer"] = character_error_rate(exp_s, ext_s)
            result["reason"] = (
                f"Extracted date '{ext_s}' does not match expected '{exp_s}'"
            )
        return result

    # Text / name / number
    match_type, accuracy, cer = compare_text(
        str(expected) if expected is not None else None,
        str(extracted) if extracted is not None else None,
        field_type=ftype,
    )
    result["match_type"] = match_type
    result["accuracy"] = accuracy
    result["cer"] = cer

    if match_type in ("exact", "normalized"):
        result["status"] = "PASS"
        result["reason"] = (
            "Exact match" if match_type == "exact" else "Normalized match"
        )
    else:
        result["status"] = "FAIL"
        result["reason"] = (
            f"Extracted {field_name} does not match expected {field_name}"
        )

    return result
