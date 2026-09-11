"""
main.py
============================================================

Main controller / router for the document validation system.

WORKFLOW
--------

    input.json
        |
        v
    main.py
        |
        |-- passport --> passport.py
        |                  |
        |                  v
        |               mrz.py
        |
        |-- visa --> visa.py
        |              |
        |              v
        |           vmrz.py
        |
        |-- license --> license.py
        |
        |-- nationalid --> aadhar.py
        |
        v
    output.json
"""

import json
import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


# ============================================================
# MODULE PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INDEX_DIR = Path(__file__).resolve().parent


# ============================================================
# PASSPORT MODULE LOADER
# ============================================================

PASSPORT_DIR = BASE_DIR / "pass"

PASSPORT_FILE = PASSPORT_DIR / "passport.py"

PASSPORT_MRZ_FILE = PASSPORT_DIR / "mrz.py"


# ============================================================
# VISA MODULE LOADER
# ============================================================

VISA_DIR = BASE_DIR / "visaprocess"

VISA_FILE = VISA_DIR / "visa.py"

VISA_MRZ_FILE = VISA_DIR / "vmrz.py"


# ============================================================
# LICENSE MODULE LOADER
# ============================================================

LICENSE_FILE = BASE_DIR / "license.py"
LEGACY_LICENSE_FILE = BASE_DIR / "licence.py"
REAL_LICENSE_FILE = BASE_DIR / "driving_license" / "license.py"

# ============================================================
# NATIONAL ID MODULE LOADER
# ============================================================

NATIONALID_DIR = BASE_DIR / "nationalid"
NATIONALID_FILE = NATIONALID_DIR / "aadhar.py"


# ============================================================
# LOAD MODULE FROM EXACT FILE
# ============================================================

def load_module_from_file(
    module_name: str,
    file_path: Path
):
    """
    Load a Python module directly from its exact file path.
    """

    if not file_path.exists():

        raise ModuleNotFoundError(
            f"Required module file not found: {file_path}"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        str(file_path)
    )

    if spec is None:

        raise ImportError(
            f"Could not create module specification for: "
            f"{file_path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    if spec.loader is None:

        raise ImportError(
            f"Could not load module: {file_path}"
        )

    sys.modules[module_name] = module

    spec.loader.exec_module(
        module
    )

    return module


# ============================================================
# LOAD PASSPORT MODULE
# ============================================================

passport = load_module_from_file(
    "passport_document_processor",
    PASSPORT_FILE
)


# ============================================================
# LOAD VISA MODULE
# ============================================================

visa = load_module_from_file(
    "visa_document_processor",
    VISA_FILE
)


# ============================================================
# FILE CONFIGURATION
# ============================================================

INPUT_FILE = INDEX_DIR / "input.json"

OUTPUT_FILE = INDEX_DIR / "output.json"


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


logger = logging.getLogger(
    "document_validation"
)


# ============================================================
# JSON FILE HELPERS
# ============================================================

def load_json(
    path: Path
) -> Dict[str, Any]:

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )

    except FileNotFoundError:

        raise RuntimeError(
            f"Input file not found: {path}"
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            f"Invalid JSON in {path}: {exc}"
        )

    except OSError as exc:

        raise RuntimeError(
            f"Could not read {path}: {exc}"
        )

    if not isinstance(
        data,
        dict
    ):

        raise RuntimeError(
            f"{path} must contain a JSON object."
        )

    return data


def save_json(
    path: Path,
    data: Dict[str, Any]
) -> None:

    try:

        with path.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False,
            )

    except OSError as exc:

        raise RuntimeError(
            f"Could not write {path}: {exc}"
        )


# ============================================================
# DOCUMENT TYPE DETECTION
# ============================================================

def detect_document_type(
    data: Dict[str, Any]
) -> str:

    document_type = data.get(
        "document_type"
    )

    if isinstance(
        document_type,
        str
    ):

        document_type = (
            document_type
            .strip()
            .lower()
        )

        if document_type:

            return document_type

    if isinstance(
        data.get("passport"),
        dict
    ):

        return "passport"

    if isinstance(
        data.get("visa"),
        dict
    ):

        return "visa"

    if isinstance(
        data.get("nationalid"),
        dict
    ):

        return "nationalid"

    if isinstance(
        data.get("license"),
        dict
    ):

        return "license"

    if isinstance(
        data.get("aadhaar"),
        dict
    ):

        return "aadhaar"

    return "unknown"


