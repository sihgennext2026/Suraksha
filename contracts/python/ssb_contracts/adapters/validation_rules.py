"""
Adapter: services/validation DocumentValidator -> canonical contract.

The upstream engine already emits the right shape of information - per-rule
records with `metric`, `status` and `reason`, plus an aggregate. It is not
modified. This maps its vocabulary onto the canonical one:

    upstream                       canonical
    --------                       ---------
    metric                    ->   rule_id
    reason                    ->   message
    status PASS               ->   PASS
    status FAIL               ->   FAIL
    status REVIEW             ->   REVIEW
    status NOT_APPLICABLE     ->   NOT_APPLICABLE
    (input missing)           ->   NOT_AVAILABLE
    overall_status PASS       ->   decision VALID
    overall_status REVIEW     ->   decision REVIEW
    overall_status FAIL       ->   decision INVALID

The decision is recomputed from the checks rather than copied from
`overall_status`, so the roll-up rule lives in exactly one place.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core import Envelope, Module, ModuleError, failed, not_available, success
from ..document_types import (
    UNSUPPORTED_DOCUMENT_TYPE,
    DocumentType,
    supports,
)
from ..modules import CheckStatus, ValidationCheck, ValidationResult

RULE_ENGINE_VERSION = "backend-validation-1.0.0"

_STATUS_MAP = {
    "PASS": CheckStatus.PASS,
    "FAIL": CheckStatus.FAIL,
    "REVIEW": CheckStatus.REVIEW,
    "NOT_APPLICABLE": CheckStatus.NOT_APPLICABLE,
    "NOT_AVAILABLE": CheckStatus.NOT_AVAILABLE,
}


def _to_check(raw: Dict[str, Any]) -> ValidationCheck:
    status = _STATUS_MAP.get(str(raw.get("status", "")).upper())
    if status is None:
        # An unrecognised status is reported as un-evaluable rather than being
        # guessed into PASS or FAIL. Silently mapping it either way would be the
        # exact failure mode this contract exists to prevent.
        status = CheckStatus.NOT_AVAILABLE
    return ValidationCheck(
        rule_id=str(raw.get("metric") or raw.get("rule_id") or "unknown_rule"),
        status=status,
        message=str(raw.get("reason") or raw.get("message") or ""),
        observed=raw.get("observed"),
        expectation=raw.get("expectation"),
        fields=list(raw.get("fields") or []),
    )


def from_validator_output(
    case_id: str,
    document_type: DocumentType,
    output: Dict[str, Any],
    *,
    rule_version: str = RULE_ENGINE_VERSION,
) -> Envelope:
    """`output` is the dict returned by `DocumentValidator.validate()`."""
    supported, reason = supports(Module.VALIDATION, document_type)
    if not supported:
        return not_available(
            case_id=case_id,
            module=Module.VALIDATION,
            reason_code=UNSUPPORTED_DOCUMENT_TYPE,
            message=reason or "This document type has no validation rule set.",
            model_version=rule_version,
        )

    raw_rules: List[Dict[str, Any]] = list(output.get("rules") or [])
    if not raw_rules:
        return not_available(
            case_id=case_id,
            module=Module.VALIDATION,
            reason_code="NO_RULES_EVALUATED",
            message=(
                "No validation rule could be evaluated, because no extracted "
                "fields were available to check."
            ),
            model_version=rule_version,
        )

    checks = [_to_check(raw) for raw in raw_rules]
    result = ValidationResult.from_checks(checks, rule_version=rule_version)
    return success(
        case_id=case_id,
        module=Module.VALIDATION,
        model_version=rule_version,
        result=result.to_dict(),
    )


def from_failure(
    case_id: str,
    code: str,
    message: str,
    *,
    retryable: bool = True,
    rule_version: str = RULE_ENGINE_VERSION,
) -> Envelope:
    return failed(
        case_id=case_id,
        module=Module.VALIDATION,
        model_version=rule_version,
        errors=[ModuleError(code=code, message=message, retryable=retryable)],
    )


def unavailable(
    case_id: str,
    reason_code: str,
    message: str,
    *,
    rule_version: str = RULE_ENGINE_VERSION,
) -> Envelope:
    return not_available(
        case_id=case_id,
        module=Module.VALIDATION,
        reason_code=reason_code,
        message=message,
        model_version=rule_version,
    )


def build_result(
    checks: List[ValidationCheck],
    *,
    rule_version: str = RULE_ENGINE_VERSION,
) -> ValidationResult:
    """Exposed for callers that already hold canonical checks."""
    return ValidationResult.from_checks(checks, rule_version=rule_version)


__all__ = [
    "RULE_ENGINE_VERSION",
    "build_result",
    "from_failure",
    "from_validator_output",
    "unavailable",
]
