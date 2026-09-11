"""
The front/back merge policy.

Each test names the rule it pins. The through-line is rule 6: nothing in this
module may produce FAIL. A document is not forged because a camera could not
read one side of it, and an officer trained to ignore a routine finding will
ignore the one that matters.
"""

import pytest

from ssb_contracts.document_types import DocumentType
from ssb_contracts.modules import (
    CheckStatus,
    DocumentSide,
    FieldAgreement,
    FieldOrigin,
    FieldReading,
    FieldSource,
    MachineCode,
    MachineCodeType,
)
from ssb_contracts.services.field_merge import merge_fields, readings_from, schema_for


def readings(*sides):
    """Collects `(origin, {field: value})` pairs into the merge's input shape."""
    collected = {}
    for origin, values in sides:
        for key, reading in readings_from(origin, values).items():
            collected.setdefault(key, []).append(reading)
    return collected


def field(outcome, key):
    return next((f for f in outcome.fields if f.key == key), None)


def check(outcome, rule_id):
    return next((c for c in outcome.checks if c.rule_id == rule_id), None)


class TestRule1Agreement:
    def test_sides_that_agree_are_accepted_and_marked(self):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings(
                (FieldOrigin.FRONT, {"document_number": "DL-0120"}),
                (FieldOrigin.BACK, {"document_number": "DL-0120"}),
            ),
        )

        entry = field(outcome, "document_number")
        assert entry.value == "DL-0120"
        assert entry.agreement is FieldAgreement.AGREED
        assert outcome.checks == []

    def test_agreement_ignores_case_and_spacing_but_not_content(self):
        # Two readings of one printed string differ in whitespace and case for
        # reasons that are not disagreements.
        agreeing = merge_fields(
            DocumentType.NATIONAL_ID,
            readings(
                (FieldOrigin.FRONT, {"name": "Ravi  Kumar"}),
                (FieldOrigin.BACK, {"name": "RAVI KUMAR"}),
            ),
        )
        assert field(agreeing, "name").agreement is FieldAgreement.AGREED

        differing = merge_fields(
            DocumentType.NATIONAL_ID,
            readings(
                (FieldOrigin.FRONT, {"name": "RAVI KUMAR"}),
                (FieldOrigin.BACK, {"name": "RAVI KUMARI"}),
            ),
        )
        assert field(differing, "name").agreement is FieldAgreement.CONFLICT


class TestRule2Disagreement:
    def test_a_disagreement_is_review_and_never_a_failure(self):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings(
                (FieldOrigin.FRONT, {"name": "RAVI KUMAR"}),
                (FieldOrigin.BACK, {"name": "RAVI KUMAF"}),
            ),
        )

        raised = check(outcome, "field_agreement_name")
        assert raised.status is CheckStatus.REVIEW
        assert all(c.status is not CheckStatus.FAIL for c in outcome.checks)

    def test_both_readings_are_preserved_for_the_officer(self):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings(
                (FieldOrigin.FRONT, {"name": "RAVI KUMAR"}),
                (FieldOrigin.BACK, {"name": "RAVI KUMAF"}),
            ),
        )

        entry = field(outcome, "name")
        # A disagreement shown as a single winning value would hide the very
        # thing the officer is being asked to settle.
        assert {r.value for r in entry.readings} == {"RAVI KUMAR", "RAVI KUMAF"}
        assert {r.origin for r in entry.readings} == {FieldOrigin.FRONT, FieldOrigin.BACK}

    def test_the_more_authoritative_source_is_the_one_displayed(self):
        outcome = merge_fields(
            DocumentType.PASSPORT,
            {
                "document_number": [
                    FieldReading(FieldOrigin.FRONT, "X1100034", FieldSource.LABEL_SAME_LINE),
                    FieldReading(FieldOrigin.MRZ, "X11000344", FieldSource.MRZ),
                ]
            },
        )

        entry = field(outcome, "document_number")
        # The MRZ is a checksummed fixed layout; a label match is a heuristic.
        assert entry.origin is FieldOrigin.MRZ
        assert entry.value == "X11000344"
        assert entry.agreement is FieldAgreement.CONFLICT


class TestRule3BackOnlyFields:
    def test_a_field_only_the_back_carries_is_accepted(self):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings(
                (FieldOrigin.FRONT, {"address": None}),
                (FieldOrigin.BACK, {"address": "12 Main Street"}),
            ),
        )

        entry = field(outcome, "address")
        assert entry.value == "12 Main Street"
        assert entry.origin is FieldOrigin.BACK
        assert entry.agreement is FieldAgreement.SINGLE_SOURCE
        # Accepted without penalty: this is where a licence prints its address.
        assert outcome.checks == []


