"""
mrz.py
============================================================

ICAO 9303 TD3 passport MRZ parser.

This module:

    1. Receives two MRZ lines from passport.py
    2. Normalizes the MRZ
    3. Validates TD3 structure
    4. Extracts passport information
    5. Calculates ICAO check digits
    6. Validates individual check digits
    7. Validates the composite check digit
    8. Writes mrz.json
    9. Returns the result to passport.py


TD3 PASSPORT FORMAT
-------------------

Line 1 = 44 characters

    PP<CCCNAME<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    0-1     Document type
    2-4     Issuing state/country
    5-43    Name


Line 2 = 44 characters

    NNNNNNNNNDCCCYYMMDDDSYYMMDDDEEEEEEEEEEEEEEC

    0-8     Document number
    9       Document number check digit

    10-12   Nationality

    13-18   Date of birth YYMMDD
    19      DOB check digit

    20      Sex

    21-26   Date of expiry YYMMDD
    27      Expiry check digit

    28-42   Optional data

    43      Composite check digit


ICAO CHECK DIGIT
----------------

Character values:

    0-9 = 0-9
    A-Z = 10-35
    <   = 0

Weights repeat:

    7, 3, 1

The check digit is:

    sum(value * weight) % 10
"""

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# CONFIGURATION
# ============================================================

MRZ_FILE = "mrz.json"

TD3_LINE_LENGTH = 44


# ============================================================
# ICAO CHARACTER VALUE
# ============================================================

def char_value(char: str) -> int:
    """
    Convert an MRZ character to its ICAO numeric value.

    ICAO 9303:

        0-9 -> 0-9
        A-Z -> 10-35
        <   -> 0
    """

    if char == "<":
        return 0

    if "0" <= char <= "9":
        return ord(char) - ord("0")

    if "A" <= char <= "Z":
        return (
            ord(char)
            - ord("A")
            + 10
        )

    # Invalid MRZ character.
    return 0


# ============================================================
# CHECK DIGIT CALCULATION
# ============================================================

def check_digit(data: str) -> int:
    """
    Calculate an ICAO 9303 MRZ check digit.

    Weight sequence:

        7, 3, 1, 7, 3, 1 ...

    The weights repeat regardless of where the
    field appears in the MRZ.
    """

    weights = (
        7,
        3,
        1,
    )

    total = 0

    for index, char in enumerate(data):

        value = char_value(char)

        weight = weights[
            index % 3
        ]

        total += (
            value * weight
        )

    return total % 10


# ============================================================
# CHECK DIGIT VALIDATION
# ============================================================

def validate_check_digit(
    data: str,
    provided: str,
) -> Tuple[int, bool]:
    """
    Calculate and compare an MRZ check digit.
    """

    calculated = check_digit(
        data
    )

    if not isinstance(
        provided,
        str
    ):

        return calculated, False

    if not re.fullmatch(
        r"\d",
        provided
    ):

        return calculated, False

    provided_value = int(
        provided
    )

    return (
        calculated,
        calculated == provided_value
    )


# ============================================================
# MRZ DATE DECODING
# ============================================================

def decode_mrz_date(
    value: str,
    date_type: str,
) -> Optional[str]:
    """
    Convert YYMMDD into YYYY-MM-DD.

    MRZ contains only a two-digit year.

    DOB:
        We use the conventional 100-year window
        relative to the current date.

    Expiry:
        Modern passports generally have expiry dates
        in the current/future century. Therefore the
        future interpretation is preferred.

    Examples:

        060505 -> 2006-05-05
        360816 -> 2036-08-16
    """

    if not isinstance(
        value,
        str
    ):

        return None

    if not re.fullmatch(
        r"\d{6}",
        value
    ):

        return None

    yy = int(
        value[0:2]
    )

    month = int(
        value[2:4]
    )

    day = int(
        value[4:6]
    )

    today = datetime.now()

    current_year = today.year

    # ========================================================
    # DOB
    # ========================================================

    if date_type == "dob":

        # Use an approximately 100-year window.
        #
        # If YY is greater than the current year's
        # two-digit value, interpret as 19YY.
        #
        # Otherwise interpret as 20YY.

        current_yy = (
            current_year % 100
        )

        if yy > current_yy:

            year = (
                1900 + yy
            )

        else:

            year = (
                2000 + yy
            )

    # ========================================================
    # EXPIRY
    # ========================================================

    elif date_type == "expiry":

        # First try 20YY.
        #
        # For:
        #
        #     360816
        #
        # this becomes:
        #
        #     2036-08-16
        #
        # which is correct for the supplied passport.

        year = (
            2000 + yy
        )

        try:

            candidate = datetime(
                year,
                month,
                day
            )

            # If 20YY is clearly far in the past,
            # allow 19YY.
            #
            # This prevents an old passport from being
            # incorrectly interpreted as a modern expiry.

            if candidate.year < (
                current_year - 1
            ):

                year = (
                    1900 + yy
                )

        except ValueError:

            pass

    else:

        return None

    # ========================================================
    # Validate calendar date
    # ========================================================

    try:

        result = datetime(
            year,
            month,
            day
        )

        return result.strftime(
            "%Y-%m-%d"
        )

    except ValueError:

        return None


