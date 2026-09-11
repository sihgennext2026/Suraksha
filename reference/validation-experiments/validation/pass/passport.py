"""
passport.py
============================================================

Passport-specific validation module.

This module receives passport data from main.py.

It performs:

    1. Passport format validation
    2. MRZ processing through mrz.py
    3. MRZ/passport field comparison
    4. Returns complete result to main.py

FLOW
----

main.py
   |
   | passport_data + mrz_lines
   v
passport.py
   |
   |-- validate_format()
   |
   |-- mrz.process_mrz()
   |
   |-- compare_with_mrz()
   |
   v
result
   |
   v
main.py
"""

import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List


# ============================================================
# PASSPORT MRZ MODULE PATH
# ============================================================

PASS_DIR = Path(__file__).resolve().parent

if str(PASS_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(PASS_DIR)
    )

import mrz

# ============================================================
# REQUIRED PASSPORT FIELDS
# ============================================================

REQUIRED_FIELDS = [
    "document_number",
    "surname",
    "given_name",
    "date_of_birth",
    "sex",
    "nationality",
    "issue_date",
    "expiry_date",
]


# ============================================================
# DATE VALIDATION
# ============================================================

def valid_date(value: Any) -> bool:
    """
    Check whether a value is a valid YYYY-MM-DD calendar date.
    """

    if not isinstance(value, str):
        return False

    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        value
    ):
        return False

    try:

        datetime.strptime(
            value,
            "%Y-%m-%d"
        )

        return True

    except ValueError:

        return False


# ============================================================
# NAME NORMALIZATION
# ============================================================

