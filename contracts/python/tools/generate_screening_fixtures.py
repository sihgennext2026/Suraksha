"""
Generates the canonical screening fixtures the React Native application replays
when no backend is reachable.

Why generate rather than hand-write: the application must not contain a second
implementation of the fusion, validation or decision logic. It has no business
deciding what MATCH means, how a missing module affects a score, or how evidence
is ranked. So the mock backend inside the app does not compute anything - it
replays case documents produced here, by the same engine the real backend runs.

Run after changing a threshold, a weight, or the fusion engine:

    cd contracts/python
    python tools/generate_screening_fixtures.py

The output lands in src/fixtures/screening/ and is committed, so an offline
checkout can develop and test the frontend with no Python at all.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ssb_contracts import (  # noqa: E402
    DocumentType,
    Module,
    ModuleError,
    assemble,
    failed,
    not_available,
    success,
)
from ssb_contracts.adapters import face_arcface, ocr_extraction, validation_rules  # noqa: E402
from ssb_contracts.modules import CheckStatus, ValidationCheck  # noqa: E402
from ssb_contracts.services import (  # noqa: E402
    ForensicsScenario,
    MockDocumentForensicsService,
)

OUTPUT_DIR = ROOT.parents[1] / "src" / "fixtures" / "screening"


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


class _Quality:
    """Shaped like faceverify.quality.QualityResult."""

    def __init__(self, ok: bool, blur: float, brightness: float, yaw: float) -> None:
        self.quality_ok = ok
        self.face_size_ok = True
        self.brightness_ok = brightness > 60
        self.blur_ok = blur > 15
        self.pose_ok = abs(yaw) < 0.25
        self.face_width = 186.0
        self.face_height = 214.0
        self.brightness = brightness
        self.blur_score = blur
        self.yaw_proxy = yaw
        self.roll = 1.4


class _Verification:
    """Shaped like faceverify.pipeline.VerificationResult."""

    def __init__(self, similarity: float, doc: _Quality, live: _Quality) -> None:
        self.similarity = similarity
        self.decision = None  # let the adapter classify from shared thresholds
        self.quality_a = doc
        self.quality_b = live


def face(case_id: str, similarity: float, *, doc_ok: bool = True) -> Any:
    return face_arcface.from_verification_result(
        case_id,
        _Verification(
            similarity,
            _Quality(doc_ok, 38.0 if doc_ok else 9.0, 118.0, 0.06),
            _Quality(True, 61.0, 134.0, 0.03),
        ),
    )


def ocr(
    case_id: str,
    document_type: DocumentType,
    subject: Dict[str, Optional[str]],
    *,
    mrz_lines: Optional[List[str]] = None,
    confidence: float = 0.97,
    detected: bool = True,
) -> Any:
    return ocr_extraction.from_extract_response(
        case_id,
        document_type,
        {
            "detected": detected,
            "detection_confidence": 0.98,
            "detection_box": [62, 118, 938, 812],
            "orientation_corrected": True,
            "correction_mode": "segmentation_quad_warp",
            "structured_fields": subject,
            "structured_fields_sources": {
                key: ("mrz" if mrz_lines and key != "place_of_birth" else "label_same_line")
                if value
                else "not_found"
                for key, value in subject.items()
            },
            "mrz_lines": mrz_lines or [],
            "mrz_line_details": [{"confidence": 0.98} for _ in (mrz_lines or [])],
            "field_lines": [{"confidence": confidence} for _ in subject],
            "detected_lang_family": "latin",
        },
        image_size=(1000, 1000),
    )


def validation(case_id: str, document_type: DocumentType, checks: List[Dict[str, Any]]) -> Any:
    return validation_rules.from_validator_output(
        case_id, document_type, {"rules": checks}
    )


def rule(metric: str, status: str, reason: str) -> Dict[str, Any]:
    return {"metric": metric, "status": status, "reason": reason}


CLEAN_PASSPORT_RULES = [
    rule("required_surname", "PASS", "Required field 'surname' is present"),
    rule("required_given_names", "PASS", "Required field 'given_names' is present"),
    rule("required_passport_number", "PASS", "Required field 'passport_number' is present"),
    rule("passport_number_format", "PASS", "Document number matches the expected format"),
    rule("date_of_birth_format", "PASS", "Date of birth is a well-formed date"),
    rule("expiry_after_issue", "PASS", "Date of issue precedes date of expiry"),
    rule("dob_reasonable", "PASS", "Date of birth yields a plausible age"),
    rule("mrz_consistency", "PASS", "Printed fields agree with the machine-readable zone"),
]

SHARMA = {
    "surname": "SHARMA",
    "given_names": "ANIL KUMAR",
    "passport_number": "P4821736",
    "nationality": "IND",
    "date_of_birth": "1989-03-14",
    "sex": "M",
    "date_of_issue": "2021-07-02",
    "date_of_expiry": "2031-07-01",
    "place_of_birth": "LUCKNOW",
}

SHARMA_MRZ = [
    "P<INDSHARMA<<ANIL<KUMAR<<<<<<<<<<<<<<<<<<<<<",
    "P48217369IND8903142M3107013UP1989031409<<<02",
]

RAHMAN = {
    "surname": "RAHMAN",
    "given_names": "IMRAN",
    "passport_number": "B0473913",
    "nationality": "BGD",
    "date_of_birth": "1991-06-22",
    "sex": "M",
    "date_of_issue": "2019-02-11",
    "date_of_expiry": "2029-02-10",
    "place_of_birth": "SYLHET",
}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def build(case_id: str, name: str) -> Dict[str, Any]:
    """
    Each scenario names a state the officer-facing application has to render.
    Together they cover every combination of module status the UI can meet.
    """
    forensics = MockDocumentForensicsService

    if name == "genuine-passport":
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr(case_id, DocumentType.PASSPORT, SHARMA, mrz_lines=SHARMA_MRZ),
            validation=validation(case_id, DocumentType.PASSPORT, CLEAN_PASSPORT_RULES),
            face_verification=face(case_id, 0.61),
            document_forensics=forensics(ForensicsScenario.GENUINE).analyse(case_id),
        ).to_dict()

    if name == "face-no-match":
        # The document itself is sound; the person presenting it is not its
        # holder. Face is the only adverse signal.
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr(case_id, DocumentType.PASSPORT, SHARMA, mrz_lines=SHARMA_MRZ),
            validation=validation(case_id, DocumentType.PASSPORT, CLEAN_PASSPORT_RULES),
            face_verification=face(case_id, 0.04),
            document_forensics=forensics(ForensicsScenario.GENUINE).analyse(case_id),
        ).to_dict()

    if name == "face-review":
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr(case_id, DocumentType.PASSPORT, SHARMA, mrz_lines=SHARMA_MRZ),
            validation=validation(
                case_id,
                DocumentType.PASSPORT,
                CLEAN_PASSPORT_RULES[:-1]
                + [
                    rule(
                        "expiry_window",
                        "REVIEW",
                        "The document expires within six months",
                    )
                ],
            ),
            face_verification=face(case_id, 0.21, doc_ok=False),
            document_forensics=forensics(ForensicsScenario.GENUINE).analyse(case_id),
        ).to_dict()

    if name == "tampered-photo-replacement":
        return assemble(
            case_id,
            DocumentType.NATIONAL_ID,
            ocr=ocr(
                case_id,
                DocumentType.NATIONAL_ID,
                {
                    "surname": "LIMBU",
                    "given_names": "DEEPAK",
                    "id_number": "NID884120",
                    "date_of_birth": "1993-02-05",
                    "date_of_expiry": "2028-05-29",
                },
                confidence=0.9,
            ),
            validation=validation(
                case_id,
                DocumentType.NATIONAL_ID,
                [
                    rule("required_surname", "PASS", "Required field 'surname' is present"),
                    rule("required_id_number", "PASS", "Required field 'id_number' is present"),
                    rule("date_of_birth_format", "PASS", "Date of birth is well formed"),
                    rule("expiry_after_issue", "NOT_APPLICABLE", "No issue date on this document"),
                ],
            ),
            # A photo substitution the bearer matches: face agrees, because the
            # subject matches the photograph that was inserted.
            face_verification=face(case_id, 0.58),
            document_forensics=forensics(ForensicsScenario.PHOTO_REPLACEMENT).analyse(case_id),
        ).to_dict()

    if name == "tampered-text-and-invalid":
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr(case_id, DocumentType.PASSPORT, RAHMAN, mrz_lines=SHARMA_MRZ, confidence=0.81),
            validation=validation(
                case_id,
                DocumentType.PASSPORT,
                CLEAN_PASSPORT_RULES[:4]
                + [
                    rule(
                        "mrz_checksum",
                        "FAIL",
                        "Document number check digit: read 9, computed 4",
                    ),
                    rule(
                        "mrz_consistency",
                        "FAIL",
                        "Printed document number B0473913 does not match the zone value B0473918",
                    ),
                    rule("dob_reasonable", "PASS", "Date of birth yields a plausible age"),
                ],
            ),
            face_verification=face(case_id, 0.11),
            document_forensics=forensics(ForensicsScenario.TEXT_MANIPULATION).analyse(case_id),
        ).to_dict()

    if name == "tampered-no-region":
        # Classifier fires, localiser resolves nothing: forensics is PARTIAL and
        # the UI must not read the empty region list as "nothing found".
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr(case_id, DocumentType.PASSPORT, SHARMA, mrz_lines=SHARMA_MRZ),
            validation=validation(case_id, DocumentType.PASSPORT, CLEAN_PASSPORT_RULES),
            face_verification=face(case_id, 0.44),
            document_forensics=forensics(ForensicsScenario.TAMPERED_NO_REGION).analyse(case_id),
        ).to_dict()

    if name == "forensics-unavailable":
        # One module down; the screening still completes and the officer is told
        # the document was not examined for tampering.
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr(case_id, DocumentType.PASSPORT, SHARMA, mrz_lines=SHARMA_MRZ),
            validation=validation(case_id, DocumentType.PASSPORT, CLEAN_PASSPORT_RULES),
            face_verification=face(case_id, 0.55),
            document_forensics=forensics(ForensicsScenario.SERVICE_FAILURE).analyse(case_id),
        ).to_dict()

    if name == "face-failed":
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr(case_id, DocumentType.PASSPORT, SHARMA, mrz_lines=SHARMA_MRZ),
            validation=validation(case_id, DocumentType.PASSPORT, CLEAN_PASSPORT_RULES),
            face_verification=face_arcface.from_failure(
                case_id,
                "NO_FACE_IN_SUBJECT_CAPTURE",
                "No face could be located in the subject photograph, so no "
                "comparison was made.",
            ),
            document_forensics=forensics(ForensicsScenario.GENUINE).analyse(case_id),
        ).to_dict()

    if name == "unsupported-document-type":
        # travel_authorization has no OCR field schema and no validation rule
        # set. Both modules say so explicitly rather than borrowing another
        # type's rules and reporting a meaningless PASS.
        return assemble(
            case_id,
            DocumentType.TRAVEL_AUTHORIZATION,
            ocr=ocr_extraction.from_extract_response(
                case_id, DocumentType.TRAVEL_AUTHORIZATION, {"detected": True}
            ),
            validation=validation_rules.from_validator_output(
                case_id, DocumentType.TRAVEL_AUTHORIZATION, {"rules": []}
            ),
            face_verification=face(case_id, 0.52),
            document_forensics=forensics(ForensicsScenario.GENUINE).analyse(case_id),
        ).to_dict()

    if name == "all-modules-down":
        # Nothing was measured. The fusion engine must not clear the case on the
        # strength of no evidence at all.
        return assemble(
            case_id,
            DocumentType.PASSPORT,
            ocr=ocr_extraction.from_failure(
                case_id, "OCR_UNAVAILABLE", "The extraction service is unavailable."
            ),
            validation=not_available(
                case_id,
                Module.VALIDATION,
                "NO_EXTRACTION",
                "No extracted fields were available to validate.",
            ),
            face_verification=face_arcface.from_failure(
                case_id, "FACE_UNAVAILABLE", "The face comparison service is unavailable."
            ),
            document_forensics=failed(
                case_id,
                Module.DOCUMENT_FORENSICS,
                "mock-dinov2-v0",
                [
                    ModuleError(
                        code="FORENSICS_UNAVAILABLE",
                        message="Forensic analysis could not complete.",
                    )
                ],
            ),
        ).to_dict()

    raise ValueError(f"Unknown scenario {name}")


SCENARIOS = [
    "genuine-passport",
    "face-review",
    "face-no-match",
    "face-failed",
    "tampered-photo-replacement",
    "tampered-text-and-invalid",
    "tampered-no-region",
    "forensics-unavailable",
    "unsupported-document-type",
    "all-modules-down",
]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    index = []

    for name in SCENARIOS:
        # A fixed case id per scenario keeps the generated file byte-stable, so
        # regenerating produces no diff unless something real changed.
        case_id = f"FIXTURE-{name.upper().replace('-', '_')}"
        document = build(case_id, name)
        # The timestamps are stamped at replay time by the app; zeroing them here
        # keeps the committed fixtures deterministic.
        document["generated_at"] = "2026-01-01T00:00:00.000Z"
        for key, value in document.items():
            if isinstance(value, dict) and "timestamp" in value:
                value["timestamp"] = "2026-01-01T00:00:00.000Z"

        path = OUTPUT_DIR / f"{name}.json"
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        risk = document["risk"]["result"]
        index.append(
            {
                "id": name,
                "document_type": document["document_type"],
                "risk_level": risk["risk_level"],
                "risk_score": risk["risk_score"],
            }
        )
        print(
            f"{name:32} {document['document_type']:22} "
            f"{risk['risk_level']:7} {risk['risk_score']:.3f}"
        )

    (OUTPUT_DIR / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n{len(SCENARIOS)} fixtures written to {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
