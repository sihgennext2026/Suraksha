"""
Integration properties the two-sided pipeline must hold.

These cover the seams between modules rather than any one module's logic: that a
front-only document is unchanged by the existence of a back path, that the merge's
findings reach validation as ordinary checks, and that the fusion engine reads a
REVIEW as an inconclusive signal rather than as a failure.
"""

from ssb_contracts import assemble, not_available
from ssb_contracts.core import Module, ModuleStatus
from ssb_contracts.adapters import face_arcface, ocr_extraction, validation_rules
from ssb_contracts.document_types import DocumentType
from ssb_contracts.modules import (
    CheckStatus,
    FieldAgreement,
    FieldOrigin,
    ValidationCheck,
)
from ssb_contracts.services.forensics_mock import ForensicsScenario, MockDocumentForensicsService

CASE = "SSB-2026-FB"

FRONT = {
    "detected": True,
    "detection_confidence": 0.97,
    "detection_box": [10, 20, 210, 320],
    "structured_fields": {"name": "RAVI KUMAR", "document_number": "DL-0120", "address": None},
    "structured_fields_sources": {
        "name": "label_same_line",
        "document_number": "label_same_line",
        "address": "not_found",
    },
    "field_lines": [{"text": "RAVI KUMAR", "confidence": 0.94}],
    "detected_lang_family": "latin",
}

BACK = {
    "detected": True,
    "structured_fields": {"address": "12 Main Street", "document_number": "DL-0120"},
    "structured_fields_sources": {
        "address": "label_next_line",
        "document_number": "label_same_line",
    },
    "field_lines": [{"text": "12 MAIN STREET", "confidence": 0.9}],
}


class TestBackwardCompatibility:
    def test_a_front_only_document_is_unchanged_by_the_back_path(self):
        outcome = ocr_extraction.from_extract_response(CASE, DocumentType.DRIVING_LICENSE, FRONT)
        result = outcome.envelope.result

        # Every field still present, still attributed to the front, and with no
        # redundant reading list: a single-sided screening looks exactly as it
        # did before two sides existed.
        by_key = {f["key"]: f for f in result["fields"]}
        assert by_key["name"]["value"] == "RAVI KUMAR"
        assert by_key["name"]["origin"] == FieldOrigin.FRONT.value
        assert by_key["name"]["agreement"] == FieldAgreement.SINGLE_SOURCE.value
        assert by_key["name"]["readings"] == []

    def test_the_top_level_detection_block_still_describes_the_front(self):
        # Existing consumers read `detection` directly; per-side detail is
        # additive and must not have displaced it.
        outcome = ocr_extraction.from_extract_response(
            CASE, DocumentType.DRIVING_LICENSE, FRONT, back=BACK
        )
        result = outcome.envelope.result
        assert result["detection"]["detected"] is True
        assert result["detection"]["confidence"] == 0.97
        assert [side["side"] for side in result["sides"]] == ["front", "back"]

    def test_only_the_front_is_listed_when_there_is_no_back_capture(self):
        outcome = ocr_extraction.from_extract_response(CASE, DocumentType.DRIVING_LICENSE, FRONT)
        # A side that was never captured is absent, not present and empty.
        assert [side["side"] for side in outcome.envelope.result["sides"]] == ["front"]
        assert outcome.envelope.result["machine_codes"] == []


class TestFieldProvenanceIsPreserved:
    def test_every_merged_field_carries_value_origin_source_and_agreement(self):
        outcome = ocr_extraction.from_extract_response(
            CASE, DocumentType.DRIVING_LICENSE, FRONT, back=BACK
        )
        for entry in outcome.envelope.result["fields"]:
            assert entry["value"] is not None
            assert entry["origin"] in {o.value for o in FieldOrigin}
            assert entry["source"] is not None
            assert entry["agreement"] in {a.value for a in FieldAgreement}

    def test_a_back_only_field_is_attributed_to_the_back(self):
        outcome = ocr_extraction.from_extract_response(
            CASE, DocumentType.DRIVING_LICENSE, FRONT, back=BACK
        )
        address = next(f for f in outcome.envelope.result["fields"] if f["key"] == "address")
        assert address["value"] == "12 Main Street"
        assert address["origin"] == FieldOrigin.BACK.value

    def test_a_conflict_keeps_both_readings_with_their_origins(self):
        conflicting = dict(BACK, structured_fields={"name": "RAVI KUMARI"})
        outcome = ocr_extraction.from_extract_response(
            CASE, DocumentType.DRIVING_LICENSE, FRONT, back=conflicting
        )
        name = next(f for f in outcome.envelope.result["fields"] if f["key"] == "name")

        assert name["agreement"] == FieldAgreement.CONFLICT.value
        assert {r["origin"] for r in name["readings"]} == {"front", "back"}
        assert {r["value"] for r in name["readings"]} == {"RAVI KUMAR", "RAVI KUMARI"}


