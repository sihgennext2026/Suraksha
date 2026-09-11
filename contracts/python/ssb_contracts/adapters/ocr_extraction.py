"""
Adapter: services/extraction extraction service -> canonical contract.

services/extraction is the stronger of the two OCR implementations in the repository
(orientation correction, U-Net segmentation, multilingual PP-OCRv5, structured
field extraction with per-field provenance) and is treated as the active one.
`reference/extraction-experiments` covers a subset of the same ground and is not adapted here.

Two things this adapter is careful about:

services/extraction returns `detection_box` in PIXELS in the corrected image's frame, while
the contract carries normalised coordinates so a consumer can draw a region
without also transporting the image dimensions. If the caller does not supply
those dimensions the box is omitted rather than guessed.

services/extraction deliberately does not parse or validate the MRZ - it returns raw lines
and leaves decoding to the validation module. `checksum_valid` is therefore left
null here, meaning "not evaluated at this stage", which is distinct from false.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core import Envelope, Module, ModuleError, failed, not_available, partial, success
from ..document_types import (
    UNSUPPORTED_DOCUMENT_TYPE,
    DocumentType,
    has_mrz,
    supports,
)
from ..modules import (
    DetectionPayload,
    DocumentSide,
    FieldOrigin,
    FieldReading,
    FieldSource,
    MachineCode,
    MachineCodeType,
    MrzPayload,
    OcrField,
    OcrResult,
    SideEvidence,
    ValidationCheck,
)
from ..services.field_merge import merge_fields

OCR_MODEL_VERSION = "phase1-ppocrv5-unet-1.0.0"


@dataclass
class ExtractionOutcome:
    """
    The extraction envelope plus what merging the two captures revealed.

    The checks travel beside the envelope rather than inside it because they are
    not extraction findings: they are statements about whether two readings of
    one document agree, which belongs with the rule results the officer reads.
    """

    envelope: Envelope
    checks: List[ValidationCheck]
    fields: List[OcrField]


def _machine_codes(body: Dict[str, Any], side: DocumentSide) -> List[MachineCode]:
    """Reads the extraction service's machine_code_result block."""
    block = body.get("machine_code_result") or {}
    codes: List[MachineCode] = []
    for detection in block.get("detections") or []:
        raw_type = (detection.get("code_type") or "").lower()
        if raw_type not in ("qr", "barcode"):
            continue
        codes.append(
            MachineCode(
                side=side,
                code_type=MachineCodeType(raw_type),
                format=detection.get("format"),
                # The extraction service locates and crops codes; it does not
                # decode their payload. None here means "present, not read",
                # which the merge reports as inconclusive rather than as a fault.
                decoded=detection.get("decoded"),
                detection_method=detection.get("detection_method"),
            )
        )
    return codes


def _fields_from_code(code: MachineCode) -> Dict[str, Optional[str]]:
    """
    Fields a decoded machine-readable payload asserts.

    Nothing is parsed here yet: the extraction service returns crops rather than
    payloads, so there is never a decoded string to read. The seam exists so a
    decoder can be added in one place, and returns nothing rather than inventing
    a value from a code it cannot read.
    """
    if not code.decoded:
        return {}
    return {}

_SOURCE_MAP = {
    "mrz": FieldSource.MRZ,
    "label_same_line": FieldSource.LABEL_SAME_LINE,
    "label_next_line": FieldSource.LABEL_NEXT_LINE,
    "standalone_id": FieldSource.STANDALONE_ID,
    "not_found": FieldSource.NOT_FOUND,
}


def _normalise_box(
    box: Optional[Sequence[float]], image_size: Optional[Tuple[int, int]]
) -> Optional[List[float]]:
    """
    the extraction service's `[x1, y1, x2, y2]` in pixels -> contract `[x, y, w, h]` in 0..1.

    Returns None when the image dimensions are unknown; a box in the wrong units
    would be drawn in the wrong place, which is worse than drawing none.
    """
    if not box or len(box) < 4 or not image_size:
        return None
    width, height = image_size
    if width <= 0 or height <= 0:
        return None
    x1, y1, x2, y2 = (float(value) for value in box[:4])
    left, top = min(x1, x2) / width, min(y1, y2) / height
    return [
        max(0.0, min(1.0, left)),
        max(0.0, min(1.0, top)),
        max(0.0, min(1.0, abs(x2 - x1) / width)),
        max(0.0, min(1.0, abs(y2 - y1) / height)),
    ]


def _mean_confidence(lines: List[Dict[str, Any]]) -> Optional[float]:
    scores = [
        float(line["confidence"])
        for line in lines
        if isinstance(line, dict) and line.get("confidence") is not None
    ]
    return round(sum(scores) / len(scores), 4) if scores else None


