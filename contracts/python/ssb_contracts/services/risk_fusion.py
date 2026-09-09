"""
Evidence Fusion Engine.

Deterministic weighted fusion over module evidence. This is NOT LightGBM and
NOT a learned model of any kind - the name matters, because calling it LightGBM
would imply the weights were fitted to labelled fraud data when they were
chosen by engineering judgement.

Two properties do the real work here:

  Missing evidence is never scored as an adverse finding. Modules that returned
  FAILED or NOT_AVAILABLE contribute no risk at all: they are dropped from the
  weighted mean and the remaining weights are renormalised over what was
  actually available. A screening can never be marked riskier *because* a module
  was down.

  Note what renormalising does and does not promise. It does not promise the
  score is monotonic in the number of modules: dropping a module that was
  reporting "clean" removes positive evidence, so the mean of what remains can
  sit higher than it did before. That is the honest outcome - the reassurance
  genuinely is no longer there - and it is why the guarantee is stated as "an
  absent module never scores worse than that module reporting its worst finding"
  rather than "an absent module never moves the score".

  Thin evidence cannot produce a confident clearance. `evidence_coverage`
  records how much of the configured weight was available; below the configured
  minimum the band is floored at REVIEW, because a LOW derived from one module
  out of five is not a finding an officer should rely on.

The output is decision support. It never issues an operational verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..config import Thresholds, load as load_thresholds
from ..core import Envelope, Module, ModuleStatus, Severity, success
from ..modules import (
    EvidenceItem,
    RiskBandsPayload,
    RiskContributor,
    RiskLevel,
    RiskResult,
)

ENGINE_VERSION = "evidence-fusion-1.0.0"

_LEVEL_ORDER = {RiskLevel.LOW: 0, RiskLevel.REVIEW: 1, RiskLevel.HIGH: 2}


@dataclass
class _Signal:
    """One module's contribution, before weighting."""

    module: Module
    #: Normalised 0..1 risk this module's finding represents. None when the
    #: module produced no evidence and must be excluded from scoring.
    risk: Optional[float]
    signal: str
    impact: str
    severity: Severity
    headline: str
    detail: str


def _evidence_or_none(envelope: Envelope) -> Optional[Dict]:
    return envelope.result if envelope.status.has_evidence else None


def _absent_signal(envelope: Envelope, module: Module, what: str) -> _Signal:
    """
    Builds the contributor entry for a module that produced nothing.

    It is listed rather than omitted so the officer can see what was missing,
    but it carries no risk and no severity - an absence is not a finding.
    """
    reason = envelope.errors[0].message if envelope.errors else ""
    if envelope.status is ModuleStatus.NOT_AVAILABLE:
        signal, impact = "NOT_AVAILABLE", (
            reason or f"{what} was not available for this screening."
        )
    else:
        signal, impact = "FAILED", (
            reason or f"{what} could not complete for this screening."
        )
    return _Signal(
        module=module,
        risk=None,
        signal=signal,
        impact=impact,
        severity=Severity.NONE,
        headline=what,
        detail=impact,
    )


def _face_signal(envelope: Envelope) -> _Signal:
    result = _evidence_or_none(envelope)
    if result is None:
        return _absent_signal(envelope, Module.FACE_VERIFICATION, "Face verification")

    similarity = float(result["similarity"])
    decision = result["decision"]
    # The raw cosine similarity is quoted as-is. It is never rescaled into a
    # percentage, here or anywhere downstream.
    if decision == "NO_MATCH":
        return _Signal(
            Module.FACE_VERIFICATION,
            1.0,
            "NO_MATCH",
            f"Cosine similarity {similarity:.3f} is below the no-match boundary "
            f"{result['thresholds']['review']:.2f}. The subject does not match "
            "the document portrait.",
            Severity.HIGH,
            "Face verification",
            f"No match · similarity {similarity:.3f}",
        )
    if decision == "REVIEW":
        return _Signal(
            Module.FACE_VERIFICATION,
            0.5,
            "REVIEW",
            f"Cosine similarity {similarity:.3f} falls between the review and "
            "match boundaries, so the comparison is inconclusive on its own.",
            Severity.MEDIUM,
            "Face verification",
            f"Review required · similarity {similarity:.3f}",
        )
    return _Signal(
        Module.FACE_VERIFICATION,
        0.0,
        "MATCH",
        f"Cosine similarity {similarity:.3f} is at or above the match boundary "
        f"{result['thresholds']['match']:.2f}.",
        Severity.NONE,
        "Face verification",
        f"Match · similarity {similarity:.3f}",
    )


