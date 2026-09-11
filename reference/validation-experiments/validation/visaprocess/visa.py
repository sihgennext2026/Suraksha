"""
visa.py
============================================================

VISA DOCUMENT VALIDATION MODULE

This module performs the complete VISA validation workflow.

WORKFLOW
--------

    main.py
       |
       v
    visa.py
       |
       |-- Validate visa fields
       |
       |-- Send MRZ to vmrz.py
       |                  |
       |                  v
       |              mrz.json
       |
       |-- Compare visa fields with MRZ
       |
       v
    Return validation result to main.py

The visa pipeline intentionally follows the same overall
processing model as the passport pipeline.

IMPORTANT
---------

MRZ processing is performed by:

    visa/vmrz.py

The visa module does NOT directly decode MRZ.
"""


from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VISA_DIR = Path(__file__).resolve().parent

if str(VISA_DIR) not in sys.path:
    sys.path.insert(0, str(VISA_DIR))

import vmrz


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("visa")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_text(
    value: Any
) -> Optional[str]:
    """
    Normalize a text value for comparison.
    """

    if value is None:
        return None

    if not isinstance(
        value,
        str
    ):
        value = str(value)

    value = (
        value
        .strip()
        .upper()
    )

    if not value:
        return None

    return value


def normalize_name(
    value: Any
) -> Optional[str]:
    """
    Normalize a person's name.

    Removes punctuation and MRZ separators.
    """

    value = normalize_text(
        value
    )

    if value is None:
        return None

    value = value.replace(
        "<",
        " "
    )

    value = value.replace(
        ",",
        " "
    )

    value = " ".join(
        value.split()
    )

    return value


def normalize_date(
    value: Any
) -> Optional[str]:
    """
    Normalize date values.

    Expected final format:

        YYYY-MM-DD
    """

    if value is None:
        return None

    value = str(
        value
    ).strip()

    if not value:
        return None

    # Already normalized.
    if len(value) == 10 and value[4] == "-" and value[7] == "-":

        return value

    # DDMMMYYYY
    months = {
        "JAN": "01",
        "FEB": "02",
        "MAR": "03",
        "APR": "04",
        "MAY": "05",
        "JUN": "06",
        "JUL": "07",
        "AUG": "08",
        "SEP": "09",
        "OCT": "10",
        "NOV": "11",
        "DEC": "12",
    }

    value_upper = value.upper()

    if len(value_upper) == 9:

        day = value_upper[0:2]
        month = value_upper[2:5]
        year = value_upper[5:9]

        if month in months:

            return (
                f"{year}-"
                f"{months[month]}-"
                f"{day}"
            )

    return value


# ============================================================
# VISA FIELD VALIDATION
# ============================================================

