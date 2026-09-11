"""
Metrics calculation for single-document and batch evaluation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def compute_metrics(field_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate per-field results into overall metrics.
    Never hardcode — always derived from field_results.
    """
    total = len(field_results)
    correct = sum(1 for r in field_results if r.get("status") == "PASS")
    incorrect = sum(1 for r in field_results if r.get("status") == "FAIL")
    missing = sum(
        1
        for r in field_results
        if r.get("status") == "REVIEW" and r.get("extracted") is None
    )
    review = sum(1 for r in field_results if r.get("status") == "REVIEW")

    exact = sum(1 for r in field_results if r.get("match_type") == "exact")
    normalized = sum(
        1 for r in field_results if r.get("match_type") in ("exact", "normalized")
    )

    field_accuracy = correct / total if total else 0.0
    exact_match_accuracy = exact / total if total else 0.0
    normalized_match_accuracy = normalized / total if total else 0.0

    cers = [r.get("cer", 1.0) for r in field_results if r.get("cer") is not None]
    avg_cer = sum(cers) / len(cers) if cers else 0.0

    if review > 0 and correct + incorrect == 0:
        overall = "REVIEW"
    elif incorrect > 0 or missing > 0:
        overall = "FAIL"
    elif correct == total and total > 0:
        overall = "PASS"
    elif review > 0:
        overall = "REVIEW"
    else:
        overall = "FAIL"

    return {
        "total_fields": total,
        "correct_fields": correct,
        "incorrect_fields": incorrect,
        "missing_fields": missing,
        "review_fields": review,
        "field_accuracy": round(field_accuracy, 4),
        "field_accuracy_percent": round(field_accuracy * 100, 2),
        "exact_match_accuracy": round(exact_match_accuracy, 4),
        "normalized_match_accuracy": round(normalized_match_accuracy, 4),
        "average_character_error_rate": round(avg_cer, 4),
        "overall_status": overall,
    }


class BatchMetricsCalculator:
    """Evaluate all cases under evaluation_data/."""

    def __init__(self, evaluation_data_dir: Path):
        self.root = Path(evaluation_data_dir)

    def evaluate_all(
        self, document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        # Late imports to avoid circular dependency with evaluator
        from app.extractors import get_extractor
        from app.evaluation.evaluator import ExtractionEvaluator

        evaluator = ExtractionEvaluator()
        types = (
            [document_type]
            if document_type
            else ["passport", "driving_license", "visa", "national_id", "permit"]
        )
        per_type: Dict[str, Any] = {}
        all_field_results: List[Dict[str, Any]] = []
        total_docs = 0

        for dtype in types:
            type_dir = self.root / dtype
            if not type_dir.is_dir():
                continue
            cases = self._discover_cases(type_dir)
            type_field_results: List[Dict[str, Any]] = []
            case_summaries = []

            for case_id, ocr_path, exp_path in cases:
                try:
                    with open(ocr_path, "r", encoding="utf-8") as f:
                        ocr = json.load(f)
                    with open(exp_path, "r", encoding="utf-8") as f:
                        expected = json.load(f)

                    extractor = get_extractor(dtype)
                    extracted = extractor.extract(ocr)
                    evaluation = evaluator.evaluate(
                        extracted=extracted,
                        expected=expected,
                        ocr=ocr,
                        document_type=dtype,
                    )
                    type_field_results.extend(evaluation.get("fields", []))
                    all_field_results.extend(evaluation.get("fields", []))
                    total_docs += 1
                    case_summaries.append(
                        {
                            "case_id": case_id,
                            "metrics": evaluation.get("metrics"),
                            "status": evaluation.get("metrics", {}).get(
                                "overall_status"
                            ),
                        }
                    )
                except Exception as e:
                    logger.exception("Batch case %s/%s failed", dtype, case_id)
                    case_summaries.append(
                        {"case_id": case_id, "error": str(e), "status": "ERROR"}
                    )

            per_type[dtype] = {
                "document_count": len(cases),
                "metrics": compute_metrics(type_field_results),
                "cases": case_summaries,
            }

        overall = compute_metrics(all_field_results)
        overall["total_documents"] = total_docs

        return {
            "overall": overall,
            "by_document_type": per_type,
        }

    def _discover_cases(
        self, type_dir: Path
    ) -> List[tuple]:
        """Find case_XXX_ocr.json + case_XXX_expected.json pairs."""
        cases = []
        ocr_files = sorted(type_dir.glob("case_*_ocr.json"))
        for ocr_path in ocr_files:
            stem = ocr_path.name.replace("_ocr.json", "")
            exp_path = type_dir / f"{stem}_expected.json"
            if exp_path.exists():
                cases.append((stem, ocr_path, exp_path))
        return cases
