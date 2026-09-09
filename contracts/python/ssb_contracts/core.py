"""
Canonical envelope shared by every module response.

Deliberately dependency-free: this package is imported by services that live in
separate repositories with their own requirements files, and adding pydantic or
similar here would force a dependency on all of them. Standard-library
dataclasses give the same typing benefit at the boundary without that cost.

The wire format is defined by contracts/schemas/ssb-screening.schema.json. This
module is a mirror of it, not an independent definition.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"


class ModuleStatus(str, Enum):
    """
    How a module fared.

    The distinction that matters operationally is between a module that produced
    an adverse finding and a module that produced nothing at all. FAILED and
    NOT_AVAILABLE are absences of evidence, never findings, and the fusion engine
    must not score them as though they were.
    """

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_AVAILABLE = "NOT_AVAILABLE"

    @property
    def has_evidence(self) -> bool:
        """True when the module produced a result the fusion engine may score."""
        return self in (ModuleStatus.SUCCESS, ModuleStatus.PARTIAL)


class Module(str, Enum):
    OCR = "ocr"
    VALIDATION = "validation"
    FACE_VERIFICATION = "face_verification"
    DOCUMENT_FORENSICS = "document_forensics"
    ANOMALY = "anomaly"
    RISK = "risk"


class Severity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class ModuleError:
    """
    A failure that may reach an officer.

    `code` is for logs and retry logic and is never displayed. `message` is a
    plain sentence that is safe to show verbatim - it must not carry a stack
    trace, an internal identifier, or any personal data.
    """

    code: str
    message: str
    retryable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


@dataclass
class Envelope:
    """
    The wrapper every module response arrives in.

    A consumer can read status, module and model_version without knowing which
    module produced the envelope, which is what lets the case assembler and the
    frontend handle all six uniformly.
    """

    case_id: str
    module: Module
    status: ModuleStatus
    model_version: str
    result: Optional[Dict[str, Any]] = None
    errors: List[ModuleError] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now)
    duration_ms: Optional[float] = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        # The invariant the whole pipeline leans on: a consumer that sees a
        # non-success status can stop reading, because there is provably nothing
        # behind it. Without this, a half-populated result could be mistaken for
        # a complete one.
        if not self.status.has_evidence and self.result is not None:
            raise ValueError(
                f"{self.module.value}: result must be None when status is "
                f"{self.status.value}"
            )
        if self.status.has_evidence and self.result is None:
            raise ValueError(
                f"{self.module.value}: result is required when status is "
                f"{self.status.value}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "module": self.module.value,
            "status": self.status.value,
            "model_version": self.model_version,
            "timestamp": self.timestamp,
            "result": self.result,
            "errors": [error.to_dict() for error in self.errors],
            "duration_ms": self.duration_ms,
        }


def success(
    case_id: str,
    module: Module,
    model_version: str,
    result: Dict[str, Any],
    *,
    duration_ms: Optional[float] = None,
) -> Envelope:
    return Envelope(
        case_id=case_id,
        module=module,
        status=ModuleStatus.SUCCESS,
        model_version=model_version,
        result=result,
        duration_ms=duration_ms,
    )


def partial(
    case_id: str,
    module: Module,
    model_version: str,
    result: Dict[str, Any],
    errors: List[ModuleError],
    *,
    duration_ms: Optional[float] = None,
) -> Envelope:
    """A usable but incomplete result. The errors say what is missing from it."""
    return Envelope(
        case_id=case_id,
        module=module,
        status=ModuleStatus.PARTIAL,
        model_version=model_version,
        result=result,
        errors=errors,
        duration_ms=duration_ms,
    )


def failed(
    case_id: str,
    module: Module,
    model_version: str,
    errors: List[ModuleError],
) -> Envelope:
    """The module ran and could not produce a result."""
    return Envelope(
        case_id=case_id,
        module=module,
        status=ModuleStatus.FAILED,
        model_version=model_version,
        result=None,
        errors=errors,
    )


def not_available(
    case_id: str,
    module: Module,
    reason_code: str,
    message: str,
    *,
    model_version: str = "not-available",
) -> Envelope:
    """
    The module did not run at all - not implemented, not deployed, or it does not
    support this document type. Distinct from FAILED, which means it ran and
    could not finish.
    """
    return Envelope(
        case_id=case_id,
        module=module,
        status=ModuleStatus.NOT_AVAILABLE,
        model_version=model_version,
        result=None,
        errors=[ModuleError(code=reason_code, message=message, retryable=False)],
    )
