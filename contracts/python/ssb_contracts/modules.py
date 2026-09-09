"""
Typed payloads that sit inside an `Envelope.result`.

One dataclass per module, each mirroring its `$defs` entry in
contracts/schemas/ssb-screening.schema.json.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from .document_types import DocumentType

#: [x, y, width, height], normalised 0..1 against the corrected document image.
BBox = Sequence[float]


def _clean(value: Any) -> Any:
    """Recursively converts dataclasses and enums to their wire representation."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {key: _clean(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------


class FieldSource(str, Enum):
    MRZ = "mrz"
    LABEL_SAME_LINE = "label_same_line"
    LABEL_NEXT_LINE = "label_next_line"
    STANDALONE_ID = "standalone_id"
    NOT_FOUND = "not_found"


@dataclass
class OcrField:
    key: str
    #: None when the field was not located. Never guessed, never defaulted.
    value: Optional[str]
    source: FieldSource = FieldSource.NOT_FOUND
    confidence: Optional[float] = None
    region: Optional[BBox] = None


@dataclass
class MrzCheckDigit:
    field: str
    observed: str
    computed: str
    valid: bool


@dataclass
class MrzPayload:
    present: bool
    format: str = "NONE"
    lines: List[str] = field(default_factory=list)
    check_digits: List[MrzCheckDigit] = field(default_factory=list)
    #: None means "not evaluated at this stage" - distinct from False, which
    #: asserts the checksum was tested and did not match.
    checksum_valid: Optional[bool] = None
    confidence: Optional[float] = None


@dataclass
class DetectionPayload:
    detected: bool
    confidence: Optional[float] = None
    box: Optional[BBox] = None
    correction_mode: Optional[str] = None
    orientation_corrected: bool = False