def _forensics_signal(envelope: Envelope) -> _Signal:
    result = _evidence_or_none(envelope)
    if result is None:
        return _absent_signal(envelope, Module.DOCUMENT_FORENSICS, "Document forensics")

    score = float(result["tamper_score"])
    tampered = bool(result["tampered"])
    manipulation = result["manipulation_type"]
    regions = result.get("suspicious_regions") or []

    if tampered:
        located = (
            f"{len(regions)} suspicious region{'s' if len(regions) != 1 else ''} identified"
            if regions
            else "no region could be localised"
        )
        return _Signal(
            Module.DOCUMENT_FORENSICS,
            min(1.0, score),
            "TAMPERED",
            f"Potential tampering detected (tamper score {score:.2f}, "
            f"type {manipulation.replace('_', ' ').lower()}); {located}.",
            Severity.HIGH,
            "Document forensics",
            f"Potential tampering · score {score:.2f}",
        )
    return _Signal(
        Module.DOCUMENT_FORENSICS,
        min(1.0, score),
        "NO_TAMPERING_DETECTED",
        f"No tampering indicators were found (tamper score {score:.2f}).",
        Severity.NONE,
        "Document forensics",
        f"No tampering detected · score {score:.2f}",
    )


def _validation_signal(envelope: Envelope) -> _Signal:
    result = _evidence_or_none(envelope)
    if result is None:
        return _absent_signal(envelope, Module.VALIDATION, "Rule validation")

    decision = result["decision"]
    summary = result["summary"]
    counts = (
        f"{summary['passed']} passed, {summary['failed']} failed, "
        f"{summary['review']} inconclusive"
    )
    if decision == "INVALID":
        return _Signal(
            Module.VALIDATION,
            1.0,
            "INVALID",
            f"Deterministic rule checking found {summary['failed']} failed "
            "rule(s). A rule failure is evidence for an officer to weigh, not a "
            "finding that the document is false.",
            Severity.HIGH,
            "Rule validation",
            counts,
        )
    if decision == "REVIEW":
        return _Signal(
            Module.VALIDATION,
            0.45,
            "REVIEW",
            f"Rule checking was inconclusive on {summary['review']} rule(s).",
            Severity.MEDIUM,
            "Rule validation",
            counts,
        )
    return _Signal(
        Module.VALIDATION,
        0.0,
        "VALID",
        f"Every applicable rule passed ({counts}).",
        Severity.NONE,
        "Rule validation",
        counts,
    )


def _ocr_signal(envelope: Envelope, thresholds: Thresholds) -> _Signal:
    result = _evidence_or_none(envelope)
    if result is None:
        return _absent_signal(envelope, Module.OCR, "Field extraction")

    confidence = result.get("overall_confidence")
    mrz = result.get("mrz") or {}
    detected = bool((result.get("detection") or {}).get("detected"))

    if not detected:
        return _Signal(
            Module.OCR,
            0.8,
            "DOCUMENT_NOT_LOCATED",
            "The document could not be located in the captured frame, so every "
            "downstream finding carries more uncertainty than usual.",
            Severity.MEDIUM,
            "Field extraction",
            "Document not located",
        )
    # `checksum_valid is None` means the checksum was not evaluated at this
    # stage, which is not a finding. Only an explicit False is a failure - the
    # difference between "not tested" and "tested and wrong".
    if mrz.get("present") and mrz.get("checksum_valid") is False:
        return _Signal(
            Module.OCR,
            0.9,
            "MRZ_CHECKSUM_FAILED",
            "A machine-readable zone check digit does not match the data it "
            "protects. On a genuine document these always agree.",
            Severity.HIGH,
            "Field extraction",
            "MRZ checksum failed",
        )
    if confidence is not None and confidence < thresholds.ocr.low_confidence_below:
        return _Signal(
            Module.OCR,
            0.5,
            "LOW_CONFIDENCE",
            f"Field extraction averaged {confidence:.2f} confidence, which "
            "weakens every check that reads those values.",
            Severity.MEDIUM,
            "Field extraction",
            f"Low confidence · {confidence:.2f}",
        )
    detail = (
        f"{len(result.get('fields') or [])} fields read"
        + (f" · confidence {confidence:.2f}" if confidence is not None else "")
    )
    return _Signal(
        Module.OCR,
        0.0,
        "OK",
        "Fields were extracted cleanly and the machine-readable zone, where "
        "present, is self-consistent.",
        Severity.NONE,
        "Field extraction",
        detail,
    )


