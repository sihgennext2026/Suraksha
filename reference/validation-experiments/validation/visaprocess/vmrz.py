"""
vmrz.py
============================================================

VISA MRZ PROCESSOR

This module performs MRZ processing for VISA documents.

WORKFLOW
--------

    visa.py
       |
       v
    vmrz.py
       |
       |-- Receive MRZ lines
       |-- Normalize MRZ
       |-- Detect MRZ format
       |-- Decode MRZ
       |-- Validate check digits
       |-- Extract fields
       |-- Save mrz.json
       |
       v
    visa.py

IMPORTANT
---------

This module is specifically used by visa.py.

It does NOT perform the complete visa validation.

It only performs MRZ processing and returns the MRZ result.

The output file is:

    mrz.json

The same filename is used by the passport MRZ processor.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

MRZ_OUTPUT_FILE = BASE_DIR / "mrz.json"


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("visa_mrz")


# ============================================================
# MRZ CHARACTER VALUES
# ============================================================

MRZ_VALUES = {
    **{
        str(index): index
        for index in range(10)
    },

    "A": 10,
    "B": 11,
    "C": 12,
    "D": 13,
    "E": 14,
    "F": 15,
    "G": 16,
    "H": 17,
    "I": 18,
    "J": 19,
    "K": 20,
    "L": 21,
    "M": 22,
    "N": 23,
    "O": 24,
    "P": 25,
    "Q": 26,
    "R": 27,
    "S": 28,
    "T": 29,
    "U": 30,
    "V": 31,
    "W": 32,
    "X": 33,
    "Y": 34,
    "Z": 35,
    "<": 0,
}


# ============================================================
# WEIGHTS
# ============================================================

MRZ_WEIGHTS = [
    7,
    3,
    1,
]


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_line(line: Any) -> str:
    """
    Normalize an MRZ line.

    MRZ should contain:
        A-Z
        0-9
        <

    Spaces and unsupported characters are removed.
    """

    if line is None:
        return ""

    value = str(line).upper().strip()

    value = value.replace(" ", "")
    value = value.replace("\n", "")
    value = value.replace("\r", "")

    # Keep only valid MRZ characters.
    value = re.sub(
        r"[^A-Z0-9<]",
        "",
        value
    )

    return value


def calculate_check_digit(
    value: str
) -> Optional[int]:
    """
    Calculate an ICAO-style MRZ check digit.
    """

    if not isinstance(value, str):
        return None

    total = 0

    for index, character in enumerate(value):

        if character not in MRZ_VALUES:
            return None

        character_value = MRZ_VALUES[character]

        weight = MRZ_WEIGHTS[
            index % len(MRZ_WEIGHTS)
        ]

        total += character_value * weight

    return total % 10


def validate_check_digit(
    value: str,
    check_digit: str
) -> bool:
    """
    Validate an MRZ check digit.
    """

    if not value:
        return False

    if not check_digit:
        return False

    if not check_digit.isdigit():
        return False

    calculated = calculate_check_digit(
        value
    )

    if calculated is None:
        return False

    return calculated == int(check_digit)


# ============================================================
# NAME DECODING
# ============================================================

def decode_name(
    name_field: str
) -> Dict[str, Optional[str]]:
    """
    Decode the name field from MRZ.

    Format:

        SURNAME<<GIVEN<NAMES

    Example:

        TRAVELER<<HAPPYPERSON
    """

    if not name_field:
        return {
            "surname": None,
            "given_name": None,
            "full_name": None,
        }

    name_field = name_field.rstrip("<")

    parts = name_field.split(
        "<<",
        1
    )

    surname = parts[0].replace(
        "<",
        " "
    ).strip()

    given_name = ""

    if len(parts) > 1:

        given_name = parts[1].replace(
            "<",
            " "
        ).strip()

    full_name = surname

    if given_name:
        full_name = (
            f"{surname}, {given_name}"
        )

    return {
        "surname": surname or None,
        "given_name": given_name or None,
        "full_name": full_name or None,
    }


# ============================================================
# DATE DECODING
# ============================================================

def decode_mrz_date(
    value: str
) -> Optional[str]:
    """
    Convert YYMMDD into YYYY-MM-DD.

    The MRZ uses a two-digit year.

    Years >= 50 are interpreted as 19xx.
    Years < 50 are interpreted as 20xx.
    """

    if not value:
        return None

    if len(value) != 6:
        return None

    if not value.isdigit():
        return None

    year = int(value[0:2])
    month = int(value[2:4])
    day = int(value[4:6])

    if year >= 50:
        full_year = 1900 + year
    else:
        full_year = 2000 + year

    try:

        date_object = datetime(
            full_year,
            month,
            day,
        )

    except ValueError:

        return None

    return date_object.strftime(
        "%Y-%m-%d"
    )


# ============================================================
# FORMAT DETECTION
# ============================================================

def detect_mrz_format(
    line_1: str,
    line_2: str
) -> str:
    """
    Detect common MRZ formats.

    TD3:
        2 lines
        44 characters each

    TD2:
        2 lines
        36 characters each

    TD1:
        3 lines
        30 characters each

    Visa MRZ data provided by the current OCR pipeline
    is processed as a two-line MRZ.
    """

    if (
        len(line_1) == 44
        and len(line_2) == 44
    ):
        return "TD3"

    if (
        len(line_1) == 36
        and len(line_2) == 36
    ):
        return "TD2"

    return "UNKNOWN"


# ============================================================
# TD3 DECODER
# ============================================================

def decode_td3(
    line_1: str,
    line_2: str
) -> Dict[str, Any]:
    """
    Decode a standard two-line 44-character MRZ.

    This is the same basic MRZ layout used by passports
    and the visa MRZ provided by the current OCR pipeline.
    """

    result: Dict[str, Any] = {
        "format": "TD3",
        "line_1": line_1,
        "line_2": line_2,
        "fields": {},
        "check_digits": {},
        "errors": [],
    }

    if len(line_1) != 44:
        result["errors"].append(
            f"MRZ line 1 must contain 44 characters; "
            f"received {len(line_1)}."
        )

    if len(line_2) != 44:
        result["errors"].append(
            f"MRZ line 2 must contain 44 characters; "
            f"received {len(line_2)}."
        )

    if result["errors"]:
        return result

    # --------------------------------------------------------
    # LINE 1
    # --------------------------------------------------------

    document_code = line_1[0]

    issuing_country = line_1[2:5]

    name_field = line_1[5:44]

    name_data = decode_name(
        name_field
    )

    result["fields"].update({
        "document_code": document_code,
        "issuing_country": issuing_country,
        "surname": name_data["surname"],
        "given_name": name_data["given_name"],
        "full_name": name_data["full_name"],
    })

    # --------------------------------------------------------
    # LINE 2
    #
    # TD3:
    #
    # 0-8     document number
    # 9       check digit
    # 10-12   nationality
    # 13-18   DOB
    # 19      DOB check digit
    # 20      sex
    # 21-26   expiry date
    # 27      expiry check digit
    # 28-42   optional data
    # 43      final check digit
    # --------------------------------------------------------

    document_number_raw = line_2[0:9]

    document_number = (
        document_number_raw
        .replace("<", "")
    )

    document_number_check = line_2[9]

    nationality = line_2[10:13]

    date_of_birth_raw = line_2[13:19]

    date_of_birth = decode_mrz_date(
        date_of_birth_raw
    )

    date_of_birth_check = line_2[19]

    sex = line_2[20]

    expiry_date_raw = line_2[21:27]

    expiry_date = decode_mrz_date(
        expiry_date_raw
    )

    expiry_date_check = line_2[27]

    optional_data = line_2[28:43]

    final_check_digit = line_2[43]

    result["fields"].update({

        "document_number": document_number,

        "nationality": nationality,

        "date_of_birth": date_of_birth,

        "sex": (
            None
            if sex == "<"
            else sex
        ),

        "expiry_date": expiry_date,

        "optional_data": (
            optional_data.replace(
                "<",
                ""
            )
            or None
        ),
    })

    # ========================================================
    # CHECK DIGIT VALIDATION
    # ========================================================

    document_number_valid = validate_check_digit(
        document_number_raw,
        document_number_check
    )

    dob_valid = validate_check_digit(
        date_of_birth_raw,
        date_of_birth_check
    )

    expiry_valid = validate_check_digit(
        expiry_date_raw,
        expiry_date_check
    )

    # Composite check:
    #
    # document number + check digit
    # DOB + check digit
    # expiry + check digit
    # optional data + final check digit
    #

    composite_value = (
        line_2[0:10]
        + line_2[13:20]
        + line_2[21:43]
    )

    composite_valid = validate_check_digit(
        composite_value,
        final_check_digit
    )

    result["check_digits"] = {

        "document_number": {
            "expected": document_number_check,
            "calculated": calculate_check_digit(
                document_number_raw
            ),
            "valid": document_number_valid,
        },

        "date_of_birth": {
            "expected": date_of_birth_check,
            "calculated": calculate_check_digit(
                date_of_birth_raw
            ),
            "valid": dob_valid,
        },

        "expiry_date": {
            "expected": expiry_date_check,
            "calculated": calculate_check_digit(
                expiry_date_raw
            ),
            "valid": expiry_valid,
        },

        "composite": {
            "expected": final_check_digit,
            "calculated": calculate_check_digit(
                composite_value
            ),
            "valid": composite_valid,
        },
    }

    # --------------------------------------------------------
    # Collect errors
    # --------------------------------------------------------

    if not document_number_valid:

        result["errors"].append(
            "Document number check digit is invalid."
        )

    if not dob_valid:

        result["errors"].append(
            "Date of birth check digit is invalid."
        )

    if not expiry_valid:

        result["errors"].append(
            "Expiry date check digit is invalid."
        )

    if not composite_valid:

        result["errors"].append(
            "Final composite MRZ check digit is invalid."
        )

    result["success"] = (
        len(result["errors"]) == 0
    )

    return result


# ============================================================
# GENERIC MRZ DECODER
# ============================================================

def decode_mrz(
    mrz_lines: List[str]
) -> Dict[str, Any]:
    """
    Decode the supplied MRZ lines.
    """

    result: Dict[str, Any] = {

        "success": False,

        "format": "UNKNOWN",

        "line_1": None,

        "line_2": None,

        "fields": {},

        "check_digits": {},

        "errors": [],
    }

    if not isinstance(
        mrz_lines,
        list
    ):

        result["errors"].append(
            "MRZ lines must be provided as a list."
        )

        return result

    if len(mrz_lines) < 2:

        result["errors"].append(
            "At least two MRZ lines are required."
        )

        return result

    line_1 = normalize_line(
        mrz_lines[0]
    )

    line_2 = normalize_line(
        mrz_lines[1]
    )

    result["line_1"] = line_1
    result["line_2"] = line_2

    mrz_format = detect_mrz_format(
        line_1,
        line_2
    )

    result["format"] = mrz_format

    # --------------------------------------------------------
    # TD3
    # --------------------------------------------------------

    if mrz_format == "TD3":

        decoded = decode_td3(
            line_1,
            line_2
        )

        return decoded

    # --------------------------------------------------------
    # TD2
    # --------------------------------------------------------

    if mrz_format == "TD2":

        result["errors"].append(
            "TD2 MRZ detected. "
            "TD2 visa decoding is not implemented "
            "in this module."
        )

        return result

    # --------------------------------------------------------
    # Unknown
    # --------------------------------------------------------

    result["errors"].append(
        "Unsupported or invalid MRZ format."
    )

    return result


# ============================================================
# SAVE MRZ JSON
# ============================================================

def save_mrz_json(
    data: Dict[str, Any]
) -> None:
    """
    Save MRZ processing result to mrz.json.
    """

    output = {

        "document_type": "visa",

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "mrz_validation": data,
    }

    with MRZ_OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        "Visa MRZ result saved to: %s",
        MRZ_OUTPUT_FILE
    )


# ============================================================
# MAIN VISA MRZ PROCESSOR
# ============================================================

def process_mrz(
    mrz_lines: List[str]
) -> Dict[str, Any]:
    """
    Main entry point used by visa.py.
    """

    logger.info(
        "Starting VISA MRZ processing."
    )

    result = decode_mrz(
        mrz_lines
    )

    save_mrz_json(
        result
    )

    logger.info(
        "VISA MRZ processing completed."
    )

    return result


# ============================================================
# ALIAS
# ============================================================

def process_visa_mrz(
    mrz_lines: List[str]
) -> Dict[str, Any]:
    """
    Explicit visa MRZ entry point.

    This is an alias around process_mrz().
    """

    return process_mrz(
        mrz_lines
    )


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        )
    )

    sample_mrz = [

        "VNUSATRAVELER<<HAPPYPERSON<<<<<<<<<<<<<<<<<<",

        "555123ABC6GBR6502056F0412236IFLND00AMS803085",
    ]

    result = process_visa_mrz(
        sample_mrz
    )

    # OUTPUT FORMATTING CHANGE ONLY:
    # Print the already-returned four-field result without
    # verbose indentation or intermediate MRZ details.
    print(
        json.dumps(
            result,
            ensure_ascii=False
        )
    )