class TestMergeChecksReachValidation:
    def test_a_conflict_moves_a_valid_result_to_review_not_invalid(self):
        envelope = validation_rules.from_validator_output(
            CASE,
            DocumentType.DRIVING_LICENSE,
            {"rules": [{"metric": "required_name", "status": "PASS", "reason": "ok"}]},
        )
        assert envelope.result["decision"] == "VALID"

        combined = validation_rules.with_extra_checks(
            envelope,
            [
                ValidationCheck(
                    rule_id="field_agreement_name",
                    status=CheckStatus.REVIEW,
                    message="Sources disagree",
                )
            ],
        )

        # A disagreement between two captures is never a forgery finding.
        assert combined.result["decision"] == "REVIEW"
        assert combined.result["summary"]["failed"] == 0

    def test_existing_checks_are_preserved_and_still_counted(self):
        envelope = validation_rules.from_validator_output(
            CASE,
            DocumentType.DRIVING_LICENSE,
            {
                "rules": [
                    {"metric": "required_name", "status": "PASS", "reason": "ok"},
                    {"metric": "not_expired", "status": "FAIL", "reason": "expired"},
                ]
            },
        )
        combined = validation_rules.with_extra_checks(
            envelope,
            [ValidationCheck(rule_id="field_read_address", status=CheckStatus.REVIEW, message="x")],
        )

        summary = combined.result["summary"]
        assert (summary["passed"], summary["failed"], summary["review"]) == (1, 1, 1)
        # A real deterministic failure still stands: an expired document is a
        # fact the document states, and a merge finding must not mask it.
        assert combined.result["decision"] == "INVALID"


class TestRiskFusionReadsReviewCorrectly:
    def _assemble(self, validation_envelope):
        return assemble(
            CASE,
            DocumentType.DRIVING_LICENSE,
            ocr=ocr_extraction.from_extract_response(
                CASE, DocumentType.DRIVING_LICENSE, FRONT, back=BACK
            ).envelope,
            validation=validation_envelope,
            face_verification=face_arcface.from_failure(
                CASE, "FACE_UNAVAILABLE", "No comparison was made."
            ),
            document_forensics=not_available(
                CASE, Module.DOCUMENT_FORENSICS, "FORENSICS_NOT_IMPLEMENTED", "Not implemented."
            ),
        )

    def test_a_review_validation_does_not_score_as_an_invalid_one(self):
        review = self._assemble(
            validation_rules.with_extra_checks(
                validation_rules.from_validator_output(
                    CASE,
                    DocumentType.DRIVING_LICENSE,
                    {"rules": [{"metric": "required_name", "status": "PASS", "reason": "ok"}]},
                ),
                [
                    ValidationCheck(
                        rule_id="field_agreement_name",
                        status=CheckStatus.REVIEW,
                        message="Sources disagree",
                    )
                ],
            )
        )
        invalid = self._assemble(
            validation_rules.from_validator_output(
                CASE,
                DocumentType.DRIVING_LICENSE,
                {"rules": [{"metric": "not_expired", "status": "FAIL", "reason": "expired"}]},
            )
        )

        # Both are inconclusive-or-worse, but a disagreement between captures
        # must not score as heavily as a rule the document actually failed.
        assert review.risk.result["risk_score"] < invalid.risk.result["risk_score"]
        assert review.risk.result["risk_level"] in {"REVIEW", "LOW"}

    def test_an_absent_module_is_never_counted_as_evidence(self):
        case = self._assemble(
            validation_rules.from_validator_output(
                CASE, DocumentType.DRIVING_LICENSE, {"rules": []}
            )
        )
        contributors = {c["source"]: c for c in case.risk.result["contributors"]}

        assert contributors["document_forensics"]["counted"] is False
        assert contributors["document_forensics"]["weight"] is None
        # Nothing examined this document for tampering, so it cannot be cleared.
        assert case.risk.result["risk_level"] != "LOW"


class TestUnsupportedAndExpired:
    def test_an_unsupported_document_type_reports_not_available_not_a_failure(self):
        outcome = ocr_extraction.from_extract_response(
            CASE, DocumentType.TRAVEL_AUTHORIZATION, FRONT, back=BACK
        )
        assert outcome.envelope.status is ModuleStatus.NOT_AVAILABLE
        assert outcome.envelope.result is None
        assert outcome.checks == []

    def test_an_expired_document_is_a_real_failure_and_survives_the_merge(self):
        envelope = validation_rules.from_validator_output(
            CASE,
            DocumentType.DRIVING_LICENSE,
            {
                "rules": [
                    {
                        "metric": "not_expired",
                        "status": "FAIL",
                        "reason": "Document expired on 2023-08-01",
                    }
                ]
            },
        )
        combined = validation_rules.with_extra_checks(
            envelope,
            [ValidationCheck(rule_id="field_read_address", status=CheckStatus.REVIEW, message="x")],
        )

        expired = next(
            c for c in combined.result["checks"] if c["rule_id"] == "not_expired"
        )
        assert expired["status"] == CheckStatus.FAIL.value
        assert combined.result["decision"] == "INVALID"
