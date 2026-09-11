"""
license.py
==========

Driving License Validation Module.

This module validates standardized driving-license data
produced by conversion.py.

It does NOT perform OCR.

It does NOT process MRZ.

It only validates the structured driving-license data
passed to it by main.py.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(
    "license_document_processor"
)


# ============================================================
# VALIDATION HELPERS
# ============================================================

def is_valid_name(
    value: Any
) -> bool:
    """
    Validate a person's name.
    """

    if not isinstance(
        value,
        str
    ):

        return False

    value = value.strip()

    if not value:

        return False

    return bool(
        re.fullmatch(
            r"[A-Za-z][A-Za-z .'-]*",
            value
        )
    )


def is_valid_date(
    value: Any
) -> bool:
    """
    Validate an ISO date in YYYY-MM-DD format.
    """

    if not isinstance(
        value,
        str
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


def parse_date(
    value: Any
) -> Optional[date]:
    """
    Convert an ISO date string into a date object.
    """

    if not is_valid_date(
        value
    ):

        return None

    return datetime.strptime(
        value,
        "%Y-%m-%d"
    ).date()


def is_valid_sex(
    value: Any
) -> bool:
    """
    Validate the sex field.
    """

    if not isinstance(
        value,
        str
    ):

        return False

    value = value.strip().upper()

    return value in (
        "M",
        "F",
        "X",
        "MALE",
        "FEMALE",
        "OTHER",
    )


def is_valid_document_number(
    value: Any
) -> bool:
    """
    Validate the driving-license document number.

    Allows uppercase letters, numbers, spaces and hyphens.
    """

    if not isinstance(
        value,
        str
    ):

        return False

    value = value.strip().upper()

    if not value:

        return False

    return bool(
        re.fullmatch(
            r"[A-Z0-9][A-Z0-9 -]{4,24}",
            value
        )
    )


def is_valid_categories(
    value: Any
) -> bool:
    """
    Validate license categories.

    Categories may be represented as a string or list.
    """

    if value is None:

        return True

    if isinstance(
        value,
        str
    ):

        return bool(
            value.strip()
        )

    if isinstance(
        value,
        list
    ):

        return all(
            isinstance(
                item,
                str
            )
            and item.strip()
            for item in value
        )

    return False


# ============================================================
# MAIN LICENSE VALIDATION
# ============================================================

def process_license(
    license_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate driving-license data.

    Args:
        license_data:
            Standardized license object generated
            by conversion.py.

    Returns:
        Dictionary containing validation results.
    """

    if not isinstance(
        license_data,
        dict
    ):

        raise ValueError(
            "License data must be a JSON object."
        )

    errors: List[str] = []

    # ========================================================
    # EXTRACT FIELDS
    # ========================================================

    name = license_data.get(
        "name"
    )

    name_native = license_data.get(
        "name_native"
    )

    father_name = license_data.get(
        "father_name"
    )

    date_of_birth = license_data.get(
        "date_of_birth"
    )

    sex = license_data.get(
        "sex"
    )

    document_number = license_data.get(
        "document_number"
    )

    issue_date = license_data.get(
        "issue_date"
    )

    expiry_date = license_data.get(
        "expiry_date"
    )

    address = license_data.get(
        "address"
    )

    categories = license_data.get(
        "categories"
    )

    # ========================================================
    # REQUIRED FIELD VALIDATION
    # ========================================================

    if not is_valid_name(
        name
    ):

        errors.append(
            "Name is missing or invalid."
        )

    if name_native is not None:

        if not isinstance(
            name_native,
            str
        ) or not name_native.strip():

            errors.append(
                "Native name is invalid."
            )

    if not is_valid_name(
        father_name
    ):

        errors.append(
            "Father's name is missing or invalid."
        )

    # ========================================================
    # DATE OF BIRTH
    # ========================================================

    dob = parse_date(
        date_of_birth
    )

    if dob is None:

        errors.append(
            "Date of birth is missing or invalid."
        )

    else:

        today = date.today()

        if dob > today:

            errors.append(
                "Date of birth cannot be in the future."
            )

    # ========================================================
    # SEX
    # ========================================================

    if not is_valid_sex(
        sex
    ):

        errors.append(
            "Sex is missing or invalid."
        )

    # ========================================================
    # DOCUMENT NUMBER
    # ========================================================

    if not is_valid_document_number(
        document_number
    ):

        errors.append(
            "Driving license document number "
            "is missing or invalid."
        )

    # ========================================================
    # ISSUE DATE
    # ========================================================

    issue = None

    if issue_date is not None:

        issue = parse_date(
            issue_date
        )

        if issue is None:

            errors.append(
                "Issue date is invalid."
            )

        elif issue > date.today():

            errors.append(
                "Issue date cannot be in the future."
            )

    # ========================================================
    # EXPIRY DATE
    # ========================================================

    expiry = None

    if expiry_date is not None:

        expiry = parse_date(
            expiry_date
        )

        if expiry is None:

            errors.append(
                "Expiry date is invalid."
            )

        elif issue is not None and expiry < issue:

            errors.append(
                "Expiry date cannot be before issue date."
            )

        elif expiry < date.today():

            errors.append(
                "Driving license has expired."
            )

    # ========================================================
    # ADDRESS
    # ========================================================

    if address is not None:

        if not isinstance(
            address,
            str
        ) or not address.strip():

            errors.append(
                "Address is invalid."
            )

    # ========================================================
    # CATEGORIES
    # ========================================================

    if not is_valid_categories(
        categories
    ):

        errors.append(
            "License categories are invalid."
        )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    validation_passed = (
        len(errors) == 0
    )

    result = {

        "validation_passed":
            validation_passed,

        "document_type":
            "license",

        "license_validation": {

            "format_valid":
                validation_passed,

            "format_errors":
                errors,
        },
    }

    logger.info(
        "Driving license validation completed."
    )

    logger.info(
        "Validation result: %s",
        validation_passed
    )

    return result