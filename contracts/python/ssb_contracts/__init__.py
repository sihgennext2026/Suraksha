"""
SSB26188 canonical screening contracts.

The single definition of how the components of the screening system talk to each
other. The wire format lives in contracts/schemas/ssb-screening.schema.json;
this package is its Python mirror, and src/contracts/ is its TypeScript mirror.

Dependency-free by design: it is imported by services in separate repositories
with their own requirements, and it must stay importable on a machine with no
model runtime installed.
"""

from .core import (
    SCHEMA_VERSION,
    Envelope,
    Module,
    ModuleError,
    ModuleStatus,
    Severity,
    failed,
    not_available,
    partial,
    success,
    utc_now,
)
from .document_types import DocumentType, has_mrz, label, parse, supports
from .config import load as load_thresholds
from .screening import ScreeningCaseResult, anomaly_unavailable, assemble

__all__ = [
    "SCHEMA_VERSION",
    "DocumentType",
    "Envelope",
    "Module",
    "ModuleError",
    "ModuleStatus",
    "ScreeningCaseResult",
    "Severity",
    "anomaly_unavailable",
    "assemble",
    "failed",
    "has_mrz",
    "label",
    "load_thresholds",
    "not_available",
    "parse",
    "partial",
    "success",
    "supports",
    "utc_now",
]
