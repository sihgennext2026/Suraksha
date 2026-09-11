"""
aadhar.py
============================================================

Aadhaar number format validation module.

IMPORTANT
---------

This module performs ONLY Aadhaar number format validation.

It does NOT perform:

    - OCR
    - QR code scanning
    - Barcode scanning
    - Image processing
    - Scanner processing
    - Document detection
    - Aadhaar XML processing

Input:
    Raw Aadhaar number string.

Supported formats:

    123456789012

    1234 5678 9012

    1234-5678-9012

Output:

    {
        "is_valid": true,
        "number": "123456789012",
        "format_detected": "12-digit numeric",
        "error": null
    }
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


# ============================================================
# AADHAAR FORMAT PATTERNS
# ============================================================

AADHAAR_CONTINUOUS_PATTERN = re.compile(
    r"^\d{12}$"
)

AADHAAR_SPACED_PATTERN = re.compile(
    r"^\d{4}\s\d{4}\s\d{4}$"
)

AADHAAR_HYPHEN_PATTERN = re.compile(
    r"^\d{4}-\d{4}-\d{4}$"
)


# ============================================================
# NORMALIZE INPUT
# ============================================================

def normalize_input(
    value: Any
) -> str:
    """
    Convert the supplied value into a clean string.

    Leading and trailing whitespace is removed.

    Internal spaces and hyphens are preserved because
    they are required to determine the original format.
    """

    if value is None:

        return ""

    if not isinstance(
        value,
        str
    ):

        return ""

    return value.strip()


# ============================================================
# VALIDATE AADHAAR NUMBER
# ============================================================

def validate_aadhaar(
    aadhaar_number: Any
) -> Dict[str, Optional[str]]:
    """
    Validate an Aadhaar number based only on its format.

    Supported formats:

        123456789012

        1234 5678 9012

        1234-5678-9012
    """

    value = normalize_input(
        aadhaar_number
    )

    # --------------------------------------------------------
    # Empty input
    # --------------------------------------------------------

    if not value:

        return {
            "is_valid": False,
            "number": None,
            "format_detected": None,
            "error": "Aadhaar number is empty."
        }

    # --------------------------------------------------------
    # Continuous 12-digit format
    # --------------------------------------------------------

    if AADHAAR_CONTINUOUS_PATTERN.fullmatch(
        value
    ):

        return {
            "is_valid": True,
            "number": value,
            "format_detected": "12-digit numeric",
            "error": None
        }

    # --------------------------------------------------------
    # 4-4-4 space format
    # --------------------------------------------------------

    if AADHAAR_SPACED_PATTERN.fullmatch(
        value
    ):

        cleaned_number = value.replace(
            " ",
            ""
        )

        return {
            "is_valid": True,
            "number": cleaned_number,
            "format_detected": "4-4-4 space grouping",
            "error": None
        }

    # --------------------------------------------------------
    # 4-4-4 hyphen format
    # --------------------------------------------------------

    if AADHAAR_HYPHEN_PATTERN.fullmatch(
        value
    ):

        cleaned_number = value.replace(
            "-",
            ""
        )

        return {
            "is_valid": True,
            "number": cleaned_number,
            "format_detected": "4-4-4 hyphen grouping",
            "error": None
        }

    # --------------------------------------------------------
    # Invalid format
    # --------------------------------------------------------

    cleaned_number = re.sub(
        r"[\s-]",
        "",
        value
    )

    if not cleaned_number.isdigit():

        return {
            "is_valid": False,
            "number": None,
            "format_detected": None,
            "error": (
                "Aadhaar number must contain only digits, "
                "spaces, or hyphens."
            )
        }

    if len(cleaned_number) != 12:

        return {
            "is_valid": False,
            "number": None,
            "format_detected": None,
            "error": (
                "Aadhaar number must contain exactly 12 digits."
            )
        }

    return {
        "is_valid": False,
        "number": None,
        "format_detected": None,
        "error": (
            "Invalid Aadhaar number format. "
            "Expected 12 digits, 4-4-4 space grouping, "
            "or 4-4-4 hyphen grouping."
        )
    }


# ============================================================
# PROCESS AADHAAR
# ============================================================

def process_aadhaar(
    aadhaar_number: Any
) -> Dict[str, Optional[str]]:
    """
    Main Aadhaar validation entry point.
    """

    return validate_aadhaar(
        aadhaar_number
    )


# ============================================================
# ALIAS
# ============================================================

def validate_aadhar(
    aadhaar_number: Any
) -> Dict[str, Optional[str]]:
    """
    Compatibility alias for code using the
    'aadhar' spelling.
    """

    return validate_aadhaar(
        aadhaar_number
    )


# ============================================================
# TEST ENTRY POINT
# ============================================================

if __name__ == "__main__":

    test_values = [

        "123456789012",

        "1234 5678 9012",

        "1234-5678-9012",

        "12345678901",

        "1234567890123",

        "1234 5678 901",

        "1234 5678 9012X",

        "",

    ]

    for value in test_values:

        result = process_aadhaar(
            value
        )

        print(
            f"{value!r} -> {result}"
        )