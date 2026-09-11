"""
Deterministic document validation engine.
Separate from extraction evaluation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.validators.date_validator import (
    validate_date_format,
    validate_date_present,
    validate_not_expired,
    validate_dob_reasonable,
    validate_expiry_after_issue,
)
from app.validators.format_validator import (
    validate_license_number_format,
    validate_name_format,
    validate_passport_number_format,
    validate_required_string,
)
from app.validators.required_validator import validate_required_fields
from app.validators.consistency_validator import validate_date_consistency
from app.validators.mrz_validator import validate_mrz_consistency

logger = logging.getLogger(__name__)


class DocumentValidator:
    """Load rule configs and run deterministic validation."""

    def __init__(self, rules_dir: Optional[Path] = None):
        self.rules_dir = Path(rules_dir) if rules_dir else Path(__file__).parent.parent / "rules"
        self._rules_cache: Dict[str, Dict] = {}

    def _load_rules(self, document_type: str) -> Dict[str, Any]:
        if document_type in self._rules_cache:
            return self._rules_cache[document_type]
        path = self.rules_dir / f"{document_type}.json"
        if not path.exists():
            logger.warning("No rules file for %s, using defaults", document_type)
            rules = {"required_fields": [], "optional_fields": [], "expiry_required": True}
        else:
            with open(path, "r", encoding="utf-8") as f:
                rules = json.load(f)
        self._rules_cache[document_type] = rules
        return rules

    def validate(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        doc_type = structured.get("document_type", "unknown")
        fields = structured.get("fields") or {}
        mrz = structured.get("mrz")
        rules = self._load_rules(doc_type)

        results: List[Dict[str, Any]] = []

        # Required fields
        required = rules.get("required_fields") or []
        results.extend(validate_required_fields(fields, required))

        # Format checks
        if "name" in fields or "name" in required:
            results.append(validate_name_format(fields.get("name")))

        if doc_type == "driving_license":
            results.append(validate_license_number_format(fields.get("license_number")))
        if doc_type == "passport":
            results.append(validate_passport_number_format(fields.get("passport_number")))

        # Date validations
        for df in ("date_of_birth", "date_of_issue", "date_of_expiry"):
            if df in fields or df in required:
                results.append(validate_date_present(df, fields.get(df)))
                results.append(validate_date_format(df, fields.get(df)))

        if fields.get("date_of_birth"):
            results.append(validate_dob_reasonable(fields.get("date_of_birth")))

        # Checked for every type that carries an expiry date. An expired
        # document is a finding about the document, not about the capture.
        if "date_of_expiry" in fields or "date_of_expiry" in required:
            results.append(validate_not_expired(fields.get("date_of_expiry")))

        # Expiry applicability
        expiry_required = rules.get("expiry_required", True)
        if not expiry_required:
            if fields.get("date_of_expiry") is None:
                results.append(
                    {
                        "metric": "date_of_expiry",
                        "status": "NOT_APPLICABLE",
                        "reason": "This document type does not require an expiry date",
                    }
                )
        else:
            results.append(
                validate_expiry_after_issue(
                    fields.get("date_of_issue"), fields.get("date_of_expiry")
                )
            )

        # Consistency
        results.extend(validate_date_consistency(fields))

        # MRZ for passport
        if doc_type == "passport":
            results.extend(validate_mrz_consistency(fields, mrz or {}))

        # Aggregate status
        statuses = [r["status"] for r in results]
        if any(s == "FAIL" for s in statuses):
            overall = "FAIL"
        elif any(s == "REVIEW" for s in statuses):
            overall = "REVIEW"
        else:
            overall = "PASS"

        return {
            "document_type": doc_type,
            "overall_status": overall,
            "rules": results,
            "summary": {
                "total_rules": len(results),
                "pass": sum(1 for r in results if r["status"] == "PASS"),
                "fail": sum(1 for r in results if r["status"] == "FAIL"),
                "review": sum(1 for r in results if r["status"] == "REVIEW"),
                "not_applicable": sum(
                    1 for r in results if r["status"] == "NOT_APPLICABLE"
                ),
            },
        }
