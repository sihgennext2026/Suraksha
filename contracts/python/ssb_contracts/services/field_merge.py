"""
Merges the readings from a document's two sides into one field set.

A document photographed twice produces two partial views of the same facts. The
front of a licence carries the holder and the dates; the back carries the
address and, increasingly, a signed machine-readable code. Some fields appear on
both. This module decides what the case document says when they do.

The policy, in full:

1. Both sides supply a field and the values agree      -> accepted, AGREED
2. Both sides supply it and the values disagree        -> accepted from the more
                                                          authoritative source,
                                                          marked CONFLICT, and a
                                                          REVIEW check is raised
3. Only the back supplies it                           -> accepted as back
                                                          evidence, no penalty
4. A field could not be read from either side          -> absent; a REVIEW check
                                                          is raised only if the
                                                          type expects it there
5. A machine-readable code disagrees with the text     -> same as (2): REVIEW
6. Anything missing or unreadable                      -> never FAIL

A disagreement between two captures of one document is not evidence of forgery.
Glare, a fold, a truncated label or a single OCR substitution all produce it, and
the officer is holding the document and can settle it in seconds. Turning that
into a fraud finding would train officers to ignore the finding that matters.

Rule 7 — provenance — is carried on every field rather than computed here: each
`OcrField` records the origin it was accepted from and keeps every reading.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Dict, List, Optional, Sequence, Tuple

from ..document_types import DocumentType
from ..modules import (
    CheckStatus,
    FieldAgreement,
    FieldOrigin,
    FieldReading,
    FieldSource,
    MachineCode,
    OcrField,
    ValidationCheck,
)

#: Ordered most authoritative first.
#:
#: A machine-readable zone and a QR payload are checksummed or signed fixed
#: layouts; a label match is a heuristic over recognised text. When two sources
#: disagree the more authoritative value is the one shown, but the disagreement
#: is still surfaced — precedence decides what is displayed, never whether the
#: officer is told.
ORIGIN_PRECEDENCE: Tuple[FieldOrigin, ...] = (
    FieldOrigin.MRZ,
    FieldOrigin.QR,
    FieldOrigin.FRONT,
    FieldOrigin.BACK,
)


@dataclass(frozen=True)
class SideSchema:
    """
    Which fields a document type carries on which side.

    Declared per type so a new document can describe its own layout without
    touching the merge itself. `back_only` matters for rule 4: a field the back
    is expected to carry, which neither side produced, is worth telling the
    officer about; a field no side was ever going to carry is not.
    """

    front: frozenset = dataclass_field(default_factory=frozenset)
    back: frozenset = dataclass_field(default_factory=frozenset)

    @property
    def back_only(self) -> frozenset:
        return self.back - self.front

    def expects(self, key: str) -> bool:
        return key in self.front or key in self.back


#: Per-type layouts. A type with no entry is treated as front-only, which is the
#: safe default: nothing is expected of a back that was never specified, so no
#: REVIEW is raised for its absence.
SIDE_SCHEMAS: Dict[DocumentType, SideSchema] = {
    DocumentType.PASSPORT: SideSchema(
        front=frozenset(
            {
                "name",
                "surname",
                "given_name",
                "date_of_birth",
                "sex",
                "document_number",
                "nationality",
                "issue_date",
                "expiry_date",
                "issuing_authority",
            }
        ),
        # A passport's observation pages carry no structured fields this
        # pipeline reads, so a back capture is accepted but expected of nothing.
        back=frozenset(),
    ),
    DocumentType.VISA: SideSchema(
        front=frozenset(
            {
                "name",
                "surname",
                "given_name",
                "date_of_birth",
                "passport_number",
                "visa_number",
                "nationality",
                "issue_date",
                "expiry_date",
            }
        ),
        back=frozenset(),
    ),
    DocumentType.DRIVING_LICENSE: SideSchema(
        front=frozenset(
            {
                "name",
                "name_native",
                "father_name",
                "date_of_birth",
                "sex",
                "document_number",
                "issue_date",
                "expiry_date",
            }
        ),
        # The reverse of a licence is where the address and the vehicle
        # categories are printed, and where the signed code usually sits.
        back=frozenset({"address", "categories", "document_number"}),
    ),
    DocumentType.NATIONAL_ID: SideSchema(
        front=frozenset(
            {
                "name",
                "name_native",
                "date_of_birth",
                "sex",
                "document_number",
                "nationality",
            }
        ),
        back=frozenset({"address", "father_name", "document_number"}),
    ),
    DocumentType.PERMIT: SideSchema(
        front=frozenset(
            {
                "name",
                "father_name",
                "date_of_birth",
                "document_number",
                "issue_date",
                "expiry_date",
                "issuing_authority",
            }
        ),
        back=frozenset({"address", "issuing_authority"}),
    ),
}


def schema_for(document_type: DocumentType) -> SideSchema:
    return SIDE_SCHEMAS.get(document_type, SideSchema())


def _normalise(value: Optional[str]) -> str:
    """
    Comparison form for two readings of the same printed value.

    Case, surrounding whitespace and the separators that OCR moves around are
    not disagreements. Anything beyond that is left alone: normalising harder —
    stripping punctuation inside a value, say — would quietly reconcile readings
    that genuinely differ.
    """
    if value is None:
        return ""
    collapsed = " ".join(str(value).split())
    return collapsed.replace(",", " ").replace("  ", " ").strip().upper()


def _rank(origin: FieldOrigin) -> int:
    try:
        return ORIGIN_PRECEDENCE.index(origin)
    except ValueError:
        return len(ORIGIN_PRECEDENCE)


@dataclass
class MergeOutcome:
    """The merged fields, and the checks the merge itself raised."""

    fields: List[OcrField]
    checks: List[ValidationCheck]


def merge_fields(
    document_type: DocumentType,
    readings_by_key: Dict[str, Sequence[FieldReading]],
    *,
    machine_codes: Sequence[MachineCode] = (),
) -> MergeOutcome:
    """
    Applies the policy above and returns the canonical field list.

    `readings_by_key` holds every source's reading for each field, including
    ones that found nothing — a reading with a null value records that a source
    looked and did not find it, which is different from that source never having
    been consulted.
    """
    schema = schema_for(document_type)
    merged: List[OcrField] = []
    checks: List[ValidationCheck] = []

    for key in sorted(readings_by_key):
        readings = [r for r in readings_by_key[key]]
        found = [r for r in readings if r.value not in (None, "")]

        if not found:
            # Rule 4 and 6. Absence is reported only where the document type
            # says the field should have been there, and never as a failure.
            if schema.expects(key):
                checks.append(
                    ValidationCheck(
                        rule_id=f"field_read_{key}",
                        status=CheckStatus.REVIEW,
                        message=(
                            f"'{key}' could not be read from either side. "
                            f"Confirm it against the document."
                        ),
                        expectation="Each expected field is read from at least one capture",
                        fields=[key],
                    )
                )
            continue

        found.sort(key=lambda r: _rank(r.origin))
        accepted = found[0]
        distinct = {_normalise(r.value) for r in found}

        if len(found) == 1:
            agreement = FieldAgreement.SINGLE_SOURCE
        elif len(distinct) == 1:
            agreement = FieldAgreement.AGREED
        else:
            agreement = FieldAgreement.CONFLICT

        if agreement is FieldAgreement.CONFLICT:
            # Rules 2 and 5. A machine-readable code disagreeing with printed
            # text lands here too — it is the same situation with a more
            # authoritative source on one side.
            detail = "; ".join(
                f"{r.origin.value}: {r.value}" for r in found if r.value not in (None, "")
            )
            checks.append(
                ValidationCheck(
                    rule_id=f"field_agreement_{key}",
                    status=CheckStatus.REVIEW,
                    message=(
                        f"'{key}' differs between sources ({detail}). "
                        f"Confirm which is correct against the document."
                    ),
                    observed=detail,
                    expectation="Sources that both read a field report the same value",
                    fields=[key],
                )
            )

        merged.append(
            OcrField(
                key=key,
                value=accepted.value,
                source=accepted.source,
                confidence=accepted.confidence,
                origin=accepted.origin,
                agreement=agreement,
                # Rule 7. Kept only where there was something to compare, so a
                # single-sided capture carries no redundant echo of itself.
                readings=list(found) if len(found) > 1 else [],
            )
        )

    checks.extend(_unreadable_code_checks(machine_codes))
    return MergeOutcome(fields=merged, checks=checks)


def _unreadable_code_checks(machine_codes: Sequence[MachineCode]) -> List[ValidationCheck]:
    """
    A code that was found but not decoded is inconclusive, never a failure.

    It is worth saying, because a licence whose signed code will not read is
    something the officer may want to look at — but an unreadable code is just
    as likely to be a smudged print or a bad angle as anything else.
    """
    checks: List[ValidationCheck] = []
    for code in machine_codes:
        if code.decoded in (None, ""):
            checks.append(
                ValidationCheck(
                    rule_id=f"machine_code_{code.side.value}_{code.code_type.value}",
                    status=CheckStatus.REVIEW,
                    message=(
                        f"A {code.code_type.value} on the {code.side.value} was detected but "
                        f"could not be decoded."
                    ),
                    expectation="A detected machine-readable code decodes to a payload",
                )
            )
    return checks


def readings_from(
    origin: FieldOrigin,
    fields: Dict[str, Optional[str]],
    sources: Optional[Dict[str, str]] = None,
) -> Dict[str, FieldReading]:
    """
    Adapts one extraction response's `{key: value}` map into readings.

    Keys whose value is null are kept: they record that this side was examined
    for the field and did not yield it.
    """
    sources = sources or {}
    result: Dict[str, FieldReading] = {}
    for key, value in (fields or {}).items():
        raw_source = sources.get(key, "")
        try:
            source = FieldSource(raw_source)
        except ValueError:
            source = FieldSource.NOT_FOUND if value in (None, "") else FieldSource.LABEL_SAME_LINE
        result[key] = FieldReading(origin=origin, value=value, source=source)
    return result