def from_extract_response(
    case_id: str,
    document_type: DocumentType,
    response: Dict[str, Any],
    *,
    back: Optional[Dict[str, Any]] = None,
    image_size: Optional[Tuple[int, int]] = None,
    model_version: str = OCR_MODEL_VERSION,
) -> "ExtractionOutcome":
    """
    Builds the canonical extraction envelope from one or both captures.

    `response` is the body of `POST /extract`; `back`, when given, is the body
    of `POST /extract-back`. With no back capture the result is exactly what it
    was before two sides existed — every field SINGLE_SOURCE from the front —
    so a single-sided screening is unchanged by this path.

    The merge's own findings come back alongside the envelope rather than inside
    it. Cross-source agreement is a property of assembling one document from two
    captures, which only the assembler can see: the validation service is handed
    a field set and never learns there were two sides.
    """
    supported, reason = supports(Module.OCR, document_type)
    if not supported:
        return ExtractionOutcome(
            envelope=not_available(
                case_id=case_id,
                module=Module.OCR,
                reason_code=UNSUPPORTED_DOCUMENT_TYPE,
                message=reason or "This document type is not supported by extraction.",
                model_version=model_version,
            ),
            checks=[],
            fields=[],
        )

    detected = bool(response.get("detected"))
    detection = DetectionPayload(
        detected=detected,
        confidence=response.get("detection_confidence"),
        box=_normalise_box(response.get("detection_box"), image_size),
        correction_mode=response.get("correction_mode"),
        orientation_corrected=bool(response.get("orientation_corrected")),
    )

    # Every source's reading of every field, keyed by field. A null value is
    # kept: it records that this side was examined and did not yield the field,
    # which is not the same as the side never having been consulted.
    readings: Dict[str, List[FieldReading]] = {}

    def collect(origin: FieldOrigin, body: Dict[str, Any]) -> List[str]:
        structured: Dict[str, Optional[str]] = body.get("structured_fields") or {}
        sources: Dict[str, str] = body.get("structured_fields_sources") or {}
        supplied: List[str] = []
        for key, value in structured.items():
            source = _SOURCE_MAP.get(sources.get(key, "not_found"), FieldSource.NOT_FOUND)
            # An MRZ-decoded value is attributed to the MRZ, not to the side it
            # was photographed on: its authority comes from the checksummed
            # layout, and the merge ranks sources by that authority.
            attributed = FieldOrigin.MRZ if source is FieldSource.MRZ else origin
            readings.setdefault(key, []).append(
                FieldReading(origin=attributed, value=value, source=source)
            )
            if value not in (None, ""):
                supplied.append(key)
        return supplied

    front_keys = collect(FieldOrigin.FRONT, response)
    back_keys = collect(FieldOrigin.BACK, back) if back else []

    machine_codes = _machine_codes(response, DocumentSide.FRONT)
    if back:
        machine_codes.extend(_machine_codes(back, DocumentSide.BACK))
    for code in machine_codes:
        for key, value in _fields_from_code(code).items():
            readings.setdefault(key, []).append(
                FieldReading(origin=FieldOrigin.QR, value=value, source=FieldSource.QR)
            )

    outcome = merge_fields(document_type, readings, machine_codes=machine_codes)
    fields = outcome.fields

    mrz_lines: List[str] = list(response.get("mrz_lines") or [])
    mrz = MrzPayload(
        present=bool(mrz_lines) and has_mrz(document_type),
        format="TD3" if document_type is DocumentType.PASSPORT and mrz_lines else "NONE",
        lines=mrz_lines,
        check_digits=[],
        # Not evaluated at this stage - services/extraction does no MRZ decoding by design.
        # Distinct from False, which would assert the checksum had been tested
        # and had failed.
        checksum_valid=None,
        confidence=_mean_confidence(response.get("mrz_line_details") or []),
    )

    sides = [
        SideEvidence(
            side=DocumentSide.FRONT,
            detection=detection,
            language=response.get("detected_lang_family"),
            field_keys=sorted(front_keys),
        )
    ]
    if back:
        sides.append(
            SideEvidence(
                side=DocumentSide.BACK,
                detection=DetectionPayload(
                    detected=bool(back.get("detected")),
                    confidence=back.get("detection_confidence"),
                    box=_normalise_box(back.get("detection_box"), image_size),
                    correction_mode=back.get("correction_mode"),
                    orientation_corrected=bool(back.get("orientation_corrected")),
                ),
                language=back.get("detected_lang_family"),
                field_keys=sorted(back_keys),
            )
        )

    result = OcrResult(
        document_type=document_type,
        fields=fields,
        mrz=mrz,
        detection=detection,
        overall_confidence=_mean_confidence(response.get("field_lines") or []),
        language=response.get("detected_lang_family"),
        sides=sides,
        machine_codes=machine_codes,
    )

    if not detected:
        # A usable but incomplete result: OCR may still have read something, but
        # every downstream check inherits the uncertainty of an unlocated
        # document, so the officer is told rather than left to infer it.
        envelope = partial(
            case_id=case_id,
            module=Module.OCR,
            model_version=model_version,
            result=result.to_dict(),
            errors=[
                ModuleError(
                    code="DOCUMENT_NOT_LOCATED",
                    message=(
                        response.get("message")
                        or "The document could not be located within the captured frame."
                    ),
                    retryable=True,
                )
            ],
        )
        return ExtractionOutcome(envelope=envelope, checks=outcome.checks, fields=fields)

    return ExtractionOutcome(
        envelope=success(
            case_id=case_id,
            module=Module.OCR,
            model_version=model_version,
            result=result.to_dict(),
        ),
        checks=outcome.checks,
        fields=fields,
    )


def from_failure(
    case_id: str,
    code: str,
    message: str,
    *,
    retryable: bool = True,
    model_version: str = OCR_MODEL_VERSION,
) -> Envelope:
    return failed(
        case_id=case_id,
        module=Module.OCR,
        model_version=model_version,
        errors=[ModuleError(code=code, message=message, retryable=retryable)],
    )
