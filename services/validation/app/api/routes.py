"""
API routes — backend only.
Primary evaluation endpoint loads all cases for a document type.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.extractors import get_extractor
from app.evaluation.case_evaluator import CaseBasedEvaluator
from app.evaluation.evaluator import ExtractionEvaluator
from app.validators.document_validator import DocumentValidator

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
EVALUATION_DATA_DIR = BASE_DIR / "evaluation_data"
RULES_DIR = BASE_DIR / "app" / "rules"
RESULTS_DIR = BASE_DIR / "results"

SUPPORTED_DOCUMENT_TYPES = [
    "passport",
    "driving_license",
    "visa",
    "national_id",
    "permit",
]


class ProcessRequest(BaseModel):
    document_type: str
    ocr: Dict[str, Any]


class ValidateRequest(BaseModel):
    document_type: str
    fields: Dict[str, Any]
    mrz: Optional[Dict[str, Any]] = None


class EvaluateRequest(BaseModel):
    """Primary batch evaluation — document_type only."""
    document_type: str


class EvaluateCaseRequest(BaseModel):
    """Single-case evaluation with explicit OCR."""
    document_type: str
    ocr: Dict[str, Any]
    expected: Optional[Dict[str, Any]] = None
    case_id: Optional[str] = "adhoc"


def _validate_document_type(document_type: str) -> None:
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported document_type '{document_type}'. "
                f"Supported: {SUPPORTED_DOCUMENT_TYPES}"
            ),
        )


def _save_result(document_type: str, result: Dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{document_type}_evaluation_result.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# Primary evaluation — all cases for a document type
# ---------------------------------------------------------------------------

@router.post("/evaluate")
async def evaluate_document_type(request: EvaluateRequest) -> Dict[str, Any]:
    """
    Evaluate ALL cases under evaluation_data/<document_type>/.

    Request: { "document_type": "driving_license" }

    Returns score + failed/review case details only (no passed-case details).
    """
    _validate_document_type(request.document_type)
    try:
        evaluator = CaseBasedEvaluator(EVALUATION_DATA_DIR)
        result = evaluator.evaluate_document_type(request.document_type)
        out_path = _save_result(request.document_type, result)
        result["result_file"] = str(out_path.relative_to(BASE_DIR))
        return result
    except Exception as e:
        logger.exception("Case-based evaluation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate/case")
async def evaluate_single_case(request: EvaluateCaseRequest) -> Dict[str, Any]:
    """
    Evaluate one raw OCR JSON against expected ground truth.

    If expected is omitted, uses case_001_expected.json for the document type.
    """
    _validate_document_type(request.document_type)
    try:
        evaluator = CaseBasedEvaluator(EVALUATION_DATA_DIR)
        result = evaluator.evaluate_single_ocr(
            document_type=request.document_type,
            ocr=request.ocr,
            expected=request.expected,
            case_id=request.case_id or "adhoc",
        )
        # Slim response focused on failures
        return {
            "document_type": request.document_type,
            "case_id": result["case_id"],
            "case_score": result["case_score"],
            "case_status": result["case_status"],
            "extracted": result.get("extracted"),
            "failed_fields": result.get("failed_fields") or [],
            "metrics": result.get("metrics"),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Single-case evaluation failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Extraction only
# ---------------------------------------------------------------------------

@router.post("/extract")
async def extract_fields(request: ProcessRequest) -> Dict[str, Any]:
    """Extract structured fields from raw OCR JSON."""
    _validate_document_type(request.document_type)
    try:
        extractor = get_extractor(request.document_type)
        return extractor.extract(request.ocr)
    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Validation only (structured JSON in)
# ---------------------------------------------------------------------------

@router.post("/validate")
async def validate_document(request: ValidateRequest) -> Dict[str, Any]:
    """Run deterministic document validation on structured JSON."""
    _validate_document_type(request.document_type)
    try:
        structured = {
            "document_type": request.document_type,
            "fields": request.fields,
        }
        if request.mrz:
            structured["mrz"] = request.mrz
        validator = DocumentValidator(rules_dir=RULES_DIR)
        return validator.validate(structured)
    except Exception as e:
        logger.exception("Validation failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Full process: extract → evaluate (single) → validate
# ---------------------------------------------------------------------------

@router.post("/process")
async def process_document(request: ProcessRequest) -> Dict[str, Any]:
    """
    Full pipeline for a single OCR payload:
    RAW OCR → extraction → single-case evaluation → document validation.
    """
    _validate_document_type(request.document_type)
    try:
        extractor = get_extractor(request.document_type)
        extracted = extractor.extract(request.ocr)

        case_eval = CaseBasedEvaluator(EVALUATION_DATA_DIR)
        evaluation = case_eval.evaluate_single_ocr(
            document_type=request.document_type,
            ocr=request.ocr,
            expected=None,
            case_id="process",
        )

        validator = DocumentValidator(rules_dir=RULES_DIR)
        validation = validator.validate(extracted)

        return {
            "document_type": request.document_type,
            "extracted": extracted,
            "evaluation": {
                "case_score": evaluation["case_score"],
                "case_status": evaluation["case_status"],
                "failed_fields": evaluation.get("failed_fields") or [],
                "metrics": evaluation.get("metrics"),
            },
            "validation": validation,
        }
    except Exception as e:
        logger.exception("Full process failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document-types")
async def list_document_types() -> Dict[str, Any]:
    return {"document_types": SUPPORTED_DOCUMENT_TYPES}


@router.get("/sample-ocr/{document_type}")
async def get_sample_ocr(document_type: str) -> Dict[str, Any]:
    """Return sample raw OCR JSON for testing."""
    _validate_document_type(document_type)
    path = EVALUATION_DATA_DIR / document_type / "case_001_ocr.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample OCR not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
