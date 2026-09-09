"""
Loads contracts/config/thresholds.json.

Every threshold, band and weight in the system comes from here. No module
defines a number of its own, and nothing is duplicated in code - if a value in
the JSON changes, every consumer changes with it, and `config_version` records
which set of numbers produced a given stored result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

#: contracts/python/ssb_contracts/config.py -> contracts/config/thresholds.json
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "thresholds.json"


@dataclass(frozen=True)
class FaceThresholds:
    """Raw cosine-similarity boundaries. Not probabilities, not percentages."""

    match: float
    review: float

    def classify(self, similarity: float) -> str:
        if similarity >= self.match:
            return "MATCH"
        if similarity >= self.review:
            return "REVIEW"
        return "NO_MATCH"


@dataclass(frozen=True)
class ForensicsThresholds:
    tampered_at_or_above: float
    review_at_or_above: float
    region_reporting_floor: float


@dataclass(frozen=True)
class RiskBands:
    review_at_or_above: float
    high_at_or_above: float


@dataclass(frozen=True)
class RiskConfig:
    weights: Dict[str, float]
    bands: RiskBands
    minimum_evidence_weight: float
    escalations: Dict[str, str]


@dataclass(frozen=True)
class OcrThresholds:
    low_confidence_below: float
    review_confidence_below: float


@dataclass(frozen=True)
class Thresholds:
    config_version: str
    face: FaceThresholds
    forensics: ForensicsThresholds
    risk: RiskConfig
    ocr: OcrThresholds
    #: PatchCore is not implemented, so this is None rather than a placeholder
    #: number that could be mistaken for a calibrated value.
    anomaly_at_or_above: Optional[float]


def _strip_comments(block: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in block.items() if not key.startswith("_")}


@lru_cache(maxsize=1)
def load(path: Optional[Path] = None) -> Thresholds:
    raw = json.loads((path or CONFIG_PATH).read_text(encoding="utf-8"))

    face = _strip_comments(raw["face_verification"])
    forensics = _strip_comments(raw["document_forensics"])
    risk = _strip_comments(raw["risk_fusion"])
    ocr = _strip_comments(raw["ocr"])
    anomaly = _strip_comments(raw["anomaly"])

    return Thresholds(
        config_version=raw["config_version"],
        face=FaceThresholds(match=face["match"], review=face["review"]),
        forensics=ForensicsThresholds(
            tampered_at_or_above=forensics["tampered_at_or_above"],
            review_at_or_above=forensics["review_at_or_above"],
            region_reporting_floor=forensics["region_reporting_floor"],
        ),
        risk=RiskConfig(
            weights=dict(risk["weights"]),
            bands=RiskBands(
                review_at_or_above=risk["bands"]["review_at_or_above"],
                high_at_or_above=risk["bands"]["high_at_or_above"],
            ),
            minimum_evidence_weight=risk["minimum_evidence_weight"],
            escalations=_strip_comments(risk["escalations"]),
        ),
        ocr=OcrThresholds(
            low_confidence_below=ocr["low_confidence_below"],
            review_confidence_below=ocr["review_confidence_below"],
        ),
        anomaly_at_or_above=anomaly["anomalous_at_or_above"],
    )