def validate_visa_fields(
    visa_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate the basic structure and values of visa data.

    This is NOT MRZ validation.

    MRZ validation is performed by vmrz.py.
    """

    errors: List[str] = []

    if not isinstance(
        visa_data,
        dict
    ):

        return {

            "format_valid": False,

            "errors": [
                "Visa data must be an object."
            ],
        }

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    required_fields = [

        "surname",

        "given_name",

        "date_of_birth",

        "passport_number",

        "nationality",

        "issue_date",

        "expiry_date",
    ]

    for field in required_fields:

        value = visa_data.get(
            field
        )

        if value is None or str(value).strip() == "":

            errors.append(
                f"Required visa field '{field}' is missing."
            )

    # --------------------------------------------------------
    # Date checks
    # --------------------------------------------------------

    dob = normalize_date(
        visa_data.get(
            "date_of_birth"
        )
    )

    issue_date = normalize_date(
        visa_data.get(
            "issue_date"
        )
    )

    expiry_date = normalize_date(
        visa_data.get(
            "expiry_date"
        )
    )

    if dob is None:

        errors.append(
            "Visa date_of_birth is invalid."
        )

    if issue_date is None:

        errors.append(
            "Visa issue_date is invalid."
        )

    if expiry_date is None:

        errors.append(
            "Visa expiry_date is invalid."
        )

    # --------------------------------------------------------
    # Passport number
    # --------------------------------------------------------

    passport_number = normalize_text(
        visa_data.get(
            "passport_number"
        )
    )

    if passport_number:

        if len(passport_number) < 5:

            errors.append(
                "Passport number is too short."
            )

    # --------------------------------------------------------
    # Nationality
    # --------------------------------------------------------

    nationality = normalize_text(
        visa_data.get(
            "nationality"
        )
    )

    if nationality:

        if len(nationality) != 3:

            errors.append(
                "Nationality must be a 3-letter country code."
            )

    return {

        "format_valid": (
            len(errors) == 0
        ),

        "errors": errors,
    }


# ============================================================
# MRZ COMPARISON
# ============================================================

def compare_visa_with_mrz(
    visa_data: Dict[str, Any],
    mrz_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare structured visa OCR fields with MRZ fields.
    """

    mismatches: List[Dict[str, Any]] = []

    mrz_fields = mrz_result.get(
        "fields",
        {}
    )

    if not isinstance(
        mrz_fields,
        dict
    ):

        return {

            "mrz_match": False,

            "mismatches": [

                {
                    "field": "mrz_fields",

                    "visa_value": None,

                    "mrz_value": None,

                    "reason": "MRZ fields are unavailable.",
                }
            ],
        }

    # ========================================================
    # SURNAME
    # ========================================================

    visa_surname = normalize_name(
        visa_data.get(
            "surname"
        )
    )

    mrz_surname = normalize_name(
        mrz_fields.get(
            "surname"
        )
    )

    if (
        visa_surname is not None
        and mrz_surname is not None
        and visa_surname != mrz_surname
    ):

        mismatches.append({

            "field": "surname",

            "visa_value": visa_surname,

            "mrz_value": mrz_surname,
        })

    # ========================================================
    # GIVEN NAME
    # ========================================================

    visa_given_name = normalize_name(
        visa_data.get(
            "given_name"
        )
    )

    mrz_given_name = normalize_name(
        mrz_fields.get(
            "given_name"
        )
    )

    if (
        visa_given_name is not None
        and mrz_given_name is not None
        and visa_given_name != mrz_given_name
    ):

        mismatches.append({

            "field": "given_name",

            "visa_value": visa_given_name,

            "mrz_value": mrz_given_name,
        })

    # ========================================================
    # DATE OF BIRTH
    # ========================================================

    visa_dob = normalize_date(
        visa_data.get(
            "date_of_birth"
        )
    )

    mrz_dob = normalize_date(
        mrz_fields.get(
            "date_of_birth"
        )
    )

    if (
        visa_dob is not None
        and mrz_dob is not None
        and visa_dob != mrz_dob
    ):

        mismatches.append({

            "field": "date_of_birth",

            "visa_value": visa_dob,

            "mrz_value": mrz_dob,
        })

    # ========================================================
    # PASSPORT NUMBER
    # ========================================================

    visa_passport_number = normalize_text(
        visa_data.get(
            "passport_number"
        )
    )

    mrz_passport_number = normalize_text(
        mrz_fields.get(
            "document_number"
        )
    )

    if (
        visa_passport_number is not None
        and mrz_passport_number is not None
        and visa_passport_number != mrz_passport_number
    ):

        mismatches.append({

            "field": "passport_number",

            "visa_value": visa_passport_number,

            "mrz_value": mrz_passport_number,
        })

    # ========================================================
    # NATIONALITY
    # ========================================================

    visa_nationality = normalize_text(
        visa_data.get(
            "nationality"
        )
    )

    mrz_nationality = normalize_text(
        mrz_fields.get(
            "nationality"
        )
    )

    if (
        visa_nationality is not None
        and mrz_nationality is not None
        and visa_nationality != mrz_nationality
    ):

        mismatches.append({

            "field": "nationality",

            "visa_value": visa_nationality,

            "mrz_value": mrz_nationality,
        })

    # ========================================================
    # EXPIRY DATE
    # ========================================================

    visa_expiry = normalize_date(
        visa_data.get(
            "expiry_date"
        )
    )

    mrz_expiry = normalize_date(
        mrz_fields.get(
            "expiry_date"
        )
    )

    if (
        visa_expiry is not None
        and mrz_expiry is not None
        and visa_expiry != mrz_expiry
    ):

        mismatches.append({

            "field": "expiry_date",

            "visa_value": visa_expiry,

            "mrz_value": mrz_expiry,
        })

    return {

        "mrz_match": (
            len(mismatches) == 0
        ),

        "mismatches": mismatches,
    }


# ============================================================
# ERROR COLLECTION
# ============================================================

def collect_visa_errors(
    format_result: Dict[str, Any],
    mrz_result: Dict[str, Any],
    comparison_result: Dict[str, Any]
) -> List[str]:
    """
    Combine visa format, MRZ and comparison errors.
    """

    errors: List[str] = []

    # --------------------------------------------------------
    # Visa format errors
    # --------------------------------------------------------

    format_errors = format_result.get(
        "errors",
        []
    )

    if isinstance(
        format_errors,
        list
    ):

        for error in format_errors:

            errors.append(
                f"Visa format validation: {error}"
            )

    # --------------------------------------------------------
    # MRZ errors
    # --------------------------------------------------------

    mrz_errors = mrz_result.get(
        "errors",
        []
    )

    if isinstance(
        mrz_errors,
        list
    ):

        for error in mrz_errors:

            errors.append(
                f"MRZ validation: {error}"
            )

    # --------------------------------------------------------
    # MRZ mismatches
    # --------------------------------------------------------

    mismatches = comparison_result.get(
        "mismatches",
        []
    )

    if isinstance(
        mismatches,
        list
    ):

        for mismatch in mismatches:

            if not isinstance(
                mismatch,
                dict
            ):
                continue

            field = mismatch.get(
                "field",
                "unknown"
            )

            visa_value = mismatch.get(
                "visa_value"
            )

            mrz_value = mismatch.get(
                "mrz_value"
            )

            errors.append(
                f"MRZ mismatch for {field}: "
                f"visa={visa_value}, "
                f"mrz={mrz_value}"
            )

    return errors


# ============================================================
# MAIN VISA PROCESSOR
# ============================================================

def process_visa(
    visa_data: Dict[str, Any],
    mrz_lines: List[str]
) -> Dict[str, Any]:
    """
    Main entry point called by main.py.

    Performs:

        1. Visa field validation
        2. Visa MRZ processing
        3. Visa/MRZ comparison
        4. Final validation decision
        5. Cleaned data generation
    """

    logger.info(
        "Starting visa validation."
    )

    # ========================================================
    # STEP 1
    # Visa format validation
    # ========================================================

    format_result = validate_visa_fields(
        visa_data
    )

    logger.info(
        "Visa format validation completed."
    )

    # ========================================================
    # STEP 2
    # MRZ processing
    # ========================================================

    mrz_result = vmrz.process_visa_mrz(
        mrz_lines
    )

    logger.info(
        "Visa MRZ processing completed."
    )

    # ========================================================
    # STEP 3
    # Compare visa data with MRZ
    # ========================================================

    comparison_result = compare_visa_with_mrz(
        visa_data,
        mrz_result
    )

    logger.info(
        "Visa/MRZ comparison completed."
    )

    # ========================================================
    # STEP 4
    # Collect errors
    # ========================================================

    errors = collect_visa_errors(
        format_result,
        mrz_result,
        comparison_result
    )

    # ========================================================
    # STEP 5
    # Final validation
    # ========================================================

    format_valid = format_result.get(
        "format_valid",
        False
    )

    mrz_success = mrz_result.get(
        "success",
        False
    )

    mrz_match = comparison_result.get(
        "mrz_match",
        False
    )

    validation_passed = (
        format_valid
        and mrz_success
        and mrz_match
        and len(errors) == 0
    )

    # ========================================================
    # STEP 6
    # Cleaned data
    # ========================================================

    cleaned_data = None

    if validation_passed:

        cleaned_data = {

            "document_type": "visa",

            "surname": visa_data.get(
                "surname"
            ),

            "given_name": visa_data.get(
                "given_name"
            ),

            "name": visa_data.get(
                "full_name"
            ),

            "date_of_birth": normalize_date(
                visa_data.get(
                    "date_of_birth"
                )
            ),

            "passport_number": visa_data.get(
                "passport_number"
            ),

            "nationality": visa_data.get(
                "nationality"
            ),

            "issue_date": normalize_date(
                visa_data.get(
                    "issue_date"
                )
            ),

            "expiry_date": normalize_date(
                visa_data.get(
                    "expiry_date"
                )
            ),
        }

    # ========================================================
    # STEP 7
    # Final result
    # ========================================================

    # ========================================================
    # OUTPUT FORMATTING CHANGE ONLY
    # ========================================================
    # The validation logic above is unchanged.
    # Return the visa-specific validation fields required
    # by main.py.
    #
    # Validation_format reports only the visa field-format
    # validation result.
    #
    # MRZ reports only MRZ extraction/parsing validation.
    #
    # Errors contains only the existing MRZ mismatch strings.
    # ========================================================

    mismatch_errors = []

    for mismatch in comparison_result.get(
        "mismatches",
        []
    ):
        if isinstance(mismatch, dict):
            mismatch_errors.append(
                f"MRZ mismatch for {mismatch.get('field', 'unknown')}: "
                f"visa={mismatch.get('visa_value')}, "
                f"mrz={mismatch.get('mrz_value')}"
            )

    return {
        "document_type": "visa",
        "Validation_format": format_valid,
        "MRZ": mrz_success,
        "Errors": mismatch_errors,
    }


# ============================================================
# ALIAS
# ============================================================

def process_visa_document(
    visa_data: Dict[str, Any],
    mrz_lines: List[str]
) -> Dict[str, Any]:
    """
    Alias for process_visa().
    """

    return process_visa(
        visa_data=visa_data,
        mrz_lines=mrz_lines,
    )