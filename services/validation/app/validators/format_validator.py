"""Format validation for document numbers and names."""

from __future__ import annotations

import re
from typing import Any, Dict


def validate_required_string(field_name: str, value: Any) -> Dict[str, Any]:
    if value is None:
        return {
            "metric": field_name,
            "status": "REVIEW",
            "reason": f"{field_name} was not read from this document",
        }
    if isinstance(value, str) and not value.strip():
        # Whitespace is what OCR returns when it located a label and recovered
        # nothing after it. That is the same absence as None, reached by a
        # different route, and it says nothing about the document.
        return {
            "metric": field_name,
            "status": "REVIEW",
            "reason": f"{field_name} was read as empty",
        }
    return {
        "metric": field_name,
        "status": "PASS",
        "reason": f"{field_name} is present and non-empty",
    }


def validate_license_number_format(value: Any) -> Dict[str, Any]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return {
            "metric": "license_number_format",
            "status": "REVIEW",
            "reason": "License number was not read from this document",
        }
    s = str(value).strip().upper()
    # Indian DL-like: 2 letters + digits/letters
    if re.match(r"^[A-Z]{2}[0-9A-Z]{8,18}$", s):
        return {
            "metric": "license_number_format",
            "status": "PASS",
            "reason": "License number format looks valid",
        }
    if len(s) >= 8:
        return {
            "metric": "license_number_format",
            "status": "PASS",
            "reason": "License number has acceptable length",
        }
    return {
        "metric": "license_number_format",
        "status": "FAIL",
        "reason": "License number format appears invalid",
    }


def validate_passport_number_format(value: Any) -> Dict[str, Any]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return {
            "metric": "passport_number_format",
            "status": "REVIEW",
            "reason": "Passport number was not read from this document",
        }
    s = str(value).strip().upper()
    if re.match(r"^[A-Z0-9]{6,12}$", s):
        return {
            "metric": "passport_number_format",
            "status": "PASS",
            "reason": "Passport number format looks valid",
        }
    return {
        "metric": "passport_number_format",
        "status": "FAIL",
        "reason": "Passport number format appears invalid",
    }


def validate_name_format(value: Any) -> Dict[str, Any]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return {
            "metric": "name_format",
            "status": "REVIEW",
            "reason": "Name was not read from this document",
        }
    s = str(value).strip()
    if len(s) < 2:
        return {
            "metric": "name_format",
            "status": "FAIL",
            "reason": "Name is too short",
        }
    if re.search(r"\d{4,}", s):
        return {
            "metric": "name_format",
            "status": "REVIEW",
            "reason": "Name contains long numeric sequences",
        }
    return {
        "metric": "name_format",
        "status": "PASS",
        "reason": "Name format looks valid",
    }