def _anomaly_signal(envelope: Envelope) -> _Signal:
    result = _evidence_or_none(envelope)
    if result is None:
        return _absent_signal(envelope, Module.ANOMALY, "Anomaly analysis")

    score = float(result["anomaly_score"])
    if result.get("anomalous"):
        return _Signal(
            Module.ANOMALY,
            min(1.0, score),
            "ANOMALOUS",
            f"The document deviates from the genuine reference distribution "
            f"(anomaly score {score:.2f}).",
            Severity.MEDIUM,
            "Anomaly analysis",
            f"Anomalous · score {score:.2f}",
        )
    return _Signal(
        Module.ANOMALY,
        min(1.0, score),
        "NOMINAL",
        f"The document sits within the genuine reference distribution "
        f"(anomaly score {score:.2f}).",
        Severity.NONE,
        "Anomaly analysis",
        f"Nominal · score {score:.2f}",
    )


@dataclass
class FusionInput:
    """
    Every module envelope the engine consumes. All are required - a module that
    did not run is passed as its NOT_AVAILABLE envelope rather than omitted, so
    the engine can report the gap rather than silently ignore it.
    """

    ocr: Envelope
    validation: Envelope
    face_verification: Envelope
    document_forensics: Envelope
    anomaly: Envelope


class EvidenceFusionEngine:
    def __init__(self, thresholds: Optional[Thresholds] = None) -> None:
        self._thresholds = thresholds or load_thresholds()

    def fuse(self, case_id: str, evidence: FusionInput) -> Envelope:
        config = self._thresholds.risk
        signals = [
            _forensics_signal(evidence.document_forensics),
            _face_signal(evidence.face_verification),
            _validation_signal(evidence.validation),
            _ocr_signal(evidence.ocr, self._thresholds),
            _anomaly_signal(evidence.anomaly),
        ]

        weighted_total = 0.0
        available_weight = 0.0
        contributors: List[RiskContributor] = []

        for signal in signals:
            weight = config.weights.get(signal.module.value, 0.0)
            counted = signal.risk is not None
            if counted:
                weighted_total += weight * float(signal.risk)
                available_weight += weight
            contributors.append(
                RiskContributor(
                    source=signal.module.value,
                    signal=signal.signal,
                    impact=signal.impact,
                    severity=signal.severity.value,
                    weight=round(weight, 4) if counted else None,
                    counted=counted,
                )
            )

        total_weight = sum(config.weights.values())
        coverage = available_weight / total_weight if total_weight else 0.0
        # Renormalising over what was available is what stops a missing module
        # from behaving like a clean one (which would dilute real findings) or
        # like a failing one (which would invent fraud).
        score = weighted_total / available_weight if available_weight else 0.0

        level = self._band(score, config.bands.review_at_or_above, config.bands.high_at_or_above)
        level, escalations = self._escalate(level, signals, coverage)

        # Contributors are ordered by how much they moved the outcome, so the
        # first row an officer reads is the one that mattered most.
        contributors.sort(
            key=lambda entry: (
                entry.counted,
                {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}[entry.severity],
                entry.weight or 0.0,
            ),
            reverse=True,
        )

        result = RiskResult(
            risk_score=round(score, 4),
            risk_level=level,
            contributors=contributors,
            evidence_coverage=round(coverage, 4),
            engine_version=ENGINE_VERSION,
            config_version=self._thresholds.config_version,
            bands=RiskBandsPayload(
                review_at_or_above=config.bands.review_at_or_above,
                high_at_or_above=config.bands.high_at_or_above,
            ),
            escalations=escalations,
            narrative=self._narrative(level, score, coverage, signals, escalations),
        )
        return success(
            case_id=case_id,
            module=Module.RISK,
            model_version=ENGINE_VERSION,
            result=result.to_dict(),
        )

    @staticmethod
    def _band(score: float, review_at: float, high_at: float) -> RiskLevel:
        if score >= high_at:
            return RiskLevel.HIGH
        if score >= review_at:
            return RiskLevel.REVIEW
        return RiskLevel.LOW

    def _escalate(
        self, level: RiskLevel, signals: List[_Signal], coverage: float
    ) -> tuple[RiskLevel, List[str]]:
        """
        Raises the band floor for signals strong enough that a low fused average
        must not bury them. Escalations can only raise, never lower.
        """
        config = self._thresholds.risk
        escalations: List[str] = []

        def raise_to(target: str, reason: str) -> None:
            nonlocal level
            candidate = RiskLevel(target)
            if _LEVEL_ORDER[candidate] > _LEVEL_ORDER[level]:
                level = candidate
                escalations.append(reason)
            elif _LEVEL_ORDER[candidate] == _LEVEL_ORDER[level]:
                escalations.append(reason)

        by_module = {signal.module: signal for signal in signals}

        forensics = by_module.get(Module.DOCUMENT_FORENSICS)
        if forensics and forensics.signal == "TAMPERED":
            raise_to(
                config.escalations["forensics_tampered_floor"],
                "Tampering was detected, which is escalated regardless of the other findings.",
            )

        face = by_module.get(Module.FACE_VERIFICATION)
        if face and face.signal == "NO_MATCH":
            raise_to(
                config.escalations["face_no_match_floor"],
                "The subject does not match the document portrait.",
            )

        if face and face.signal == "REVIEW":
            raise_to(
                config.escalations["face_review_floor"],
                "The face comparison was inconclusive and needs a human look.",
            )

        validation = by_module.get(Module.VALIDATION)
        if validation and validation.signal == "INVALID":
            raise_to(
                config.escalations["validation_invalid_floor"],
                "One or more deterministic rules failed.",
            )

        if validation and validation.signal == "REVIEW":
            raise_to(
                config.escalations["validation_review_floor"],
                "One or more rules were inconclusive.",
            )

        if coverage < config.minimum_evidence_weight:
            raise_to(
                config.escalations["insufficient_evidence_floor"],
                f"Only {coverage:.0%} of the evidence was available, which is not "
                "enough to support a low-risk assessment.",
            )

        return level, escalations

    @staticmethod
    def _narrative(
        level: RiskLevel,
        score: float,
        coverage: float,
        signals: List[_Signal],
        escalations: List[str],
    ) -> str:
        adverse = [s for s in signals if s.risk is not None and s.risk > 0.0]
        adverse.sort(key=lambda s: s.risk or 0.0, reverse=True)
        missing = [s for s in signals if s.risk is None]

        parts = [
            f"Fused risk score {score:.2f} across {coverage:.0%} of the available "
            f"evidence places this screening in the {level.value} band."
        ]
        if adverse:
            leading = "; ".join(s.impact for s in adverse[:2])
            parts.append(f"Leading findings: {leading}")
        else:
            parts.append("No adverse findings were recorded by any module that ran.")
        if missing:
            names = ", ".join(s.headline.lower() for s in missing)
            parts.append(
                f"Not scored because no result was produced: {names}. "
                "Absent evidence has not been counted for or against this document."
            )
        if escalations:
            parts.append("Escalated: " + " ".join(escalations))
        parts.append(
            "This is decision support. The operational decision rests with the officer."
        )
        return " ".join(parts)


def build_evidence_index(evidence: FusionInput) -> List[EvidenceItem]:
    """
    The officer-facing evidence index, derived here rather than in the frontend
    so no consumer has to re-interpret raw module payloads to build it.
    """
    thresholds = load_thresholds()
    signals = [
        _ocr_signal(evidence.ocr, thresholds),
        _validation_signal(evidence.validation),
        _face_signal(evidence.face_verification),
        _forensics_signal(evidence.document_forensics),
        _anomaly_signal(evidence.anomaly),
    ]
    envelopes = {
        Module.OCR: evidence.ocr,
        Module.VALIDATION: evidence.validation,
        Module.FACE_VERIFICATION: evidence.face_verification,
        Module.DOCUMENT_FORENSICS: evidence.document_forensics,
        Module.ANOMALY: evidence.anomaly,
    }
    return [
        EvidenceItem(
            module=signal.module.value,
            status=envelopes[signal.module].status.value,
            headline=signal.headline,
            detail=signal.detail,
            severity=signal.severity.value,
        )
        for signal in signals
    ]