def normalize_name(value: str) -> str:
    """
    Normalize names before comparison.

    Examples:

        KUMARAGURU, KRISHNARAJ

    and:

        KUMARAGURU KRISHNARAJ

    become comparable.
    """

    value = str(value).upper()

    value = value.replace(
        ",",
        " "
    )

    value = re.sub(
        r"[^A-Z0-9 ]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# FORMAT VALIDATION
# ============================================================

def validate_format(
    data: Dict[str, Any]
) -> List[str]:
    """
    Validate passport structured data.

    Checks:

        - required fields
        - field types
        - passport number
        - names
        - nationality
        - sex
        - dates
        - date relationships
    """

    errors: List[str] = []

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    for field in REQUIRED_FIELDS:

        if field not in data:

            errors.append(
                f"Missing required field: {field}"
            )

    # Stop here if required fields are missing.
    if errors:
        return errors

    # --------------------------------------------------------
    # Document number
    # --------------------------------------------------------

    document_number = data.get(
        "document_number"
    )

    if not isinstance(
        document_number,
        str
    ):

        errors.append(
            "document_number must be a string."
        )

    else:

        document_number = (
            document_number
            .strip()
            .upper()
        )

        if not re.fullmatch(
            r"[A-Z0-9]{6,12}",
            document_number
        ):

            errors.append(
                "document_number must be "
                "alphanumeric and 6-12 characters long."
            )

    # --------------------------------------------------------
    # Surname
    # --------------------------------------------------------

    surname = data.get(
        "surname"
    )

    if (
        not isinstance(surname, str)
        or not surname.strip()
    ):

        errors.append(
            "surname must be a non-empty string."
        )

    # --------------------------------------------------------
    # Given name
    # --------------------------------------------------------

    given_name = data.get(
        "given_name"
    )

    if (
        not isinstance(given_name, str)
        or not given_name.strip()
    ):

        errors.append(
            "given_name must be a non-empty string."
        )

    # --------------------------------------------------------
    # Full name
    # --------------------------------------------------------

    if "full_name" in data:

        if (
            data["full_name"] is not None
            and not isinstance(
                data["full_name"],
                str
            )
        ):

            errors.append(
                "full_name must be a string or null."
            )

    # --------------------------------------------------------
    # Nationality
    # --------------------------------------------------------

    nationality = data.get(
        "nationality"
    )

    if not isinstance(
        nationality,
        str
    ):

        errors.append(
            "nationality must be a string."
        )

    elif not re.fullmatch(
        r"[A-Z]{3}",
        nationality.upper()
    ):

        errors.append(
            "nationality must be a 3-letter "
            "country code."
        )

    # --------------------------------------------------------
    # Sex
    # --------------------------------------------------------

    sex = data.get(
        "sex"
    )

    if sex not in (
        "M",
        "F",
        "O",
    ):

        errors.append(
            "sex must be M, F, or O."
        )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    for field in (
        "date_of_birth",
        "issue_date",
        "expiry_date",
    ):

        if not valid_date(
            data.get(field)
        ):

            errors.append(
                f"{field} must be a valid "
                "YYYY-MM-DD date."
            )

    # --------------------------------------------------------
    # Issue date < expiry date
    # --------------------------------------------------------

    if (
        valid_date(data.get("issue_date"))
        and valid_date(data.get("expiry_date"))
    ):

        issue = datetime.strptime(
            data["issue_date"],
            "%Y-%m-%d"
        )

        expiry = datetime.strptime(
            data["expiry_date"],
            "%Y-%m-%d"
        )

        if issue >= expiry:

            errors.append(
                "issue_date must be earlier "
                "than expiry_date."
            )

    # --------------------------------------------------------
    # DOB < issue date
    # --------------------------------------------------------

    if (
        valid_date(data.get("date_of_birth"))
        and valid_date(data.get("issue_date"))
    ):

        dob = datetime.strptime(
            data["date_of_birth"],
            "%Y-%m-%d"
        )

        issue = datetime.strptime(
            data["issue_date"],
            "%Y-%m-%d"
        )

        if dob >= issue:

            errors.append(
                "date_of_birth must be earlier "
                "than issue_date."
            )

    return errors


# ============================================================
# MRZ COMPARISON
# ============================================================

def compare_with_mrz(
    passport_data: Dict[str, Any],
    mrz_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Compare structured passport data against
    fields extracted from the MRZ.
    """

    mismatches: List[Dict[str, Any]] = []

    comparisons = {

        "document_number": (
            passport_data.get("document_number"),
            mrz_data.get("document_number"),
        ),

        "date_of_birth": (
            passport_data.get("date_of_birth"),
            mrz_data.get("date_of_birth"),
        ),

        "nationality": (
            passport_data.get("nationality"),
            mrz_data.get("nationality"),
        ),

        "sex": (
            passport_data.get("sex"),
            mrz_data.get("sex"),
        ),

        "expiry_date": (
            passport_data.get("expiry_date"),
            mrz_data.get("date_of_expiry"),
        ),

        "surname": (
            passport_data.get("surname"),
            mrz_data.get("surname"),
        ),

        "given_name": (
            passport_data.get("given_name"),
            mrz_data.get("given_names"),
        ),
    }

    # --------------------------------------------------------
    # Compare every field
    # --------------------------------------------------------

    for field, values in comparisons.items():

        passport_value, mrz_value = values

        # Missing MRZ value
        if mrz_value is None:

            mismatches.append({
                "field": field,
                "passport_value": passport_value,
                "mrz_value": None,
                "error": (
                    f"{field} could not be extracted "
                    "from MRZ."
                ),
            })

            continue

        # Missing passport value
        if passport_value is None:
            continue

        # ----------------------------------------------------
        # Names
        # ----------------------------------------------------

        if field in (
            "surname",
            "given_name",
        ):

            left = normalize_name(
                str(passport_value)
            )

            right = normalize_name(
                str(mrz_value)
            )

        # ----------------------------------------------------
        # Other fields
        # ----------------------------------------------------

        else:

            left = str(
                passport_value
            ).strip().upper()

            right = str(
                mrz_value
            ).strip().upper()

        # ----------------------------------------------------
        # Mismatch
        # ----------------------------------------------------

        if left != right:

            mismatches.append({

                "field": field,

                "passport_value": passport_value,

                "mrz_value": mrz_value,

                "error": (
                    f"{field} does not match "
                    "between passport data and MRZ."
                ),
            })

    return mismatches


# ============================================================
# PASSPORT PROCESSOR
# ============================================================

def process_passport(
    passport_data: Dict[str, Any],
    mrz_lines: Any,
) -> Dict[str, Any]:
    """
    Main passport processing function.

    Called by main.py.

    Steps:

        1. Validate passport format
        2. Send MRZ to mrz.py
        3. Receive parsed MRZ
        4. Compare passport data with MRZ
        5. Return result
    """

    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    if not isinstance(
        passport_data,
        dict
    ):

        return {
            "document_type":
                "passport",

            "Validation_format":
                False,

            "MRZ":
                False,

            "Errors": [
                "Passport data must be a JSON object."
            ],
        }

    # ========================================================
    # STAGE 1 - FORMAT VALIDATION
    # ========================================================

    format_errors = validate_format(
        passport_data
    )

    format_valid = (
        len(format_errors) == 0
    )

    # ========================================================
    # STAGE 2 - MRZ PROCESSING
    # ========================================================

    try:

        mrz_result = mrz.process_mrz(
            mrz_lines
        )

    except Exception as exc:

        mrz_result = {
            "success": False,
            "errors": [
                f"MRZ module error: {str(exc)}"
            ],
        }

    mrz_success = mrz_result.get(
        "success",
        False
    )

    # ========================================================
    # STAGE 3 - MRZ FIELD COMPARISON
    # ========================================================

    mismatches: List[Dict[str, Any]] = []

    if (
        format_valid
        and mrz_success
    ):

        mismatches = compare_with_mrz(
            passport_data,
            mrz_result
        )

    mrz_match = (
        format_valid
        and mrz_success
        and len(mismatches) == 0
    )

    # ========================================================
    # CLEANED DATA
    # ========================================================

    cleaned_data = {

        "document_number": passport_data.get(
            "document_number"
        ),

        "surname": passport_data.get(
            "surname"
        ),

        "given_name": passport_data.get(
            "given_name"
        ),

        "full_name": passport_data.get(
            "full_name",
            (
                f"{passport_data.get('surname', '')}, "
                f"{passport_data.get('given_name', '')}"
            )
        ),

        "date_of_birth": passport_data.get(
            "date_of_birth"
        ),

        "sex": passport_data.get(
            "sex"
        ),

        "nationality": passport_data.get(
            "nationality"
        ),

        "issue_date": passport_data.get(
            "issue_date"
        ),

        "expiry_date": passport_data.get(
            "expiry_date"
        ),
    }

    # If basic required validation failed,
    # cleaned_data is not considered validated.
    if not format_valid:

        cleaned_data = None

    # ========================================================
    # FINAL RESULT
    # ========================================================

    errors: List[str] = []

    for error in format_errors:

        errors.append(
            f"Passport format validation: {error}"
        )

    if not mrz_success:

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

    for mismatch in mismatches:

        field = mismatch.get(
            "field",
            "unknown"
        )

        passport_value = mismatch.get(
            "passport_value"
        )

        mrz_value = mismatch.get(
            "mrz_value"
        )

        errors.append(
            f"MRZ mismatch for {field}: "
            f"passport={passport_value}, "
            f"mrz={mrz_value}"
        )

    return {

        "document_type":
            "passport",

        "Validation_format":
            format_valid,

        "MRZ":
            mrz_match,

        "Errors":
            errors,
    }


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    print(
        "passport.py is a module."
    )

    print(
        "It is normally called by main.py."
    )