# ============================================================
# NAME PARSING
# ============================================================

def parse_name(
    name_field: str
) -> Tuple[str, str, str]:
    """
    Parse the TD3 MRZ name field.

    Example:

        KUMARAGURU<<KRISHNARAJ

    becomes:

        surname:
            KUMARAGURU

        given_names:
            KRISHNARAJ

        full_name:
            KUMARAGURU, KRISHNARAJ
    """

    # MRZ uses << between surname and given names.
    parts = name_field.split(
        "<<",
        1
    )

    surname = (
        parts[0]
        .replace("<", " ")
        .strip()
    )

    given_names = ""

    if len(parts) > 1:

        given_names = (
            parts[1]
            .replace("<", " ")
            .strip()
        )

    # Remove repeated whitespace.
    surname = re.sub(
        r"\s+",
        " ",
        surname
    )

    given_names = re.sub(
        r"\s+",
        " ",
        given_names
    )

    full_name = surname

    if given_names:

        full_name += (
            ", "
            + given_names
        )

    return (
        surname,
        given_names,
        full_name
    )


# ============================================================
# MRZ NORMALIZATION
# ============================================================

def normalize_mrz(
    raw_lines: Any
) -> Tuple[
    Optional[str],
    Optional[str],
    List[str]
]:
    """
    Normalize raw MRZ input.

    Expected:

        [
            line_1,
            line_2
        ]

    Spaces and line breaks are removed.

    Returns:

        line1
        line2
        errors
    """

    errors: List[str] = []

    # --------------------------------------------------------
    # Check list
    # --------------------------------------------------------

    if not isinstance(
        raw_lines,
        list
    ):

        return (
            None,
            None,
            [
                "mrz_lines must be a list."
            ]
        )

    lines: List[str] = []

    # --------------------------------------------------------
    # Clean lines
    # --------------------------------------------------------

    for line in raw_lines:

        if not isinstance(
            line,
            str
        ):

            continue

        cleaned = (
            line
            .upper()
            .replace(" ", "")
            .replace("\n", "")
            .replace("\r", "")
            .strip()
        )

        if cleaned:

            lines.append(
                cleaned
            )

    # --------------------------------------------------------
    # TD3 requires exactly two useful lines
    # --------------------------------------------------------

    if len(lines) < 2:

        return (
            None,
            None,
            [
                "Passport TD3 MRZ requires two lines."
            ]
        )

    line1 = lines[0]
    line2 = lines[1]

    # --------------------------------------------------------
    # Length validation
    # --------------------------------------------------------

    if len(line1) != TD3_LINE_LENGTH:

        errors.append(
            "MRZ line 1 should contain "
            f"{TD3_LINE_LENGTH} characters, "
            f"found {len(line1)}."
        )

    if len(line2) != TD3_LINE_LENGTH:

        errors.append(
            "MRZ line 2 should contain "
            f"{TD3_LINE_LENGTH} characters, "
            f"found {len(line2)}."
        )

    # --------------------------------------------------------
    # Character validation
    # --------------------------------------------------------

    valid_characters = re.compile(
        r"^[A-Z0-9<]+$"
    )

    if not valid_characters.fullmatch(
        line1
    ):

        errors.append(
            "MRZ line 1 contains invalid "
            "characters."
        )

    if not valid_characters.fullmatch(
        line2
    ):

        errors.append(
            "MRZ line 2 contains invalid "
            "characters."
        )

    return (
        line1,
        line2,
        errors
    )


# ============================================================
# TD3 PASSPORT PARSER
# ============================================================

