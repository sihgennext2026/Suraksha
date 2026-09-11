"""
conversion.py
=============

ENTRY POINT OF THE DOCUMENT VALIDATION SYSTEM.

FLOW:

    realinput.json
          |
          v
    conversion.py
          |
          |-- Read raw OCR JSON
          |-- Detect document type
          |-- Extract required fields
          |-- Normalize field names
          |-- Preserve MRZ
          |
          v
       input.json
          |
          v
       main.py
          |
          |-- Detect document type
          |
          |-- passport -> passport/passport.py
          |-- visa     -> visaprocess/visa.py
          |-- voterid  -> voterid.py
          |-- license  -> license.py
          |-- nationalid -> nationalid/aadhar.py
          |
          v
       output.json

IMPORTANT:
-----------

conversion.py does NOT validate documents.

It only converts the raw OCR result into a clean,
standardized input.json.

After conversion succeeds, conversion.py automatically
starts main.py.

If any part of the workflow fails, output.json will contain:

{
    "status": "invalid",
    "reason": "..."
}
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

REAL_INPUT_FILE = BASE_DIR / "realinput.json"
INPUT_FILE = BASE_DIR / "input.json"
OUTPUT_FILE = BASE_DIR / "output.json"

LOG_FILE = BASE_DIR / "conversion.log"

MAIN_FILE = BASE_DIR / "main.py"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("conversion")


# ============================================================
# INVALID OUTPUT
# ============================================================

def create_invalid_output(
    reason: str
) -> None:
    """
    Create output.json when the workflow fails.

    This prevents the system from ending with only
    SystemExit: 1 without producing a useful result.
    """

    invalid_result = {
        "status": "invalid",
        "reason": reason
    }

    try:

        with OUTPUT_FILE.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                invalid_result,
                file,
                indent=4,
                ensure_ascii=False
            )

        logger.error(
            "Invalid result saved to: %s",
            OUTPUT_FILE
        )

    except Exception as exc:

        logger.exception(
            "Could not create output.json: %s",
            exc
        )


# ============================================================
# JSON FUNCTIONS
# ============================================================

def load_json(
    file_path: Path
) -> Dict[str, Any]:
    """
    Read and parse a JSON file.
    """

    logger.info(
        "Reading file: %s",
        file_path
    )

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
            "JSON root must be an object."
        )

    logger.info(
        "JSON loaded successfully."
    )

    return data


def save_json(
    file_path: Path,
    data: Dict[str, Any]
) -> None:
    """
    Save dictionary data into a formatted JSON file.
    """

    logger.info(
        "Writing JSON to: %s",
        file_path
    )

    with file_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    logger.info(
        "JSON created successfully: %s",
        file_path
    )


# ============================================================
# DOCUMENT TYPE DETECTION
# ============================================================

def detect_document_type(
    data: Dict[str, Any]
) -> Optional[str]:
    """
    Detect the document type from the raw OCR JSON.

    Supported types:

        passport
        visa
        nationalid
        license
    """

    document_type = data.get(
        "document_type"
    )

    if not isinstance(
        document_type,
        str
    ):

        return None

    document_type = (
        document_type
        .strip()
        .lower()
    )

    aliases = {

        # Passport
        "passport": "passport",
        "passports": "passport",

        # Visa
        "visa": "visa",
        "visas": "visa",

        # national id
        "nationalid": "nationalid",
        "nationalid": "nationalid",
        "nationalid": "nationalid",
        "nationalid": "nationalid",
        "national_id": "nationalid",
        "national-id": "nationalid",
        "national id": "nationalid",
        "aadhaar": "nationalid",
        "aadhar": "nationalid",

        # Driving License
        "license": "license",
        "licence": "license",
        "driving_license": "license",
        "driving_licence": "license",
        "driving license": "license",
        "driving licence": "license",
    }

    normalized = aliases.get(
        document_type
    )

    if normalized:

        logger.info(
            "Detected document type: %s",
            normalized
        )

    else:

        logger.warning(
            "Unknown document type received: %s",
            document_type
        )

    return normalized


# ============================================================
# FIELD HELPER
# ============================================================

def get_structured_fields(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract the structured_fields section
    from the raw OCR result.
    """

    fields = data.get(
        "structured_fields"
    )

    if isinstance(
        fields,
        dict
    ):

        return fields

    logger.warning(
        "structured_fields not found."
    )

    return {}


# ============================================================
# MRZ EXTRACTION
# ============================================================

