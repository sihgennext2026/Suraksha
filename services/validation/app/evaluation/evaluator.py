"""
Extraction evaluator: compares extracted structured JSON against expected ground truth.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.evaluation.field_evaluator import evaluate_field
from app.evaluation.metrics import compute_metrics


# Required evaluation fields per document type
REQUIRED_FIELDS: Dict[str, List[str]] = {
    "driving_license": [
        "name",
        "license_number",
        "date_of_birth",
        "date_of_issue",
        "date_of_expiry",
    ],
    "passport": [
        "name",
        "passport_number",
        "nationality",
        "date_of_birth",
        "date_of_issue",
        "date_of_expiry",
    ],
    "visa": [
        "name",
        "visa_number",
        "passport_number",
        "nationality",
        "visa_type",
        "date_of_issue",
        "date_of_expiry",
    ],
    "national_id": [
        "name",
        "national_id_number",
        "date_of_birth",
        "gender",
        "address",
    ],
    "permit": [
        "name",
        "permit_number",
        "permit_type",
        "date_of_issue",
        "date_of_expiry",
    ],
}


class ExtractionEvaluator:
    """Evaluate extracted fields against expected ground truth."""

    def evaluate(
        self,
        extracted: Dict[str, Any],
        expected: Dict[str, Any],
        ocr: Optional[Dict[str, Any]] = None,
        document_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        doc_type = (
            document_type
            or extracted.get("document_type")
            or expected.get("document_type")
            or "unknown"
        )
        exp_fields = expected.get("fields") or {}
        ext_fields = extracted.get("fields") or {}
        field_meta = extracted.get("field_meta") or {}

        required = REQUIRED_FIELDS.get(doc_type, list(exp_fields.keys()))
        # Evaluate intersection of required + expected keys
        fields_to_eval = list(dict.fromkeys(required + list(exp_fields.keys())))

        field_results: List[Dict[str, Any]] = []
        for fname in fields_to_eval:
            if fname not in exp_fields and fname not in required:
                continue
            expected_val = exp_fields.get(fname)
            extracted_val = ext_fields.get(fname)
            meta = field_meta.get(fname) or {}
            fr = evaluate_field(
                field_name=fname,
                expected=expected_val,
                extracted=extracted_val,
                source_text=meta.get("source_text"),
                ocr_confidence=meta.get("ocr_confidence"),
            )
            field_results.append(fr)

        metrics = compute_metrics(field_results)

        result: Dict[str, Any] = {
            "document_type": doc_type,
            "fields": field_results,
            "metrics": metrics,
        }

        # Passport MRZ consistency (separate from extraction accuracy)
        if doc_type == "passport" and extracted.get("mrz"):
            result["mrz_consistency"] = self._evaluate_mrz(
                extracted.get("fields") or {},
                extracted.get("mrz") or {},
            )

        return result

    def _evaluate_mrz(
        self, fields: Dict[str, Any], mrz: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare MRZ-derived values against visible fields."""
        checks = []

        def _check(label: str, visible: Any, mrz_val: Any) -> Dict[str, Any]:
            if mrz_val is None:
                return {
                    "metric": label,
                    "status": "REVIEW",
                    "reason": f"MRZ {label} not available",
                    "visible": visible,
                    "mrz": mrz_val,
                }
            if visible is None:
                return {
                    "metric": label,
                    "status": "REVIEW",
                    "reason": f"Visible {label} not extracted",
                    "visible": visible,
                    "mrz": mrz_val,
                }
            # Name: flexible order
            if label == "name":
                v = str(visible).upper().replace(" ", "")
                m = str(mrz_val).upper().replace(" ", "").replace("<", "")
                # Check if tokens overlap
                v_tokens = set(str(visible).upper().split())
                m_tokens = set(
                    t for t in str(mrz_val).upper().replace("<", " ").split() if t
                )
                if v_tokens & m_tokens or v in m or m in v:
                    return {
                        "metric": label,
                        "status": "PASS",
                        "reason": "MRZ name matches visible name",
                        "visible": visible,
                        "mrz": mrz_val,
                    }
                return {
                    "metric": label,
                    "status": "FAIL",
                    "reason": "MRZ name does not match visible name",
                    "visible": visible,
                    "mrz": mrz_val,
                }

            # Exact / normalized for numbers and dates
            v = str(visible).strip().upper().replace(" ", "").replace("-", "")
            m = str(mrz_val).strip().upper().replace(" ", "").replace("-", "")
            if v == m:
                return {
                    "metric": label,
                    "status": "PASS",
                    "reason": f"MRZ {label} matches visible field",
                    "visible": visible,
                    "mrz": mrz_val,
                }
            # Nationality: accept code vs full name (IND / INDIAN)
            if label == "nationality":
                if v.startswith(m) or m.startswith(v) or m in v or v in m:
                    return {
                        "metric": label,
                        "status": "PASS",
                        "reason": f"MRZ {label} consistent with visible field",
                        "visible": visible,
                        "mrz": mrz_val,
                    }
            return {
                "metric": label,
                "status": "FAIL",
                "reason": f"MRZ {label} does not match visible field",
                "visible": visible,
                "mrz": mrz_val,
            }

        checks.append(_check("name", fields.get("name"), mrz.get("name")))
        checks.append(
            _check(
                "passport_number",
                fields.get("passport_number"),
                mrz.get("passport_number"),
            )
        )
        checks.append(
            _check("nationality", fields.get("nationality"), mrz.get("nationality"))
        )
        checks.append(
            _check(
                "date_of_birth",
                fields.get("date_of_birth"),
                mrz.get("date_of_birth"),
            )
        )
        checks.append(
            _check(
                "date_of_expiry",
                fields.get("date_of_expiry"),
                mrz.get("date_of_expiry"),
            )
        )

        statuses = [c["status"] for c in checks]
        if all(s == "PASS" for s in statuses):
            overall = "PASS"
        elif any(s == "FAIL" for s in statuses):
            overall = "FAIL"
        else:
            overall = "REVIEW"

        return {
            "overall_status": overall,
            "checks": checks,
        }