# ============================================================
# PASSPORT ERROR COLLECTION
# ============================================================

def collect_passport_errors(
    passport_result: Dict[str, Any]
) -> List[str]:

    errors: List[str] = []

    format_errors = passport_result.get(
        "format_errors",
        []
    )

    if isinstance(
        format_errors,
        list
    ):

        for error in format_errors:

            errors.append(
                f"Passport format validation: {error}"
            )

    mismatches = passport_result.get(
        "mrz_mismatches",
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

    mrz_result = passport_result.get(
        "mrz_validation"
    )

    if isinstance(
        mrz_result,
        dict
    ):

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

    return errors


# ============================================================
# VISA ERROR COLLECTION
# ============================================================

def collect_visa_errors(
    visa_result: Dict[str, Any]
) -> List[str]:

    errors: List[str] = []

    format_errors = visa_result.get(
        "format_errors",
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

    mismatches = visa_result.get(
        "mrz_mismatches",
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

            if visa_value is None:

                visa_value = mismatch.get(
                    "passport_value"
                )

            mrz_value = mismatch.get(
                "mrz_value"
            )

            errors.append(
                f"MRZ mismatch for {field}: "
                f"visa={visa_value}, "
                f"mrz={mrz_value}"
            )

    mrz_result = visa_result.get(
        "mrz_validation"
    )

    if isinstance(
        mrz_result,
        dict
    ):

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

    return errors


# ============================================================
# PASSPORT ROUTING
# ============================================================

def process_passport_route(
    data: Dict[str, Any]
) -> Dict[str, Any]:

    logger.info(
        "Routing document to passport.py"
    )

    passport_data = data.get(
        "passport"
    )

    if not isinstance(
        passport_data,
        dict
    ):

        raise ValueError(
            "input.json does not contain a valid "
            "'passport' object."
        )

    mrz_data = data.get(
        "mrz"
    )

    if not isinstance(
        mrz_data,
        dict
    ):

        raise ValueError(
            "input.json does not contain a valid "
            "'mrz' object."
        )

    line_1 = mrz_data.get(
        "line_1"
    )

    line_2 = mrz_data.get(
        "line_2"
    )

    if not isinstance(
        line_1,
        str
    ):

        raise ValueError(
            "MRZ line_1 is missing or invalid."
        )

    if not isinstance(
        line_2,
        str
    ):

        raise ValueError(
            "MRZ line_2 is missing or invalid."
        )

    mrz_lines = [
        line_1,
        line_2,
    ]

    logger.info(
        "Passport data successfully extracted."
    )

    logger.info(
        "Sending passport data and MRZ to passport.py."
    )

    result = passport.process_passport(
        passport_data=passport_data,
        mrz_lines=mrz_lines,
    )

    logger.info(
        "passport.py processing completed."
    )

    return result


# ============================================================
# VISA ROUTING
# ============================================================

def process_visa_route(
    data: Dict[str, Any]
) -> Dict[str, Any]:

    logger.info(
        "Routing document to visa.py"
    )

    visa_data = data.get(
        "visa"
    )

    if not isinstance(
        visa_data,
        dict
    ):

        raise ValueError(
            "input.json does not contain a valid "
            "'visa' object."
        )

    mrz_data = data.get(
        "mrz"
    )

    if not isinstance(
        mrz_data,
        dict
    ):

        raise ValueError(
            "input.json does not contain a valid "
            "'mrz' object."
        )

    line_1 = mrz_data.get(
        "line_1"
    )

    line_2 = mrz_data.get(
        "line_2"
    )

    if not isinstance(
        line_1,
        str
    ):

        raise ValueError(
            "MRZ line_1 is missing or invalid."
        )

    if not isinstance(
        line_2,
        str
    ):

        raise ValueError(
            "MRZ line_2 is missing or invalid."
        )

    mrz_lines = [
        line_1,
        line_2,
    ]

    logger.info(
        "Visa data successfully extracted."
    )

    logger.info(
        "Sending visa data and MRZ to visa.py."
    )

    result = visa.process_visa(
        visa_data=visa_data,
        mrz_lines=mrz_lines,
    )

    logger.info(
        "visa.py processing completed."
    )

    return result


# ============================================================
# LICENSE ROUTING
# ============================================================

def process_license_route(
    data: Dict[str, Any]
) -> Dict[str, Any]:

    logger.info(
        "Routing document to license.py"
    )

    candidate_files = [
        LICENSE_FILE,
        LEGACY_LICENSE_FILE,
        REAL_LICENSE_FILE,
    ]

    license_file = next(
        (path for path in candidate_files if path.exists()),
        LICENSE_FILE,
    )

    if not license_file.exists():
        raise FileNotFoundError(
            f"License module not found. Checked: {candidate_files}"
        )

    license_module = load_module_from_file(
        "license_document_processor",
        license_file
    )

    license_data = data.get(
        "license"
    )

    if not isinstance(
        license_data,
        dict
    ):

        raise ValueError(
            "input.json does not contain a valid "
            "'license' object."
        )

    logger.info(
        "Driving license data successfully extracted."
    )

    logger.info(
        "Sending driving license data to license.py."
    )

    result = license_module.process_license(
        license_data=license_data
    )

    logger.info(
        "license.py processing completed."
    )

    return result


# ============================================================
# NATIONAL ID ROUTING
# ============================================================

def process_nationalid_route(
    data: Dict[str, Any]
) -> Dict[str, Any]:

    logger.info(
        "Routing document to nationalid/aadhar.py."
    )

    nationalid_data = data.get(
        "nationalid"
    )

    if nationalid_data is None:
        nationalid_data = data.get(
            "aadhaar"
        )

    if not isinstance(
        nationalid_data,
        str
    ):

        raise ValueError(
            "input.json does not contain a valid raw Aadhaar number string."
        )

    logger.info(
        "Raw Aadhaar input successfully extracted."
    )

    nationalid_module = load_module_from_file(
        "nationalid_aadhaar_processor",
        NATIONALID_FILE
    )

    result = nationalid_module.process_aadhaar(
        nationalid_data
    )

    logger.info(
        "aadhar.py processing completed."
    )

    return result


# ============================================================
# PLACEHOLDER ROUTES
# ============================================================

def process_unimplemented_document(
    document_type: str
) -> Dict[str, Any]:

    return {
        "validation_passed": False,

        "document_type": document_type,

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),

        "passport_validation": None,

        "mrz_validation": None,

        "final_data": None,

        "errors": [
            f"{document_type} processing is not implemented yet."
        ],
    }


# ============================================================
# MAIN DOCUMENT PROCESSOR
# ============================================================

def process_document() -> Dict[str, Any]:

    logger.info(
        "Starting document validation system."
    )

    data = load_json(
        INPUT_FILE
    )

    document_type = detect_document_type(
        data
    )

    logger.info(
        "Detected document type: %s",
        document_type,
    )

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    # ========================================================
    # PASSPORT
    # ========================================================

    if document_type == "passport":

        try:

            passport_result = process_passport_route(
                data
            )

            format_valid = passport_result.get(
                "Validation_format",
                False
            )

            mrz_success = passport_result.get(
                "MRZ",
                False
            )

            mismatch_errors = passport_result.get(
                "Errors",
                []
            )

            validation_passed = (
                format_valid
                and mrz_success
                and len(mismatch_errors) == 0
            )

            result = {

                "validation_passed":
                    validation_passed,

                "document_type":
                    "passport",

                "passport_validation":
                    passport_result,
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            logger.info(
                "Passport validation completed."
            )

            logger.info(
                "Final validation result: %s",
                validation_passed
            )

            return result

        except Exception as exc:

            logger.exception(
                "Passport processing failed."
            )

            result = {

                "validation_passed":
                    False,

                "document_type":
                    "passport",

                "passport_validation": {

                    "document_type":
                        "passport",

                    "Validation_format":
                        False,

                    "MRZ":
                        False,

                    "Errors": [
                        f"Passport processing error: {str(exc)}"
                    ],
                },
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            return result

    # ========================================================
    # VISA
    # ========================================================

    if document_type == "visa":

        try:

            visa_result = process_visa_route(
                data
            )

            format_valid = visa_result.get(
                "Validation_format",
                False
            )

            mrz_success = visa_result.get(
                "MRZ",
                False
            )

            mismatch_errors = visa_result.get(
                "Errors",
                []
            )

            validation_passed = (
                format_valid
                and mrz_success
                and len(mismatch_errors) == 0
            )

            result = {

                "validation_passed":
                    validation_passed,

                "document_type":
                    "visa",

                "visa_validation":
                    visa_result,
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            logger.info(
                "Visa validation completed."
            )

            logger.info(
                "Final validation result: %s",
                validation_passed
            )

            return result

        except Exception as exc:

            logger.exception(
                "Visa processing failed."
            )

            result = {

                "validation_passed":
                    False,

                "document_type":
                    "visa",

                "timestamp":
                    timestamp,

                "passport_validation":
                    None,

                "visa_validation":
                    None,

                "mrz_validation":
                    None,

                "final_data":
                    None,

                "errors": [
                    f"Visa processing error: {str(exc)}"
                ],
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            return result

    # ========================================================
    # NATIONAL ID
    # ========================================================

    if document_type in (
        "nationalid",
        "national_id",
        "national id",
        "aadhaar",
        "aadhar",
    ):

        try:

            nationalid_result = process_nationalid_route(
                data
            )

            validation_passed = nationalid_result.get(
                "is_valid",
                False
            )

            result = {
                "validation_passed": validation_passed,
                "document_type": "nationalid",
                "nationalid_validation": nationalid_result,
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            logger.info(
                "National ID validation completed."
            )

            logger.info(
                "Final validation result: %s",
                validation_passed
            )

            return result

        except Exception as exc:

            logger.exception(
                "National ID processing failed."
            )

            result = {
                "validation_passed": False,
                "document_type": "nationalid",
                "nationalid_validation": {
                    "is_valid": False,
                    "number": None,
                    "format_detected": None,
                    "error": f"National ID processing error: {str(exc)}"
                },
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            return result

    # ========================================================
    # DRIVER LICENSE
    # ========================================================

    if document_type in (
        "license",
        "driver_license",
        "driving_license",
        "driver's license",
    ):

        try:

            license_result = process_license_route(
                data
            )

            validation_passed = license_result.get(
                "validation_passed",
                False
            )

            result = {

                "validation_passed":
                    validation_passed,

                "document_type":
                    "license",

                "license_validation":
                    license_result,
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            logger.info(
                "Driving license validation completed."
            )

            logger.info(
                "Final validation result: %s",
                validation_passed
            )

            return result

        except Exception as exc:

            logger.exception(
                "Driving license processing failed."
            )

            result = {

                "validation_passed":
                    False,

                "document_type":
                    "license",

                "license_validation": {

                    "validation_passed":
                        False,

                    "errors": [
                        f"Driving license processing error: {str(exc)}"
                    ],
                },
            }

            save_json(
                OUTPUT_FILE,
                result
            )

            return result

    # ========================================================
    # UNKNOWN
    # ========================================================

    result = {

        "validation_passed":
            False,

        "document_type":
            document_type,

        "timestamp":
            timestamp,

        "passport_validation":
            None,

        "mrz_validation":
            None,

        "final_data":
            None,

        "errors": [
            "Unable to determine document type."
        ],
    }

    save_json(
        OUTPUT_FILE,
        result
    )

    return result


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        process_document()

    except Exception as exc:

        logger.exception(
            "Fatal application error."
        )

        emergency_result = {

            "validation_passed":
                False,

            "document_type":
                "unknown",

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "passport_validation":
                None,

            "mrz_validation":
                None,

            "final_data":
                None,

            "errors": [
                f"Fatal error: {str(exc)}"
            ],
        }

        try:

            save_json(
                OUTPUT_FILE,
                emergency_result
            )

        except Exception:

            pass