def extract_mrz(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract MRZ lines from the raw OCR JSON.

    MRZ is preserved exactly as OCR produced it.
    """

    mrz_lines = data.get(
        "mrz_lines"
    )

    if not isinstance(
        mrz_lines,
        list
    ):

        logger.warning(
            "No MRZ lines found."
        )

        return {
            "line_1": None,
            "line_2": None,
        }

    lines: List[str] = [
        str(line).strip()
        for line in mrz_lines
        if isinstance(line, str)
    ]

    result = {

        "line_1": (
            lines[0]
            if len(lines) >= 1
            else None
        ),

        "line_2": (
            lines[1]
            if len(lines) >= 2
            else None
        ),
    }

    logger.info(
        "MRZ lines extracted: %d",
        len(lines)
    )

    return result


# ============================================================
# PASSPORT CONVERSION
# ============================================================

def convert_passport(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convert raw passport OCR JSON into
    standardized passport structure.
    """

    fields = get_structured_fields(
        data
    )

    mrz = extract_mrz(
        data
    )

    passport_data = {

        "document_number": fields.get(
            "document_number",
            fields.get("passport_number")
        ),

        "surname": fields.get(
            "surname"
        ),

        "given_name": fields.get(
            "given_name"
        ),

        "full_name": fields.get(
            "name"
        ),

        "date_of_birth": fields.get(
            "date_of_birth"
        ),

        "sex": fields.get(
            "sex"
        ),

        "nationality": fields.get(
            "nationality"
        ),

        "issue_date": fields.get(
            "issue_date"
        ),

        "expiry_date": fields.get(
            "expiry_date"
        ),

        "name_native": fields.get(
            "name_native"
        ),

        "father_name": fields.get(
            "father_name"
        ),

        "issuing_authority": fields.get(
            "issuing_authority"
        ),
    }

    converted = {

        "document_type": "passport",

        "passport": passport_data,

        "mrz": mrz,
    }

    logger.info(
        "Passport data converted successfully."
    )

    return converted


# ============================================================
# VISA CONVERSION
# ============================================================

def convert_visa(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convert raw visa OCR JSON into
    standardized visa structure.
    """

    fields = get_structured_fields(
        data
    )

    mrz = extract_mrz(
        data
    )

    visa_data = {

        "full_name": fields.get(
            "name"
        ),

        "surname": fields.get(
            "surname"
        ),

        "given_name": fields.get(
            "given_name"
        ),

        "date_of_birth": fields.get(
            "date_of_birth"
        ),

        "passport_number": fields.get(
            "passport_number"
        ),

        "visa_number": fields.get(
            "visa_number"
        ),

        "nationality": fields.get(
            "nationality"
        ),

        "issue_date": fields.get(
            "issue_date"
        ),

        "expiry_date": fields.get(
            "expiry_date"
        ),

        "name_native": fields.get(
            "name_native"
        ),
    }

    converted = {

        "document_type": "visa",

        "visa": visa_data,

        "mrz": mrz,
    }

    logger.info(
        "Visa data converted successfully."
    )

    return converted


# ============================================================
# DRIVING LICENSE CONVERSION
# ============================================================

def convert_license(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convert raw driving-license OCR JSON into
    standardized license structure.
    """

    fields = get_structured_fields(
        data
    )

    license_data = {

        "name": fields.get(
            "name"
        ),

        "name_native": fields.get(
            "name_native"
        ),

        "father_name": fields.get(
            "father_name"
        ),

        "date_of_birth": fields.get(
            "date_of_birth"
        ),

        "sex": fields.get(
            "sex"
        ),

        "document_number": fields.get(
            "document_number"
        ),

        "issue_date": fields.get(
            "issue_date"
        ),

        "expiry_date": fields.get(
            "expiry_date"
        ),

        "address": fields.get(
            "address"
        ),

        "categories": fields.get(
            "categories"
        ),
    }

    converted = {

        "document_type": "license",

        "license": license_data,
    }

    logger.info(
        "Driving license data converted successfully."
    )

    return converted


# ============================================================
# NATIONAL ID CONVERSION
# ============================================================

def convert_nationalid(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convert raw Aadhaar OCR JSON into
    standardized national ID structure.
    """

    fields = get_structured_fields(
        data
    )

    aadhaar_number = fields.get(
        "document_number"
    )

    if aadhaar_number is None:

        aadhaar_number = fields.get(
            "aadhaar_number"
        )

    if aadhaar_number is None:

        aadhaar_number = fields.get(
            "aadhar_number"
        )

    if not isinstance(
        aadhaar_number,
        str
    ):

        aadhaar_number = ""

    converted = {

        "document_type": "nationalid",

        "nationalid": aadhaar_number,
    }

    logger.info(
        "National ID data converted successfully."
    )

    return converted


# ============================================================
# GENERIC CONVERSION
# ============================================================

def convert_document(
    data: Dict[str, Any],
    document_type: str
) -> Dict[str, Any]:
    """
    Convert the raw document according to its type.
    """

    # --------------------------------------------------------
    # Passport
    # --------------------------------------------------------

    if document_type == "passport":

        return convert_passport(
            data
        )

    # --------------------------------------------------------
    # Visa
    # --------------------------------------------------------

    if document_type == "visa":

        return convert_visa(
            data
        )

    # --------------------------------------------------------
    # Voter ID
    # --------------------------------------------------------

    if document_type == "nationalid":

        return convert_nationalid(
            data
        )

    # --------------------------------------------------------
    # Driving License
    # --------------------------------------------------------

    if document_type == "license":

        return convert_license(
            data
        )

    # --------------------------------------------------------
    # Unknown document
    # --------------------------------------------------------

    raise ValueError(
        f"Unsupported document type: {document_type}"
    )


# ============================================================
# VALIDATE CONVERSION RESULT
# ============================================================

def validate_converted_data(
    data: Dict[str, Any]
) -> None:
    """
    Basic checks to ensure conversion produced
    something usable by main.py.

    This is NOT document validation.
    """

    if not isinstance(
        data,
        dict
    ):

        raise ValueError(
            "Converted data is not a JSON object."
        )

    document_type = data.get(
        "document_type"
    )

    if not document_type:

        raise ValueError(
            "Converted JSON has no document_type."
        )

    # --------------------------------------------------------
    # Passport
    # --------------------------------------------------------

    if document_type == "passport":

        if "passport" not in data:

            raise ValueError(
                "Converted passport data is missing 'passport'."
            )

        if "mrz" not in data:

            raise ValueError(
                "Converted passport data is missing 'mrz'."
            )

        if not isinstance(
            data["passport"],
            dict
        ):

            raise ValueError(
                "'passport' must be an object."
            )

        if not isinstance(
            data["mrz"],
            dict
        ):

            raise ValueError(
                "'mrz' must be an object."
            )

    # --------------------------------------------------------
    # Visa
    # --------------------------------------------------------

    elif document_type == "visa":

        if "visa" not in data:

            raise ValueError(
                "Converted visa data is missing 'visa'."
            )

        if "mrz" not in data:

            raise ValueError(
                "Converted visa data is missing 'mrz'."
            )

        if not isinstance(
            data["visa"],
            dict
        ):

            raise ValueError(
                "'visa' must be an object."
            )

        if not isinstance(
            data["mrz"],
            dict
        ):

            raise ValueError(
                "'mrz' must be an object."
            )

    # --------------------------------------------------------
    # National ID
    # --------------------------------------------------------

    elif document_type == "nationalid":

        if "nationalid" not in data:

            raise ValueError(
                "Converted national ID data is missing 'nationalid'."
            )

        if not isinstance(
            data["nationalid"],
            str
        ):

            raise ValueError(
                "'nationalid' must be a string."
            )

    # --------------------------------------------------------
    # Driving License
    # --------------------------------------------------------

    elif document_type == "license":

        if "license" not in data:

            raise ValueError(
                "Converted license data is missing 'license'."
            )

        if not isinstance(
            data["license"],
            dict
        ):

            raise ValueError(
                "'license' must be an object."
            )

    logger.info(
        "Converted JSON structure validated successfully."
    )


# ============================================================
# START MAIN.PY
# ============================================================

def start_main() -> int:
    """
    Start main.py after conversion.

    If main.py fails for ANY reason, output.json
    will contain status = invalid.

    The actual error from main.py is also stored
    in the reason field.
    """

    logger.info(
        "Conversion completed."
    )

    logger.info(
        "Starting main.py..."
    )

    # --------------------------------------------------------
    # Check main.py
    # --------------------------------------------------------

    if not MAIN_FILE.exists():

        reason = (
            f"main.py not found: {MAIN_FILE}"
        )

        logger.error(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    try:

        logger.info(
            "Python interpreter: %s",
            sys.executable
        )

        logger.info(
            "Main file: %s",
            MAIN_FILE
        )

        # ----------------------------------------------------
        # Start main.py
        # ----------------------------------------------------

        result = subprocess.run(

            [
                sys.executable,
                str(MAIN_FILE)
            ],

            cwd=str(BASE_DIR),

            capture_output=True,

            text=True,
        )

        # ----------------------------------------------------
        # MAIN.PY OUTPUT
        # ----------------------------------------------------

        if result.stdout:

            logger.info(
                "========== MAIN.PY OUTPUT =========="
            )

            logger.info(
                "%s",
                result.stdout
            )

        # ----------------------------------------------------
        # MAIN.PY SUCCESS
        # ----------------------------------------------------

        if result.returncode == 0:

            logger.info(
                "main.py completed successfully."
            )

            return 0

        # ----------------------------------------------------
        # MAIN.PY FAILURE
        # ----------------------------------------------------

        logger.error(
            "main.py failed with exit code: %s",
            result.returncode
        )

        # Get the actual error
        if result.stderr:

            logger.error(
                "========== MAIN.PY ERROR =========="
            )

            logger.error(
                "%s",
                result.stderr
            )

            reason = (
                "Document validation failed. "
                "main.py error: "
                + result.stderr.strip()
            )

        else:

            reason = (
                "Document validation failed. "
                f"main.py exited with code "
                f"{result.returncode}."
            )

        # --------------------------------------------------------
        # Create invalid output
        # --------------------------------------------------------

        create_invalid_output(
            reason
        )

        return 1

    except Exception as exc:

        reason = (
            "Could not start validation system: "
            f"{exc}"
        )

        logger.exception(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1


# ============================================================
# MAIN CONVERSION WORKFLOW
# ============================================================

def run_conversion() -> int:
    """
    Complete conversion workflow.

    Steps:

        1. Read realinput.json
        2. Detect document type
        3. Convert data
        4. Validate converted structure
        5. Save input.json
        6. Start main.py
    """

    logger.info("=" * 70)

    logger.info(
        "DOCUMENT CONVERSION STARTED"
    )

    logger.info("=" * 70)

    # ========================================================
    # STEP 1
    # Read realinput.json
    # ========================================================

    try:

        raw_data = load_json(
            REAL_INPUT_FILE
        )

    except FileNotFoundError as exc:

        reason = (
            "Input file error: "
            + str(exc)
        )

        logger.error(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    except json.JSONDecodeError as exc:

        reason = (
            "realinput.json contains invalid JSON. "
            f"Line: {exc.lineno}, "
            f"Column: {exc.colno}. "
            f"{exc.msg}"
        )

        logger.error(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    except Exception as exc:

        reason = (
            "Could not read realinput.json: "
            f"{exc}"
        )

        logger.exception(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    # ========================================================
    # STEP 2
    # Detect document type
    # ========================================================

    document_type = detect_document_type(
        raw_data
    )

    if not document_type:

        reason = (
            "Document type could not be detected. "
            "realinput.json must contain a valid "
            "'document_type'."
        )

        logger.error(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    # ========================================================
    # STEP 3
    # Convert
    # ========================================================

    try:

        converted_data = convert_document(
            raw_data,
            document_type
        )

    except Exception as exc:

        reason = (
            "Document conversion failed: "
            f"{exc}"
        )

        logger.exception(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    # ========================================================
    # STEP 4
    # Validate converted structure
    # ========================================================

    try:

        validate_converted_data(
            converted_data
        )

    except Exception as exc:

        reason = (
            "Converted data is invalid: "
            f"{exc}"
        )

        logger.error(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    # ========================================================
    # STEP 5
    # Save input.json
    # ========================================================

    try:

        save_json(
            INPUT_FILE,
            converted_data
        )

    except Exception as exc:

        reason = (
            "Failed to create input.json: "
            f"{exc}"
        )

        logger.exception(
            reason
        )

        create_invalid_output(
            reason
        )

        return 1

    # ========================================================
    # STEP 6
    # Start main.py
    # ========================================================

    logger.info(
        "Conversion successful."
    )

    logger.info(
        "input.json is ready for main.py."
    )

    logger.info(
        "Starting validation system..."
    )

    return start_main()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        exit_code = run_conversion()

    except Exception as exc:

        # ----------------------------------------------------
        # FINAL SAFETY NET
        #
        # If ANY unexpected exception escapes everything above,
        # still create output.json as invalid.
        # ----------------------------------------------------

        logger.exception(
            "Unexpected system error: %s",
            exc
        )

        create_invalid_output(
            f"Unexpected system error: {exc}"
        )

        exit_code = 1

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    if exit_code == 0:

        logger.info("=" * 70)

        logger.info(
            "DOCUMENT VALIDATION WORKFLOW "
            "COMPLETED SUCCESSFULLY"
        )

        logger.info("=" * 70)

    # --------------------------------------------------------
    # FAILURE
    # --------------------------------------------------------

    else:

        logger.error("=" * 70)

        logger.error(
            "DOCUMENT VALIDATION FAILED"
        )

        logger.error(
            "Check output.json for the result."
        )

        logger.error("=" * 70)

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Do NOT use sys.exit(exit_code).
    #
    # A failed document is a validation result, not a
    # Python crash that should show SystemExit: 1.
    # --------------------------------------------------------

    sys.exit(0)