@dataclass
class OcrResult:
    document_type: DocumentType
    fields: List[OcrField]
    mrz: MrzPayload
    detection: DetectionPayload
    overall_confidence: Optional[float] = None
    language: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _clean(self)

    def field_value(self, key: str) -> Optional[str]:
        for entry in self.fields:
            if entry.key == key:
                return entry.value
        return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class CheckStatus(str, Enum):
    """
    NOT_APPLICABLE and NOT_AVAILABLE are kept apart deliberately: the first means
    the rule is irrelevant to this document type, the second that its input was
    missing. Neither is a failure, and collapsing them would hide which.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ValidationDecision(str, Enum):
    VALID = "VALID"
    REVIEW = "REVIEW"
    INVALID = "INVALID"


@dataclass
class ValidationCheck:
    rule_id: str
    status: CheckStatus
    message: str
    observed: Optional[str] = None
    expectation: Optional[str] = None
    fields: List[str] = field(default_factory=list)


@dataclass
class ValidationSummary:
    passed: int = 0
    failed: int = 0
    review: int = 0
    not_applicable: int = 0
    not_available: int = 0


@dataclass
class ValidationResult:
    decision: ValidationDecision
    checks: List[ValidationCheck]
    summary: ValidationSummary
    rule_version: str

    def to_dict(self) -> Dict[str, Any]:
        return _clean(self)

    @staticmethod
    def from_checks(checks: List[ValidationCheck], rule_version: str) -> "ValidationResult":
        """
        Rolls checks up into a decision.

        A failed check makes the document INVALID for the rule set; a check that
        is inconclusive makes it REVIEW. Checks that did not apply or could not
        run never influence the decision - that is the whole point of keeping
        them as separate statuses.
        """
        summary = ValidationSummary(
            passed=sum(1 for check in checks if check.status is CheckStatus.PASS),
            failed=sum(1 for check in checks if check.status is CheckStatus.FAIL),
            review=sum(1 for check in checks if check.status is CheckStatus.REVIEW),
            not_applicable=sum(
                1 for check in checks if check.status is CheckStatus.NOT_APPLICABLE
            ),
            not_available=sum(
                1 for check in checks if check.status is CheckStatus.NOT_AVAILABLE
            ),
        )
        if summary.failed:
            decision = ValidationDecision.INVALID
        elif summary.review:
            decision = ValidationDecision.REVIEW
        else:
            decision = ValidationDecision.VALID
        return ValidationResult(
            decision=decision, checks=checks, summary=summary, rule_version=rule_version
        )


# ---------------------------------------------------------------------------
# Face verification
# ---------------------------------------------------------------------------


class FaceDecision(str, Enum):
    MATCH = "MATCH"
    REVIEW = "REVIEW"
    NO_MATCH = "NO_MATCH"


@dataclass
class FaceQualityMetrics:
    face_width_px: Optional[float] = None
    face_height_px: Optional[float] = None
    brightness: Optional[float] = None
    blur_score: Optional[float] = None
    yaw_proxy: Optional[float] = None
    roll_deg: Optional[float] = None


@dataclass
class FaceQualityChecks:
    face_size_ok: Optional[bool] = None
    brightness_ok: Optional[bool] = None
    blur_ok: Optional[bool] = None
    pose_ok: Optional[bool] = None


@dataclass
class FaceQuality:
    """
    `score` stays None unless a model actually produces one. The current ArcFace
    pipeline reports pass/fail gates and raw measurements, so deriving a 0..1
    figure from them would be an invented confidence - which the contract
    forbids. Consumers render `acceptable` plus the metrics instead.
    """

    acceptable: Optional[bool]
    score: Optional[float] = None
    metrics: Optional[FaceQualityMetrics] = None
    checks: Optional[FaceQualityChecks] = None


@dataclass
class FaceThresholdsPayload:
    match: float
    review: float


@dataclass
class FaceVerificationResult:
    #: RAW cosine similarity in [-1, 1]. Not a probability, not a percentage.
    similarity: float
    decision: FaceDecision
    thresholds: FaceThresholdsPayload
    quality: Dict[str, FaceQuality]
    embedding_dim: Optional[int] = 512

    def to_dict(self) -> Dict[str, Any]:
        return _clean(self)


# ---------------------------------------------------------------------------
# Document forensics
# ---------------------------------------------------------------------------


class ManipulationType(str, Enum):
    PHOTO_REPLACEMENT = "PHOTO_REPLACEMENT"
    TEXT_MANIPULATION = "TEXT_MANIPULATION"
    STAMP_SIGNATURE_MANIPULATION = "STAMP_SIGNATURE_MANIPULATION"
    COPY_PASTE_SPLICING = "COPY_PASTE_SPLICING"
    OTHER = "OTHER"
    NONE = "NONE"


@dataclass
class SuspiciousRegion:
    bbox: BBox
    score: float
    note: Optional[str] = None


@dataclass
class DocumentForensicsResult:
    tampered: bool
    tamper_score: float
    manipulation_type: ManipulationType
    type_score: Optional[float] = None
    #: May be empty even when `tampered` is true: the classification head can
    #: fire without the localisation head resolving a region. An empty list is
    #: never evidence of authenticity.
    suspicious_regions: List[SuspiciousRegion] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return _clean(self)


# ---------------------------------------------------------------------------
# Anomaly (PatchCore - not implemented)
# ---------------------------------------------------------------------------


@dataclass
class AnomalyResult:
    anomaly_score: float
    anomalous: bool
    suspicious_regions: List[SuspiciousRegion] = field(default_factory=list)
    threshold: Optional[float] = None
    reference_set_size: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return _clean(self)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    LOW = "LOW"
    REVIEW = "REVIEW"
    HIGH = "HIGH"


@dataclass
class RiskContributor:
    source: str
    signal: str
    impact: str
    severity: str
    weight: Optional[float] = None
    counted: bool = True


@dataclass
class RiskBandsPayload:
    review_at_or_above: float
    high_at_or_above: float


@dataclass
class RiskResult:
    #: Normalised 0..1. Defined by configuration, not measured from data.
    risk_score: float
    risk_level: RiskLevel
    contributors: List[RiskContributor]
    evidence_coverage: float
    engine_version: str
    config_version: str
    bands: Optional[RiskBandsPayload] = None
    escalations: List[str] = field(default_factory=list)
    narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return _clean(self)


@dataclass
class EvidenceItem:
    module: str
    status: str
    headline: str
    detail: str
    severity: str = "NONE"
