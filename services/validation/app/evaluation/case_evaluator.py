"""
Case-based evaluation across all OCR/expected pairs for a document type.

Produces:
- per-case scores
- average score across all cases
- detailed failure reasons ONLY for failed/review cases
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.extractors import get_extractor
from app.evaluation.evaluator import ExtractionEvaluator
from app.evaluation.metrics import compute_metrics

logger = logging.getLogger(__name__)

# Configurable score thresholds for overall_status
DEFAULT_THRESHOLDS = {
    "pass_min": 90.0,   # 90–100 → PASS
    "review_min": 75.0,  # 75–89.99 → REVIEW
    # below review_min → FAIL
}


class CaseBasedEvaluator:
    """
    Evaluate all cases under evaluation_data/<document_type>/.

    Each case = case_XXX_ocr.json + case_XXX_expected.json
    """

    def __init__(
        self,
        evaluation_data_dir: Path,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        self.root = Path(evaluation_data_dir)
        self.thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.field_evaluator = ExtractionEvaluator()

    def evaluate_document_type(self, document_type: str) -> Dict[str, Any]:
        """
        Load all cases for document_type, extract, compare, score.

        Returns the focused final JSON:
        {
          document_type, evaluation: {counts, score, overall_status},
          failed_cases: [...], review_cases: [...]
        }
        """
        type_dir = self.root / document_type
        if not type_dir.is_dir():
            return {
                "document_type": document_type,
                "error": f"No evaluation data directory for '{document_type}'",
                "evaluation": {
                    "total_cases": 0,
                    "passed_cases": 0,
                    "failed_cases": 0,
                    "review_cases": 0,
                    "score": 0.0,
                    "score_percent": 0.0,
                    "overall_status": "FAIL",
                },
                "failed_cases": [],
                "review_cases": [],
            }

        cases = self._discover_cases(type_dir)
        if not cases:
            return {
                "document_type": document_type,
                "error": f"No case pairs found under evaluation_data/{document_type}/",
                "evaluation": {
                    "total_cases": 0,
                    "passed_cases": 0,
                    "failed_cases": 0,
                    "review_cases": 0,
                    "score": 0.0,
                    "score_percent": 0.0,
                    "overall_status": "FAIL",
                },
                "failed_cases": [],
                "review_cases": [],
            }

        case_scores: List[float] = []
        passed = 0
        failed = 0
        review = 0
        failed_cases: List[Dict[str, Any]] = []
        review_cases: List[Dict[str, Any]] = []

        for case_id, ocr_path, exp_path in cases:
            case_result = self._evaluate_single_case(
                case_id, ocr_path, exp_path, document_type
            )
            case_scores.append(case_result["case_score"])
            status = case_result["case_status"]

            if status == "PASS":
                passed += 1
            elif status == "REVIEW":
                review += 1
                review_cases.append(self._to_failure_detail(case_result))
            else:
                failed += 1
                failed_cases.append(self._to_failure_detail(case_result))

        total = len(cases)
        avg_score = sum(case_scores) / total if total else 0.0
        avg_score = round(avg_score, 2)
        overall_status = self._score_to_status(avg_score)

        return {
            "document_type": document_type,
            "evaluation": {
                "total_cases": total,
                "passed_cases": passed,
                "failed_cases": failed,
                "review_cases": review,
                "score": avg_score,
                "score_percent": avg_score,
                "overall_status": overall_status,
            },
            "failed_cases": failed_cases,
            "review_cases": review_cases,
        }

    def evaluate_single_ocr(
        self,
        document_type: str,
        ocr: Dict[str, Any],
        expected: Optional[Dict[str, Any]] = None,
        case_id: str = "adhoc",
    ) -> Dict[str, Any]:
        """
        Evaluate one raw OCR payload.
        If expected is not provided, tries case_001_expected.json as fallback.
        """
        if expected is None:
            exp_path = self.root / document_type / "case_001_expected.json"
            if exp_path.exists():
                with open(exp_path, "r", encoding="utf-8") as f:
                    expected = json.load(f)
            else:
                raise FileNotFoundError(
                    f"No expected JSON provided and no case_001_expected.json "
                    f"for {document_type}"
                )

        extractor = get_extractor(document_type)
        extracted = extractor.extract(ocr)
        evaluation = self.field_evaluator.evaluate(
            extracted=extracted,
            expected=expected,
            ocr=ocr,
            document_type=document_type,
        )

        field_results = evaluation.get("fields", [])
        metrics = evaluation.get("metrics", {})
        case_score = round((metrics.get("field_accuracy") or 0.0) * 100, 2)
        case_status = self._case_status_from_fields(field_results)

        # MRZ consistency failures (passport)
        mrz_failed = []
        if document_type == "passport" and evaluation.get("mrz_consistency"):
            for check in evaluation["mrz_consistency"].get("checks", []):
                if check.get("status") in ("FAIL", "REVIEW"):
                    mrz_failed.append(
                        {
                            "field": f"mrz_{check.get('metric', 'consistency')}",
                            "expected": check.get("visible"),
                            "extracted": check.get("mrz"),
                            "status": check.get("status"),
                            "reason": check.get("reason", "MRZ consistency check failed"),
                        }
                    )

        result = {
            "case_id": case_id,
            "case_score": case_score,
            "case_status": case_status,
            "extracted": extracted,
            "expected": expected,
            "field_results": field_results,
            "metrics": metrics,
            "failed_fields": [
                {
                    "field": f["field"],
                    "expected": f.get("expected"),
                    "extracted": f.get("extracted"),
                    "status": f.get("status"),
                    "reason": f.get("reason"),
                }
                for f in field_results
                if f.get("status") in ("FAIL", "REVIEW")
            ]
            + mrz_failed,
        }

        if mrz_failed and case_status == "PASS":
            # MRZ failure can downgrade the case
            if any(x["status"] == "FAIL" for x in mrz_failed):
                result["case_status"] = "FAIL"
            else:
                result["case_status"] = "REVIEW"

        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _evaluate_single_case(
        self,
        case_id: str,
        ocr_path: Path,
        exp_path: Path,
        document_type: str,
    ) -> Dict[str, Any]:
        with open(ocr_path, "r", encoding="utf-8") as f:
            ocr = json.load(f)
        with open(exp_path, "r", encoding="utf-8") as f:
            expected = json.load(f)

        return self.evaluate_single_ocr(
            document_type=document_type,
            ocr=ocr,
            expected=expected,
            case_id=case_id,
        )

    def _to_failure_detail(self, case_result: Dict[str, Any]) -> Dict[str, Any]:
        """Slim payload for failed/review cases — only failed field details."""
        return {
            "case_id": case_result["case_id"],
            "case_score": case_result["case_score"],
            "failed_fields": case_result.get("failed_fields") or [],
        }

    def _case_status_from_fields(self, field_results: List[Dict[str, Any]]) -> str:
        """
        PASS only when all required evaluatable fields pass.
        Any FAIL → FAIL. Any REVIEW (and no FAIL) → REVIEW.
        """
        statuses = [f.get("status") for f in field_results]
        if not statuses:
            return "REVIEW"
        if any(s == "FAIL" for s in statuses):
            return "FAIL"
        if any(s == "REVIEW" for s in statuses):
            return "REVIEW"
        return "PASS"

    def _score_to_status(self, score: float) -> str:
        if score >= self.thresholds["pass_min"]:
            return "PASS"
        if score >= self.thresholds["review_min"]:
            return "REVIEW"
        return "FAIL"

    def _discover_cases(self, type_dir: Path) -> List[Tuple[str, Path, Path]]:
        cases = []
        for ocr_path in sorted(type_dir.glob("case_*_ocr.json")):
            stem = ocr_path.name.replace("_ocr.json", "")
            exp_path = type_dir / f"{stem}_expected.json"
            if exp_path.exists():
                cases.append((stem, ocr_path, exp_path))
        return cases