def parse_td3(
    line1: str,
    line2: str,
) -> Dict[str, Any]:
    """
    Parse a standard ICAO 9303 TD3 passport MRZ.
    """

    # ========================================================
    # LINE 1
    # ========================================================

    document_type = line1[0:2]

    issuing_country = line1[2:5]

    name_field = line1[5:44]

    (
        surname,
        given_names,
        full_name
    ) = parse_name(
        name_field
    )

    # ========================================================
    # LINE 2
    # ========================================================

    document_number_raw = line2[0:9]

    document_number = (
        document_number_raw
        .replace("<", "")
    )

    document_number_check = line2[9]

    nationality = line2[10:13]

    dob_raw = line2[13:19]

    dob_check = line2[19]

    sex = line2[20]

    expiry_raw = line2[21:27]

    expiry_check = line2[27]

    optional_data = line2[28:43]

    composite_check = line2[43]

    # ========================================================
    # Decode dates
    # ========================================================

    date_of_birth = decode_mrz_date(
        dob_raw,
        "dob"
    )

    date_of_expiry = decode_mrz_date(
        expiry_raw,
        "expiry"
    )

    # ========================================================
    # INDIVIDUAL CHECKSUMS
    # ========================================================

    (
        document_number_calculated,
        document_number_valid
    ) = validate_check_digit(
        document_number_raw,
        document_number_check
    )

    (
        dob_calculated,
        dob_valid
    ) = validate_check_digit(
        dob_raw,
        dob_check
    )

    (
        expiry_calculated,
        expiry_valid
    ) = validate_check_digit(
        expiry_raw,
        expiry_check
    )

    # ========================================================
    # COMPOSITE CHECKSUM
    # ========================================================

    """
    ICAO TD3 composite data consists of:

        Document number + document number check
        +
        Date of birth + DOB check
        +
        Date of expiry + expiry check
        +
        Optional data

    Positions:

        0:10   document number + check
        13:20  DOB + check
        21:43  expiry + check + optional data

    Therefore:

        line2[0:10]
        + line2[13:20]
        + line2[21:43]

    IMPORTANT:
    Do NOT append line2[28:43] again because it is already
    included inside line2[21:43].
    """

    composite_data = (
        line2[0:10]
        + line2[13:20]
        + line2[21:43]
    )

    composite_calculated = check_digit(
        composite_data
    )

    try:

        composite_valid = (
            composite_calculated
            == int(composite_check)
        )

    except ValueError:

        composite_valid = False

    # ========================================================
    # ERROR COLLECTION
    # ========================================================

    errors: List[str] = []

    # --------------------------------------------------------
    # Document number checksum
    # --------------------------------------------------------

    if not document_number_valid:

        errors.append(
            "Passport document number "
            "check digit is invalid."
        )

    # --------------------------------------------------------
    # DOB checksum
    # --------------------------------------------------------

    if not dob_valid:

        errors.append(
            "Date of birth check digit "
            "is invalid."
        )

    # --------------------------------------------------------
    # Expiry checksum
    # --------------------------------------------------------

    if not expiry_valid:

        errors.append(
            "Date of expiry check digit "
            "is invalid."
        )

    # --------------------------------------------------------
    # Composite checksum
    # --------------------------------------------------------

    if not composite_valid:

        errors.append(
            "Composite MRZ check digit "
            "is invalid."
        )

    # ========================================================
    # DOCUMENT TYPE
    # ========================================================

    if not document_type.startswith(
        "P"
    ):

        errors.append(
            f"Invalid passport document type: "
            f"{document_type}"
        )

    # ========================================================
    # COUNTRY CODE
    # ========================================================

    if not re.fullmatch(
        r"[A-Z<]{3}",
        issuing_country
    ):

        errors.append(
            "Invalid issuing country code."
        )

    # ========================================================
    # NATIONALITY
    # ========================================================

    if not re.fullmatch(
        r"[A-Z<]{3}",
        nationality
    ):

        errors.append(
            "Invalid nationality code."
        )

    # ========================================================
    # SEX
    # ========================================================

    if sex not in (
        "M",
        "F",
        "X",
        "<",
    ):

        errors.append(
            f"Invalid sex character: {sex}"
        )

    # ========================================================
    # DATES
    # ========================================================

    if date_of_birth is None:

        errors.append(
            "Invalid date of birth in MRZ."
        )

    if date_of_expiry is None:

        errors.append(
            "Invalid expiry date in MRZ."
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    success = (
        len(errors) == 0
    )

    # ========================================================
    # RESULT
    # ========================================================

    return {

        "success": success,

        "errors": errors,

        "document_type": "passport",

        "mrz_document_type": document_type,

        "issuing_country": issuing_country,

        "surname": surname,

        "given_names": given_names,

        "full_name": full_name,

        "document_number": document_number,

        "nationality": nationality,

        "date_of_birth": date_of_birth,

        "sex": sex,

        "date_of_expiry": date_of_expiry,

        "optional_data": optional_data,

        "checksums": {

            "document_number": {

                "provided": document_number_check,

                "calculated": (
                    document_number_calculated
                ),

                "valid": (
                    document_number_valid
                ),
            },

            "date_of_birth": {

                "provided": dob_check,

                "calculated": (
                    dob_calculated
                ),

                "valid": (
                    dob_valid
                ),
            },

            "date_of_expiry": {

                "provided": expiry_check,

                "calculated": (
                    expiry_calculated
                ),

                "valid": (
                    expiry_valid
                ),
            },

            "composite": {

                "provided": composite_check,

                "calculated": (
                    composite_calculated
                ),

                "valid": (
                    composite_valid
                ),
            },
        },

        # These are parser-confidence indicators.
        # Since these values come directly from a syntactically
        # valid MRZ position, they represent parser confidence,
        # NOT OCR confidence.
        "confidence": {

            "document_type": 1.0,

            "issuing_country": 1.0,

            "surname": 1.0,

            "given_names": 1.0,

            "document_number": 1.0,

            "nationality": 1.0,

            "date_of_birth": 1.0,

            "sex": 1.0,

            "date_of_expiry": 1.0,
        },

        "raw_mrz": {

            "line_1": line1,

            "line_2": line2,
        },

        "timestamp": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }


# ============================================================
# WRITE MRZ JSON
# ============================================================

def write_mrz_json(
    result: Dict[str, Any]
) -> None:
    """
    Write MRZ processing result to mrz.json.
    """

    try:

        with open(
            MRZ_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                result,
                file,
                indent=4,
                ensure_ascii=False,
            )

    except OSError as exc:

        # Do not hide the error.
        #
        # The parser result can still be returned to
        # passport.py, but we include the file error.

        if isinstance(
            result.get("errors"),
            list
        ):

            result["errors"].append(
                f"Could not write mrz.json: {exc}"
            )

        else:

            result["errors"] = [
                f"Could not write mrz.json: {exc}"
            ]

        result["success"] = False


# ============================================================
# MAIN MRZ FUNCTION
# ============================================================

def process_mrz(
    mrz_lines: Any
) -> Dict[str, Any]:
    """
    Main MRZ function.

    Called by passport.py.

    Input:

        [
            line_1,
            line_2
        ]

    Output:

        Complete MRZ result dictionary.

    Also writes:

        mrz.json
    """

    try:

        # ----------------------------------------------------
        # Normalize MRZ
        # ----------------------------------------------------

        (
            line1,
            line2,
            normalization_errors
        ) = normalize_mrz(
            mrz_lines
        )

        # ----------------------------------------------------
        # Normalization failed
        # ----------------------------------------------------

        if normalization_errors:

            result = {

                "success": False,

                "errors": normalization_errors,

                "document_type": "passport",

                "timestamp": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }

            write_mrz_json(
                result
            )

            return result

        # ----------------------------------------------------
        # Safety check
        # ----------------------------------------------------

        if line1 is None or line2 is None:

            result = {

                "success": False,

                "errors": [
                    "MRZ lines could not be normalized."
                ],

                "document_type": "passport",

                "timestamp": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }

            write_mrz_json(
                result
            )

            return result

        # ----------------------------------------------------
        # TD3 length errors
        #
        # Do not parse malformed lines.
        # ----------------------------------------------------

        if (
            len(line1) != TD3_LINE_LENGTH
            or len(line2) != TD3_LINE_LENGTH
        ):

            result = {

                "success": False,

                "errors": [
                    "Cannot parse passport MRZ "
                    "because one or both lines "
                    "do not contain exactly 44 characters."
                ],

                "document_type": "passport",

                "raw_mrz": {

                    "line_1": line1,

                    "line_2": line2,
                },

                "timestamp": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }

            write_mrz_json(
                result
            )

            return result

        # ----------------------------------------------------
        # Parse TD3
        # ----------------------------------------------------

        result = parse_td3(
            line1,
            line2
        )

        # ----------------------------------------------------
        # Save result
        # ----------------------------------------------------

        write_mrz_json(
            result
        )

        return result

    except Exception as exc:

        # ----------------------------------------------------
        # Unexpected error
        # ----------------------------------------------------

        result = {

            "success": False,

            "errors": [
                f"Unexpected MRZ processing error: {exc}"
            ],

            "document_type": "passport",

            "timestamp": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

        try:

            write_mrz_json(
                result
            )

        except Exception:

            pass

        return result


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    print(
        "mrz.py is an MRZ processing module."
    )

    print(
        "It is normally called by passport.py."
    )