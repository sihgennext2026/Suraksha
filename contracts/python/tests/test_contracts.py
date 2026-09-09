"""
Contract tests for the canonical screening contracts.

These assert the properties the whole integration rests on, in preference to
asserting shapes: that absent evidence never becomes a finding, that a raw
cosine similarity is never rescaled, that a strong signal cannot be diluted, and
that a module which did not run is visible in the record rather than missing
from it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ssb_contracts import (
    DocumentType,
    Module,
    ModuleError,
    ModuleStatus,
    assemble,
    anomaly_unavailable,
    failed,
    load_thresholds,
    not_available,
    parse,
    success,
    supports,
)
from ssb_contracts.adapters import face_arcface, ocr_phase1, validation_backend
from ssb_contracts.modules import (
    CheckStatus,
    FaceDecision,
    ManipulationType,
    RiskLevel,
    ValidationCheck,
    ValidationDecision,
)
from ssb_contracts.services import (
    EvidenceFusionEngine,
    ForensicsScenario,
    FusionInput,
    MockDocumentForensicsService,
)

CASE = "SSB-2026-0001"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "ssb-screening.schema.json"


# ---------------------------------------------------------------------------
# Helpers that build each module's evidence at a chosen outcome
# ---------------------------------------------------------------------------


def face_envelope(similarity: float):
    class _Quality:
        quality_ok = True
        face_width = 180.0
        face_height = 200.0
        brightness = 128.0
        blur_score = 42.0
        yaw_proxy = 0.04
        roll = 1.2

    class _Result:
        pass

    result = _Result()
    result.similarity = similarity
    result.decision = None  # force the adapter to classify from thresholds
    result.quality_a = _Quality()
    result.quality_b = _Quality()
    return face_arcface.from_verification_result(CASE, result)


def validation_envelope(*statuses: CheckStatus):
    checks = [
        ValidationCheck(
            rule_id=f"rule_{index}",
            status=status,
            message=f"rule {index} was {status.value}",
        )
        for index, status in enumerate(statuses)
    ]
    result = validation_backend.build_result(checks)
    return success(
        CASE, Module.VALIDATION, validation_backend.RULE_ENGINE_VERSION, result.to_dict()
    )


def ocr_envelope(*, detected: bool = True, confidence: float = 0.96):
    return ocr_phase1.from_extract_response(
        CASE,
        DocumentType.PASSPORT,
        {
            "detected": detected,
            "detection_confidence": 0.98,
            "detection_box": [10, 20, 210, 320],
            "orientation_corrected": True,
            "structured_fields": {"surname": "SHARMA", "passport_number": "P4821736"},
            "structured_fields_sources": {"surname": "mrz", "passport_number": "mrz"},
            "mrz_lines": ["P<INDSHARMA<<ANIL", "P48217369IND8903142M3107013"],
            "mrz_line_details": [{"confidence": 0.98}],
            "field_lines": [{"confidence": confidence}, {"confidence": confidence}],
            "detected_lang_family": "latin",
        },
        image_size=(1000, 1000),
    )


def forensics_envelope(scenario: ForensicsScenario):
    return MockDocumentForensicsService(scenario).analyse(CASE)


def fuse(**overrides):
    evidence = FusionInput(
        ocr=overrides.get("ocr", ocr_envelope()),
        validation=overrides.get("validation", validation_envelope(CheckStatus.PASS)),
        face_verification=overrides.get("face_verification", face_envelope(0.55)),
        document_forensics=overrides.get(
            "document_forensics", forensics_envelope(ForensicsScenario.GENUINE)
        ),
        anomaly=overrides.get("anomaly", anomaly_unavailable(CASE)),
    )
    return EvidenceFusionEngine().fuse(CASE, evidence).result


# ---------------------------------------------------------------------------
# Envelope invariants
# ---------------------------------------------------------------------------


class TestEnvelope:
    def test_a_non_success_status_can_never_carry_a_result(self):
        # The invariant every consumer relies on: seeing FAILED is enough to stop
        # reading, because there is provably nothing behind it.
        with pytest.raises(ValueError):
            failed(CASE, Module.OCR, "v1", []).__class__(
                case_id=CASE,
                module=Module.OCR,
                status=ModuleStatus.FAILED,
                model_version="v1",
                result={"anything": True},
            )

    def test_success_must_carry_a_result(self):
        from ssb_contracts.core import Envelope

        with pytest.raises(ValueError):
            Envelope(
                case_id=CASE,
                module=Module.OCR,
                status=ModuleStatus.SUCCESS,
                model_version="v1",
                result=None,
            )

    def test_failed_and_not_available_do_not_count_as_evidence(self):
        assert ModuleStatus.SUCCESS.has_evidence
        assert ModuleStatus.PARTIAL.has_evidence
        assert not ModuleStatus.FAILED.has_evidence
        assert not ModuleStatus.NOT_AVAILABLE.has_evidence

    def test_every_envelope_carries_schema_and_model_version(self):
        envelope = forensics_envelope(ForensicsScenario.GENUINE).to_dict()
        assert envelope["schema_version"] == "1.0"
        assert envelope["model_version"] == "mock-dinov2-v0"
        assert envelope["case_id"] == CASE
        assert envelope["timestamp"].endswith("Z")


# ---------------------------------------------------------------------------
# Document types
# ---------------------------------------------------------------------------


class TestDocumentTypes:
    def test_the_legacy_react_native_spelling_still_parses(self):
        assert parse("driving_licence") is DocumentType.DRIVING_LICENSE
        assert parse("driving_license") is DocumentType.DRIVING_LICENSE

    def test_unsupported_types_are_declared_rather_than_deleted(self):
        # travel_authorization survives as an officer-selectable type, but every
        # backend module says plainly that it cannot process it.
        ocr_ok, ocr_reason = supports(Module.OCR, DocumentType.TRAVEL_AUTHORIZATION)
        val_ok, val_reason = supports(Module.VALIDATION, DocumentType.TRAVEL_AUTHORIZATION)
        assert not ocr_ok and ocr_reason
        assert not val_ok and val_reason

    def test_other_never_borrows_another_types_rules(self):
        envelope = validation_backend.from_validator_output(
            CASE, DocumentType.OTHER, {"rules": [{"metric": "x", "status": "PASS"}]}
        )
        # Even with rules supplied, an unsupported type returns NOT_AVAILABLE
        # rather than a fabricated PASS.
        assert envelope.status is ModuleStatus.NOT_AVAILABLE
        assert envelope.result is None

    def test_only_passport_and_visa_bear_an_mrz(self):
        from ssb_contracts import has_mrz

        assert has_mrz(DocumentType.PASSPORT)
        assert has_mrz(DocumentType.VISA)
        assert not has_mrz(DocumentType.DRIVING_LICENSE)
        assert not has_mrz(DocumentType.NATIONAL_ID)
        assert not has_mrz(DocumentType.PERMIT)


# ---------------------------------------------------------------------------
# Face verification
# ---------------------------------------------------------------------------


class TestFaceVerification:
    def test_thresholds_come_from_the_shared_configuration(self):
        thresholds = load_thresholds().face
        # These are the values gowtham-pepline actually classifies with. The old
        # React Native assumptions (0.85 / 0.60) were on a different scale.
        assert thresholds.match == 0.30
        assert thresholds.review == 0.14

    def test_match(self):
        result = face_envelope(0.42).result
        assert result["decision"] == FaceDecision.MATCH.value
        assert result["similarity"] == 0.42

    def test_review(self):
        assert face_envelope(0.20).result["decision"] == FaceDecision.REVIEW.value

    def test_no_match(self):
        assert face_envelope(0.05).result["decision"] == FaceDecision.NO_MATCH.value

    def test_similarity_is_carried_raw_and_never_rescaled(self):
        result = face_envelope(0.31).result
        assert result["similarity"] == pytest.approx(0.31)
        # A rescaled value would land near 31 or 0.655; neither is acceptable.
        assert result["similarity"] <= 1.0

    def test_thresholds_travel_with_the_result(self):
        # So that re-tuning later cannot change the meaning of a stored case.
        result = face_envelope(0.31).result
        assert result["thresholds"] == {"match": 0.30, "review": 0.14}

    def test_quality_score_is_null_because_no_model_provides_one(self):
        quality = face_envelope(0.31).result["quality"]["document_face"]
        assert quality["score"] is None, "a fabricated quality score has crept in"
        assert quality["acceptable"] is True
        assert quality["metrics"]["blur_score"] == 42.0

    def test_a_failed_comparison_is_not_a_non_match(self):
        envelope = face_arcface.from_failure(CASE, "NO_FACE", "No face was found.")
        assert envelope.status is ModuleStatus.FAILED
        assert envelope.result is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_all_pass_is_valid(self):
        result = validation_envelope(CheckStatus.PASS, CheckStatus.PASS).result
        assert result["decision"] == ValidationDecision.VALID.value
        assert result["summary"]["passed"] == 2

    def test_a_failed_rule_makes_the_rule_set_invalid(self):
        result = validation_envelope(CheckStatus.PASS, CheckStatus.FAIL).result
        assert result["decision"] == ValidationDecision.INVALID.value
        assert result["summary"]["failed"] == 1

    def test_not_available_is_not_a_failure(self):
        result = validation_envelope(
            CheckStatus.PASS, CheckStatus.NOT_AVAILABLE, CheckStatus.NOT_APPLICABLE
        ).result
        assert result["decision"] == ValidationDecision.VALID.value
        assert result["summary"]["not_available"] == 1
        assert result["summary"]["not_applicable"] == 1
        assert result["summary"]["failed"] == 0

    def test_not_applicable_and_not_available_stay_distinct(self):
        result = validation_envelope(
            CheckStatus.NOT_APPLICABLE, CheckStatus.NOT_AVAILABLE
        ).result
        assert result["summary"]["not_applicable"] == 1
        assert result["summary"]["not_available"] == 1

    def test_an_unknown_upstream_status_is_never_guessed_into_pass(self):
        envelope = validation_backend.from_validator_output(
            CASE,
            DocumentType.PASSPORT,
            {"rules": [{"metric": "mystery", "status": "SOMETHING_NEW"}]},
        )
        assert envelope.result["checks"][0]["status"] == CheckStatus.NOT_AVAILABLE.value

    def test_upstream_vocabulary_is_mapped_faithfully(self):
        envelope = validation_backend.from_validator_output(
            CASE,
            DocumentType.PASSPORT,
            {
                "rules": [
                    {"metric": "required_name", "status": "PASS", "reason": "present"},
                    {"metric": "mrz_checksum", "status": "FAIL", "reason": "mismatch"},
                    {"metric": "expiry", "status": "NOT_APPLICABLE", "reason": "n/a"},
                ]
            },
        )
        checks = envelope.result["checks"]
        assert [check["rule_id"] for check in checks] == [
            "required_name",
            "mrz_checksum",
            "expiry",
        ]
        assert checks[0]["message"] == "present"


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------


class TestOcr:
    def test_pixel_boxes_are_normalised_against_the_supplied_image_size(self):
        box = ocr_envelope().result["detection"]["box"]
        assert box == [0.01, 0.02, 0.2, 0.3]

    def test_a_box_is_omitted_rather_than_guessed_without_image_dimensions(self):
        envelope = ocr_phase1.from_extract_response(
            CASE,
            DocumentType.PASSPORT,
            {"detected": True, "detection_box": [10, 20, 210, 320]},
        )
        assert envelope.result["detection"]["box"] is None

    def test_mrz_checksum_is_null_because_extraction_does_not_evaluate_it(self):
        mrz = ocr_envelope().result["mrz"]
        assert mrz["present"] is True
        assert mrz["checksum_valid"] is None, "null must not become false"

    def test_a_non_mrz_document_reports_no_zone(self):
        envelope = ocr_phase1.from_extract_response(
            CASE,
            DocumentType.DRIVING_LICENSE,
            {"detected": True, "mrz_lines": ["SHOULD", "NOT", "HAPPEN"]},
        )
        assert envelope.result["mrz"]["present"] is False

    def test_an_undetected_document_is_partial_not_failed(self):
        envelope = ocr_envelope(detected=False)
        assert envelope.status is ModuleStatus.PARTIAL
        assert envelope.result is not None
        assert envelope.errors[0].code == "DOCUMENT_NOT_LOCATED"


# ---------------------------------------------------------------------------
# Document forensics (mock DINOv2)
# ---------------------------------------------------------------------------


class TestDocumentForensicsMock:
    def test_genuine(self):
        result = forensics_envelope(ForensicsScenario.GENUINE).result
        assert result["tampered"] is False
        assert result["manipulation_type"] == ManipulationType.NONE.value
        assert result["suspicious_regions"] == []

    @pytest.mark.parametrize(
        "scenario,expected_type",
        [
            (ForensicsScenario.PHOTO_REPLACEMENT, ManipulationType.PHOTO_REPLACEMENT),
            (ForensicsScenario.TEXT_MANIPULATION, ManipulationType.TEXT_MANIPULATION),
            (
                ForensicsScenario.STAMP_SIGNATURE_MANIPULATION,
                ManipulationType.STAMP_SIGNATURE_MANIPULATION,
            ),
            (ForensicsScenario.COPY_PASTE_SPLICING, ManipulationType.COPY_PASTE_SPLICING),
            (ForensicsScenario.UNKNOWN_MANIPULATION, ManipulationType.OTHER),
        ],
    )
    def test_each_manipulation_class_is_reachable(self, scenario, expected_type):
        result = forensics_envelope(scenario).result
        assert result["tampered"] is True
        assert result["manipulation_type"] == expected_type.value
        assert result["tamper_score"] > 0.5

    def test_service_failure_returns_no_result(self):
        envelope = forensics_envelope(ForensicsScenario.SERVICE_FAILURE)
        assert envelope.status is ModuleStatus.FAILED
        assert envelope.result is None
        assert envelope.errors[0].code == "FORENSICS_UNAVAILABLE"

    def test_tampered_without_a_region_is_partial_not_success(self):
        # An empty region list must not read as "nothing found".
        envelope = forensics_envelope(ForensicsScenario.TAMPERED_NO_REGION)
        assert envelope.status is ModuleStatus.PARTIAL
        assert envelope.result["tampered"] is True
        assert envelope.result["suspicious_regions"] == []
        assert envelope.errors[0].code == "LOCALISATION_INCONCLUSIVE"

    def test_regions_are_normalised_and_orderable(self):
        regions = forensics_envelope(ForensicsScenario.PHOTO_REPLACEMENT).result[
            "suspicious_regions"
        ]
        assert regions
        for region in regions:
            assert len(region["bbox"]) == 4
            assert all(0.0 <= value <= 1.0 for value in region["bbox"])

    def test_scenario_selection_is_deterministic_per_case(self):
        service = MockDocumentForensicsService()
        assert service.scenario_for("SSB-2026-0042") == service.scenario_for("SSB-2026-0042")

    def test_an_unprompted_service_failure_is_never_selected(self):
        service = MockDocumentForensicsService()
        for index in range(200):
            scenario = service.scenario_for(f"SSB-2026-{index:04d}")
            assert scenario is not ForensicsScenario.SERVICE_FAILURE

    def test_the_mock_is_replaceable_behind_the_service_type(self):
        from ssb_contracts.services import DocumentForensicsService

        assert isinstance(MockDocumentForensicsService(), DocumentForensicsService)


# ---------------------------------------------------------------------------
# Evidence fusion
# ---------------------------------------------------------------------------


class TestRiskFusion:
    def test_a_clean_screening_is_low(self):
        risk = fuse(
            face_verification=face_envelope(0.62),
            validation=validation_envelope(CheckStatus.PASS, CheckStatus.PASS),
            document_forensics=forensics_envelope(ForensicsScenario.GENUINE),
        )
        assert risk["risk_level"] == RiskLevel.LOW.value
        assert risk["risk_score"] < 0.3

    def test_detected_tampering_escalates_to_high(self):
        risk = fuse(document_forensics=forensics_envelope(ForensicsScenario.PHOTO_REPLACEMENT))
        assert risk["risk_level"] == RiskLevel.HIGH.value
        assert any("Tampering" in reason for reason in risk["escalations"])

    def test_a_face_non_match_cannot_be_diluted_below_review(self):
        # Everything else is clean; without the escalation the weighted mean
        # would leave this in the LOW band.
        risk = fuse(face_verification=face_envelope(0.02))
        assert risk["risk_level"] in (RiskLevel.REVIEW.value, RiskLevel.HIGH.value)

    def test_a_missing_module_never_scores_worse_than_its_worst_finding(self):
        """
        The guarantee that matters: an absent module must never be treated as
        though it had reported the worst thing it could report. Being down is
        not evidence of fraud.
        """
        forensics_down = failed(
            CASE,
            Module.DOCUMENT_FORENSICS,
            "mock-dinov2-v0",
            [ModuleError(code="X", message="down")],
        )
        missing = fuse(document_forensics=forensics_down)
        adverse = fuse(
            document_forensics=forensics_envelope(ForensicsScenario.PHOTO_REPLACEMENT)
        )
        assert missing["risk_score"] < adverse["risk_score"]
        assert missing["risk_level"] != RiskLevel.HIGH.value

    def test_an_absent_module_contributes_no_weighted_risk(self):
        # Renormalisation can move the mean when a reassuring module drops out -
        # that is intentional, because the reassurance really is gone. What must
        # never happen is the absence itself adding risk.
        risk = fuse(
            document_forensics=failed(
                CASE,
                Module.DOCUMENT_FORENSICS,
                "mock-dinov2-v0",
                [ModuleError(code="X", message="down")],
            )
        )
        forensics = next(
            c for c in risk["contributors"] if c["source"] == "document_forensics"
        )
        assert forensics["counted"] is False
        assert forensics["weight"] is None
        assert forensics["severity"] == "NONE"
        assert risk["evidence_coverage"] < 1.0

    def test_an_unevaluated_mrz_checksum_is_not_a_checksum_failure(self):
        # Extraction does not decode the MRZ, so checksum_valid arrives as null.
        # Null must not be read as "tested and failed".
        risk = fuse(ocr=ocr_envelope())
        ocr = next(c for c in risk["contributors"] if c["source"] == "ocr")
        assert ocr["signal"] != "MRZ_CHECKSUM_FAILED"
        assert ocr["severity"] == "NONE"

    def test_an_unavailable_module_is_listed_but_not_counted(self):
        risk = fuse()
        anomaly = next(c for c in risk["contributors"] if c["source"] == "anomaly")
        assert anomaly["counted"] is False
        assert anomaly["weight"] is None
        assert anomaly["signal"] == "NOT_AVAILABLE"
        assert anomaly["severity"] == "NONE"

    def test_a_failed_module_is_reported_as_failed_not_as_a_finding(self):
        risk = fuse(
            face_verification=face_arcface.from_failure(
                CASE, "NO_FACE", "No face was found in the subject photograph."
            )
        )
        face = next(c for c in risk["contributors"] if c["source"] == "face_verification")
        assert face["signal"] == "FAILED"
        assert face["severity"] == "NONE"
        assert face["counted"] is False

    def test_coverage_is_reported_and_thin_evidence_cannot_clear(self):
        risk = fuse(
            ocr=ocr_phase1.from_failure(CASE, "OCR_DOWN", "Extraction unavailable."),
            validation=not_available(CASE, Module.VALIDATION, "X", "unavailable"),
            face_verification=face_arcface.from_failure(CASE, "X", "unavailable"),
            document_forensics=forensics_envelope(ForensicsScenario.SERVICE_FAILURE),
        )
        assert risk["evidence_coverage"] == 0.0
        # Nothing was measured, so a confident LOW would be unjustifiable.
        assert risk["risk_level"] == RiskLevel.REVIEW.value

    def test_an_inconclusive_module_cannot_be_averaged_into_a_clearance(self):
        # A face REVIEW plus four quiet modules used to fuse to 0.27 and land in
        # LOW. "I cannot tell" has to reach the officer.
        risk = fuse(face_verification=face_envelope(0.21))
        assert risk["risk_level"] == RiskLevel.REVIEW.value
        assert any("inconclusive" in reason for reason in risk["escalations"])

    def test_a_case_cannot_be_cleared_while_the_tamper_module_was_down(self):
        # The module that would have caught the problem never ran, so this is an
        # unexamined case rather than a low-risk one.
        risk = fuse(document_forensics=forensics_envelope(ForensicsScenario.SERVICE_FAILURE))
        assert risk["risk_level"] == RiskLevel.REVIEW.value
        assert risk["evidence_coverage"] < load_thresholds().risk.minimum_evidence_weight

    def test_a_full_clean_screening_still_clears(self):
        # The floors must not make every case REVIEW; a complete clean run is LOW
        # even though anomaly is permanently unavailable.
        risk = fuse(face_verification=face_envelope(0.62))
        assert risk["risk_level"] == RiskLevel.LOW.value
        assert risk["evidence_coverage"] == pytest.approx(0.96)

    def test_the_engine_is_not_called_lightgbm(self):
        risk = fuse()
        assert "lightgbm" not in risk["engine_version"].lower()
        assert risk["engine_version"].startswith("evidence-fusion")

    def test_thresholds_and_config_version_travel_with_the_result(self):
        risk = fuse()
        assert risk["config_version"] == load_thresholds().config_version
        assert risk["bands"]["review_at_or_above"] == 0.3
        assert risk["bands"]["high_at_or_above"] == 0.65

    def test_only_three_officer_facing_levels_exist(self):
        assert {level.value for level in RiskLevel} == {"LOW", "REVIEW", "HIGH"}

    def test_the_narrative_names_what_was_missing(self):
        risk = fuse()
        assert "anomaly analysis" in risk["narrative"].lower()
        assert "decision rests with the officer" in risk["narrative"].lower()


# ---------------------------------------------------------------------------
# Case-level assembly
# ---------------------------------------------------------------------------


class TestScreeningCase:
    def build(self, **overrides):
        return assemble(
            CASE,
            DocumentType.PASSPORT,
            ocr=overrides.get("ocr", ocr_envelope()),
            validation=overrides.get("validation", validation_envelope(CheckStatus.PASS)),
            face_verification=overrides.get("face_verification", face_envelope(0.55)),
            document_forensics=overrides.get(
                "document_forensics", forensics_envelope(ForensicsScenario.GENUINE)
            ),
        )

    def test_every_module_is_present_even_when_it_did_not_run(self):
        case = self.build().to_dict()
        for module in (
            "ocr",
            "validation",
            "face_verification",
            "document_forensics",
            "anomaly",
            "risk",
        ):
            assert module in case, f"{module} missing from the case document"
            assert case[module]["schema_version"] == "1.0"

    def test_anomaly_is_explicitly_not_available(self):
        anomaly = self.build().to_dict()["anomaly"]
        assert anomaly["status"] == "NOT_AVAILABLE"
        assert anomaly["result"] is None
        assert anomaly["errors"][0]["code"] == "ANOMALY_NOT_IMPLEMENTED"

    def test_the_evidence_index_is_built_by_the_backend(self):
        evidence = self.build().to_dict()["evidence"]
        assert {item["module"] for item in evidence} == {
            "ocr",
            "validation",
            "face_verification",
            "document_forensics",
            "anomaly",
        }
        for item in evidence:
            assert item["headline"] and item["detail"]

    def test_one_failed_module_does_not_stop_the_case_completing(self):
        case = self.build(
            document_forensics=forensics_envelope(ForensicsScenario.SERVICE_FAILURE)
        ).to_dict()
        assert case["document_forensics"]["status"] == "FAILED"
        # The rest of the screening still produced a result.
        assert case["ocr"]["status"] == "SUCCESS"
        assert case["risk"]["status"] == "SUCCESS"
        assert case["risk"]["result"]["risk_level"] in {"LOW", "REVIEW", "HIGH"}

    def test_a_tampered_case_reads_end_to_end(self):
        case = self.build(
            document_forensics=forensics_envelope(ForensicsScenario.PHOTO_REPLACEMENT),
            face_verification=face_envelope(0.05),
        ).to_dict()
        assert case["risk"]["result"]["risk_level"] == "HIGH"
        assert case["document_forensics"]["result"]["manipulation_type"] == "PHOTO_REPLACEMENT"
        assert case["document_forensics"]["result"]["suspicious_regions"]

    def test_the_case_document_is_json_serialisable(self):
        # It crosses a process boundary and is stored, so it must round-trip.
        payload = json.dumps(self.build().to_dict())
        assert json.loads(payload)["case_id"] == CASE


# ---------------------------------------------------------------------------
# Schema parity
# ---------------------------------------------------------------------------


class TestSchemaParity:
    def load_schema(self):
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_python_enums_match_the_canonical_schema(self):
        defs = self.load_schema()["$defs"]
        assert set(defs["documentType"]["enum"]) == {t.value for t in DocumentType}
        assert set(defs["moduleStatus"]["enum"]) == {s.value for s in ModuleStatus}
        assert set(defs["moduleName"]["enum"]) == {m.value for m in Module}
        assert set(defs["manipulationType"]["enum"]) == {
            m.value for m in ManipulationType
        }
        assert set(defs["validationCheckStatus"]["enum"]) == {
            s.value for s in CheckStatus
        }
        assert set(defs["riskResult"]["properties"]["risk_level"]["enum"]) == {
            level.value for level in RiskLevel
        }

    def test_the_schema_version_is_the_one_the_package_emits(self):
        from ssb_contracts import SCHEMA_VERSION

        assert self.load_schema()["$defs"]["schemaVersion"]["const"] == SCHEMA_VERSION