class TestRule4UnreadableFields:
    def test_a_field_neither_side_read_is_review_when_the_type_expects_it(self):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings(
                (FieldOrigin.FRONT, {"address": None}),
                (FieldOrigin.BACK, {"address": None}),
            ),
        )

        assert field(outcome, "address") is None
        raised = check(outcome, "field_read_address")
        assert raised.status is CheckStatus.REVIEW

    def test_a_field_the_type_never_carries_raises_nothing(self):
        # A passport has no address to fail to read.
        outcome = merge_fields(
            DocumentType.PASSPORT,
            readings((FieldOrigin.FRONT, {"address": None})),
        )
        assert outcome.checks == []


class TestRule5MachineCodeConflicts:
    def test_a_code_disagreeing_with_the_text_is_review(self):
        outcome = merge_fields(
            DocumentType.NATIONAL_ID,
            {
                "document_number": [
                    FieldReading(FieldOrigin.FRONT, "1234 5678", FieldSource.LABEL_SAME_LINE),
                    FieldReading(FieldOrigin.QR, "1234 5679", FieldSource.QR),
                ]
            },
        )

        entry = field(outcome, "document_number")
        assert entry.agreement is FieldAgreement.CONFLICT
        # A signed payload outranks recognised text, but the officer is still told.
        assert entry.origin is FieldOrigin.QR
        assert check(outcome, "field_agreement_document_number").status is CheckStatus.REVIEW

    def test_a_code_that_will_not_decode_is_review_not_a_failure(self):
        outcome = merge_fields(
            DocumentType.NATIONAL_ID,
            {},
            machine_codes=[
                MachineCode(
                    side=DocumentSide.BACK, code_type=MachineCodeType.QR, decoded=None
                )
            ],
        )

        raised = check(outcome, "machine_code_back_qr")
        assert raised.status is CheckStatus.REVIEW

    def test_a_decoded_code_raises_nothing(self):
        outcome = merge_fields(
            DocumentType.NATIONAL_ID,
            {},
            machine_codes=[
                MachineCode(
                    side=DocumentSide.BACK, code_type=MachineCodeType.QR, decoded="payload"
                )
            ],
        )
        assert outcome.checks == []


class TestRule6NothingEverFails:
    @pytest.mark.parametrize(
        "case",
        [
            {"front": {"name": "A"}, "back": {"name": "B"}},
            {"front": {"name": None}, "back": {"name": None}},
            {"front": {"address": None}, "back": {}},
            {"front": {}, "back": {}},
        ],
    )
    def test_no_combination_of_missing_or_conflicting_evidence_produces_fail(self, case):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings(
                (FieldOrigin.FRONT, case["front"]),
                (FieldOrigin.BACK, case["back"]),
            ),
        )
        assert all(c.status is not CheckStatus.FAIL for c in outcome.checks)


class TestRule7Provenance:
    def test_every_field_records_where_it_came_from(self):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings(
                (FieldOrigin.FRONT, {"name": "RAVI KUMAR"}),
                (FieldOrigin.BACK, {"address": "12 Main Street"}),
            ),
        )

        assert field(outcome, "name").origin is FieldOrigin.FRONT
        assert field(outcome, "address").origin is FieldOrigin.BACK

    def test_a_single_source_field_carries_no_redundant_readings(self):
        outcome = merge_fields(
            DocumentType.DRIVING_LICENSE,
            readings((FieldOrigin.FRONT, {"name": "RAVI KUMAR"})),
        )
        # Nothing to compare, so nothing to echo back.
        assert field(outcome, "name").readings == []


class TestPerTypeSchemas:
    def test_a_type_can_declare_its_own_back_fields(self):
        assert "address" in schema_for(DocumentType.DRIVING_LICENSE).back
        assert "address" in schema_for(DocumentType.NATIONAL_ID).back_only

    def test_an_undeclared_type_expects_nothing_of_a_back(self):
        # The safe default: a type with no layout declared is treated as
        # front-only, so no absence on its reverse is ever raised.
        assert schema_for(DocumentType.OTHER).back == frozenset()
        assert schema_for(DocumentType.OTHER).expects("address") is False
