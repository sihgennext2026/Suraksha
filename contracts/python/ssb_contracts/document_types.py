"""
Canonical document type, and which modules can actually process each one.

Before this file the four components disagreed: the React Native app used
`DRIVING_LICENCE` and offered seven types, Phase_1's OCR enum offered five with
`DRIVING_LICENSE`, and backend/validation shipped rule files for the same five.
The canonical spelling follows the Python services, because they are the ones
with rule files and model behaviour keyed to it.

The two extra types the officer-facing application offers -
`travel_authorization` and `other` - are kept rather than deleted: an officer at
a post genuinely meets documents outside the five, and removing the option would
push them into declaring the wrong type, which is worse. Instead the capability
matrix below says plainly that no backend module supports them, and every module
returns NOT_AVAILABLE for those types rather than falling back to another type's
rules.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Tuple

from .core import Module


class DocumentType(str, Enum):
    PASSPORT = "passport"
    VISA = "visa"
    DRIVING_LICENSE = "driving_license"
    NATIONAL_ID = "national_id"
    PERMIT = "permit"
    TRAVEL_AUTHORIZATION = "travel_authorization"
    OTHER = "other"


#: Types the OCR service (Phase_1) has a field schema and language mapping for.
OCR_SUPPORTED = frozenset(
    {
        DocumentType.PASSPORT,
        DocumentType.VISA,
        DocumentType.DRIVING_LICENSE,
        DocumentType.NATIONAL_ID,
        DocumentType.PERMIT,
    }
)

#: Types that carry an ICAO 9303 machine-readable zone. Phase_1 documents this
#: explicitly: an MRZ band must not be cropped from any other type.
MRZ_BEARING = frozenset({DocumentType.PASSPORT, DocumentType.VISA})

#: Types backend/validation ships a rules file for (app/rules/*.json).
VALIDATION_SUPPORTED = frozenset(
    {
        DocumentType.PASSPORT,
        DocumentType.VISA,
        DocumentType.DRIVING_LICENSE,
        DocumentType.NATIONAL_ID,
        DocumentType.PERMIT,
    }
)

UNSUPPORTED_DOCUMENT_TYPE = "UNSUPPORTED_DOCUMENT_TYPE"


def supports(module: Module, document_type: DocumentType) -> Tuple[bool, Optional[str]]:
    """
    Whether `module` can process `document_type`, and if not, why.

    Face verification and document forensics work on imagery rather than on a
    document layout, so they are type-independent. Anomaly detection is not
    implemented for any type.
    """
    if module is Module.OCR:
        if document_type in OCR_SUPPORTED:
            return True, None
        return False, (
            f"The extraction service has no field schema for "
            f"{label(document_type).lower()}. No fields were read."
        )

    if module is Module.VALIDATION:
        if document_type in VALIDATION_SUPPORTED:
            return True, None
        return False, (
            f"No validation rule set exists for {label(document_type).lower()}. "
            "Rules from another document type are deliberately not substituted."
        )

    if module is Module.ANOMALY:
        return False, "Anomaly detection (PatchCore) is not implemented."

    # Face verification and document forensics operate on imagery.
    return True, None


LABELS: Dict[DocumentType, str] = {
    DocumentType.PASSPORT: "Passport",
    DocumentType.VISA: "Visa",
    DocumentType.DRIVING_LICENSE: "Driving licence",
    DocumentType.NATIONAL_ID: "National identity card",
    DocumentType.PERMIT: "Permit",
    DocumentType.TRAVEL_AUTHORIZATION: "Travel authorisation",
    DocumentType.OTHER: "Other document",
}


def label(document_type: DocumentType) -> str:
    return LABELS[document_type]


def has_mrz(document_type: DocumentType) -> bool:
    return document_type in MRZ_BEARING


def parse(value: str) -> DocumentType:
    """
    Reads a wire value, tolerating the spellings already in the codebase.

    `driving_licence` is accepted because the React Native application used it
    before this contract existed and stored cases still carry it.
    """
    normalised = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "driving_licence": DocumentType.DRIVING_LICENSE,
        "drivinglicense": DocumentType.DRIVING_LICENSE,
        "nationalid": DocumentType.NATIONAL_ID,
        "travel_authorisation": DocumentType.TRAVEL_AUTHORIZATION,
    }
    if normalised in aliases:
        return aliases[normalised]
    return DocumentType(normalised)
