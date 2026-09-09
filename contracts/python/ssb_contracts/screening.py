"""
Case-level assembly.

The officer-facing application consumes the document this module produces, not
the individual module payloads. That is deliberate: if the frontend assembled
the case itself it would have to decide what a missing module means, how to rank
findings, and which signal dominates - all of which are backend policy. Putting
the assembly here keeps that policy in one testable place and keeps the app to
rendering what it is handed.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .core import SCHEMA_VERSION, Envelope, Module, not_available, utc_now
from .document_types import DocumentType
from .modules import EvidenceItem
from .services.risk_fusion import EvidenceFusionEngine, FusionInput, build_evidence_index

#: PatchCore has not been built. Every screening carries this envelope so the
#: absence is explicit in the record rather than being an omitted key that a
#: consumer could mistake for an oversight.
ANOMALY_NOT_IMPLEMENTED = (
    "ANOMALY_NOT_IMPLEMENTED",
    "Anomaly detection (PatchCore) is not implemented. This document has not "
    "been compared against a reference distribution.",
)


def anomaly_unavailable(case_id: str) -> Envelope:
    code, message = ANOMALY_NOT_IMPLEMENTED
    return not_available(
        case_id=case_id,
        module=Module.ANOMALY,
        reason_code=code,
        message=message,
    )


@dataclass
class ScreeningCaseResult:
    case_id: str
    document_type: DocumentType
    ocr: Envelope
    validation: Envelope
    face_verification: Envelope
    document_forensics: Envelope
    anomaly: Envelope
    risk: Envelope
    evidence: List[EvidenceItem] = field(default_factory=list)
    generated_at: str = field(default_factory=utc_now)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "document_type": self.document_type.value,
            "ocr": self.ocr.to_dict(),
            "validation": self.validation.to_dict(),
            "face_verification": self.face_verification.to_dict(),
            "document_forensics": self.document_forensics.to_dict(),
            "anomaly": self.anomaly.to_dict(),
            "risk": self.risk.to_dict(),
            "evidence": [dataclasses.asdict(item) for item in self.evidence],
            "generated_at": self.generated_at,
        }


def assemble(
    case_id: str,
    document_type: DocumentType,
    *,
    ocr: Envelope,
    validation: Envelope,
    face_verification: Envelope,
    document_forensics: Envelope,
    anomaly: Optional[Envelope] = None,
    engine: Optional[EvidenceFusionEngine] = None,
) -> ScreeningCaseResult:
    """
    Fuses the module evidence and returns the case document.

    Every module envelope is required. A module that did not run is passed as
    its NOT_AVAILABLE envelope rather than left out, so the gap appears in the
    record and in the officer's evidence list instead of vanishing.
    """
    anomaly_envelope = anomaly or anomaly_unavailable(case_id)
    fusion_input = FusionInput(
        ocr=ocr,
        validation=validation,
        face_verification=face_verification,
        document_forensics=document_forensics,
        anomaly=anomaly_envelope,
    )
    risk = (engine or EvidenceFusionEngine()).fuse(case_id, fusion_input)

    return ScreeningCaseResult(
        case_id=case_id,
        document_type=document_type,
        ocr=ocr,
        validation=validation,
        face_verification=face_verification,
        document_forensics=document_forensics,
        anomaly=anomaly_envelope,
        risk=risk,
        evidence=build_evidence_index(fusion_input),
    )
