"""
Document forensics - MOCK implementation.

The production module will be:

    corrected document image
        -> DINOv2 ViT-B/14
        -> forensic classification head  (tampered / tamper_score / type)
        +  patch localisation head       (suspicious regions)
        -> DocumentForensicsResult

None of that exists yet. No weights are downloaded, no model is trained, and no
dataset ships with this package. What exists is the service boundary and a mock
behind it that emits the identical contract, so every consumer downstream - the
fusion engine, the case assembler, the officer UI, the database - is exercised
now exactly as it will be when the real head lands.

Replacing the mock is a one-line change in the registry:

    MockDocumentForensicsService  ->  DinoV2DocumentForensicsService

No consumer changes, because no consumer knows which one it is talking to. That
is why `DocumentForensicsService` below is an abstract base rather than a
convenience wrapper, and why nothing in the emitted payload hints at being mock
data apart from `model_version`, which is meant to.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from ..config import Thresholds, load as load_thresholds
from ..core import Envelope, Module, ModuleError, failed, partial, success
from ..modules import (
    DocumentForensicsResult,
    ManipulationType,
    SuspiciousRegion,
)

MOCK_MODEL_VERSION = "mock-dinov2-v0"


class ForensicsScenario(str, Enum):
    """
    The states the real service will be able to reach, each reproducible on
    demand so integration tests and demonstrations can exercise all of them.
    """

    GENUINE = "GENUINE"
    PHOTO_REPLACEMENT = "PHOTO_REPLACEMENT"
    TEXT_MANIPULATION = "TEXT_MANIPULATION"
    STAMP_SIGNATURE_MANIPULATION = "STAMP_SIGNATURE_MANIPULATION"
    COPY_PASTE_SPLICING = "COPY_PASTE_SPLICING"
    UNKNOWN_MANIPULATION = "UNKNOWN_MANIPULATION"
    #: Classifier fires, localiser resolves nothing. A real and important state:
    #: an empty region list must not read as "nothing found".
    TAMPERED_NO_REGION = "TAMPERED_NO_REGION"
    #: The module ran and could not produce a result at all.
    SERVICE_FAILURE = "SERVICE_FAILURE"


class DocumentForensicsService(ABC):
    """
    The boundary every consumer depends on.

    Implementations: `MockDocumentForensicsService` today,
    `DinoV2DocumentForensicsService` once the model exists.
    """

    @abstractmethod
    def analyse(self, case_id: str, image_path: Optional[str] = None) -> Envelope:
        """Returns a `document_forensics` envelope. Never raises for an expected
        failure - a failure is reported as a FAILED envelope so one module going
        down cannot take the screening with it."""


#: Deterministic per-scenario outputs. Regions are [x, y, w, h] normalised
#: against the corrected document image, placed where that manipulation class
#: actually appears on an ID document: the portrait on the left, the data fields
#: in the middle band, stamps low and right, the MRZ across the bottom.
_SCENARIOS = {
    ForensicsScenario.GENUINE: {
        "tampered": False,
        "tamper_score": 0.04,
        "manipulation_type": ManipulationType.NONE,
        "type_score": None,
        "regions": [],
    },
    ForensicsScenario.PHOTO_REPLACEMENT: {
        "tampered": True,
        "tamper_score": 0.91,
        "manipulation_type": ManipulationType.PHOTO_REPLACEMENT,
        "type_score": 0.87,
        "regions": [
            (
                (0.08, 0.28, 0.27, 0.45),
                0.94,
                "The security overlay is discontinuous at the portrait boundary.",
            ),
            (
                (0.09, 0.24, 0.29, 0.06),
                0.61,
                "Lamination thickness changes along the upper portrait edge.",
            ),
        ],
    },
    ForensicsScenario.TEXT_MANIPULATION: {
        "tampered": True,
        "tamper_score": 0.78,
        "manipulation_type": ManipulationType.TEXT_MANIPULATION,
        "type_score": 0.74,
        "regions": [
            (
                (0.44, 0.22, 0.30, 0.09),
                0.81,
                "Character spacing in the document number field is irregular "
                "compared with the fields adjacent to it.",
            )
        ],
    },
    ForensicsScenario.STAMP_SIGNATURE_MANIPULATION: {
        "tampered": True,
        "tamper_score": 0.69,
        "manipulation_type": ManipulationType.STAMP_SIGNATURE_MANIPULATION,
        "type_score": 0.66,
        "regions": [
            (
                (0.58, 0.66, 0.30, 0.20),
                0.72,
                "Ink distribution in the seal is inconsistent with an impression "
                "made by a genuine die.",
            )
        ],
    },
    ForensicsScenario.COPY_PASTE_SPLICING: {
        "tampered": True,
        "tamper_score": 0.83,
        "manipulation_type": ManipulationType.COPY_PASTE_SPLICING,
        "type_score": 0.79,
        "regions": [
            (
                (0.36, 0.40, 0.26, 0.12),
                0.86,
                "Substrate noise in this block does not match its surround, "
                "consistent with a region copied from elsewhere.",
            ),
            (
                (0.06, 0.80, 0.88, 0.13),
                0.55,
                "The machine-readable zone shares the noise signature of the "
                "block above.",
            ),
        ],
    },
    ForensicsScenario.UNKNOWN_MANIPULATION: {
        "tampered": True,
        "tamper_score": 0.62,
        "manipulation_type": ManipulationType.OTHER,
        "type_score": 0.31,
        "regions": [
            (
                (0.52, 0.30, 0.34, 0.26),
                0.64,
                "This region departs from the expected characteristics of a "
                "genuine document in a way that matches no known class.",
            )
        ],
    },
    ForensicsScenario.TAMPERED_NO_REGION: {
        "tampered": True,
        "tamper_score": 0.71,
        "manipulation_type": ManipulationType.OTHER,
        "type_score": 0.28,
        "regions": [],
    },
}


class MockDocumentForensicsService(DocumentForensicsService):
    """
    Deterministic stand-in for the DINOv2 forensics head.

    Scenario selection is either explicit (tests, demonstrations) or derived from
    the case identifier, so a given case replays identically on every run and
    across restarts.
    """

    def __init__(
        self,
        scenario: Optional[ForensicsScenario] = None,
        thresholds: Optional[Thresholds] = None,
    ) -> None:
        self._forced_scenario = scenario
        self._thresholds = thresholds or load_thresholds()

    def scenario_for(self, case_id: str) -> ForensicsScenario:
        if self._forced_scenario is not None:
            return self._forced_scenario
        digest = hashlib.sha256(case_id.encode("utf-8")).digest()
        # Service failure is excluded from the derived pool: an unprompted
        # failure would make ordinary demonstrations flaky. It is reachable only
        # by asking for it.
        pool = [s for s in ForensicsScenario if s is not ForensicsScenario.SERVICE_FAILURE]
        return pool[digest[0] % len(pool)]

    def analyse(self, case_id: str, image_path: Optional[str] = None) -> Envelope:
        del image_path  # The real service reads it; the mock does not need to.
        scenario = self.scenario_for(case_id)

        if scenario is ForensicsScenario.SERVICE_FAILURE:
            return failed(
                case_id=case_id,
                module=Module.DOCUMENT_FORENSICS,
                model_version=MOCK_MODEL_VERSION,
                errors=[
                    ModuleError(
                        code="FORENSICS_UNAVAILABLE",
                        message=(
                            "Forensic analysis could not complete. The remaining "
                            "findings are unaffected, but this document has not "
                            "been examined for tampering."
                        ),
                        retryable=True,
                    )
                ],
            )

        spec = _SCENARIOS[scenario]
        floor = self._thresholds.forensics.region_reporting_floor
        regions = [
            SuspiciousRegion(bbox=list(bbox), score=score, note=note)
            for bbox, score, note in spec["regions"]
            if score >= floor
        ]

        result = DocumentForensicsResult(
            tampered=bool(spec["tampered"]),
            tamper_score=float(spec["tamper_score"]),
            manipulation_type=spec["manipulation_type"],
            type_score=spec["type_score"],
            suspicious_regions=regions,
        )

        # A classifier that fires without the localiser resolving a region is a
        # usable but incomplete result, so it is reported as PARTIAL rather than
        # SUCCESS. The officer is told the region could not be shown instead of
        # being left to infer it from an empty list.
        if result.tampered and not result.suspicious_regions:
            return partial(
                case_id=case_id,
                module=Module.DOCUMENT_FORENSICS,
                model_version=MOCK_MODEL_VERSION,
                result=result.to_dict(),
                errors=[
                    ModuleError(
                        code="LOCALISATION_INCONCLUSIVE",
                        message=(
                            "Tampering was detected but could not be localised to "
                            "a region of the document."
                        ),
                        retryable=False,
                    )
                ],
            )

        return success(
            case_id=case_id,
            module=Module.DOCUMENT_FORENSICS,
            model_version=MOCK_MODEL_VERSION,
            result=result.to_dict(),
        )
