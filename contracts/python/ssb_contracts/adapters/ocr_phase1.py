"""
Adapter: Phase_1 extraction service -> canonical contract.

Phase_1 is the stronger of the two OCR implementations in the repository
(orientation correction, U-Net segmentation, multilingual PP-OCRv5, structured
field extraction with per-field provenance) and is treated as the active one.
`backend/extraction` covers a subset of the same ground and is not adapted here.

Two things this adapter is careful about:

Phase_1 returns `detection_box` in PIXELS in the corrected image's frame, while
the contract carries normalised coordinates so a consumer can draw a region
without also transporting the image dimensions. If the caller does not supply
those dimensions the box is omitted rather than guessed.

Phase_1 deliberately does not parse or validate the MRZ - it returns raw lines
and leaves decoding to the validation module. `checksum_valid` is therefore left
null here, meaning "not evaluated at this stage", which is distinct from false.
"""

from __future__ import annotations

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
    FieldSource,
    MrzPayload,
    OcrField,
    OcrResult,
)

OCR_MODEL_VERSION = "phase1-ppocrv5-unet-1.0.0"

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
    Phase_1's `[x1, y1, x2, y2]` in pixels -> contract `[x, y, w, h]` in 0..1.

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
    image_size: Optional[Tuple[int, int]] = None,
    model_version: str = OCR_MODEL_VERSION,
) -> Envelope:
    """`response` is the JSON body of Phase_1's `POST /extract`."""
    supported, reason = supports(Module.OCR, document_type)
    if not supported:
        return not_available(
            case_id=case_id,
            module=Module.OCR,
            reason_code=UNSUPPORTED_DOCUMENT_TYPE,
            message=reason or "This document type is not supported by extraction.",
            model_version=model_version,
        )

    detected = bool(response.get("detected"))
    detection = DetectionPayload(
        detected=detected,
        confidence=response.get("detection_confidence"),
        box=_normalise_box(response.get("detection_box"), image_size),
        correction_mode=response.get("correction_mode"),
        orientation_corrected=bool(response.get("orientation_corrected")),
    )

    structured: Dict[str, Optional[str]] = response.get("structured_fields") or {}
    sources: Dict[str, str] = response.get("structured_fields_sources") or {}
    fields = [
        OcrField(
            key=key,
            # Phase_1 leaves a field null when it is absent from this document
            # type or could not be found. That null is carried through rather
            # than being replaced with an empty string.
            value=value,
            source=_SOURCE_MAP.get(sources.get(key, "not_found"), FieldSource.NOT_FOUND),
        )
        for key, value in structured.items()
    ]

    mrz_lines: List[str] = list(response.get("mrz_lines") or [])
    mrz = MrzPayload(
        present=bool(mrz_lines) and has_mrz(document_type),
        format="TD3" if document_type is DocumentType.PASSPORT and mrz_lines else "NONE",
        lines=mrz_lines,
        check_digits=[],
        # Not evaluated at this stage - Phase_1 does no MRZ decoding by design.
        # Distinct from False, which would assert the checksum had been tested
        # and had failed.
        checksum_valid=None,
        confidence=_mean_confidence(response.get("mrz_line_details") or []),
    )

    result = OcrResult(
        document_type=document_type,
        fields=fields,
        mrz=mrz,
        detection=detection,
        overall_confidence=_mean_confidence(response.get("field_lines") or []),
        language=response.get("detected_lang_family"),
    )

    if not detected:
        # A usable but incomplete result: OCR may still have read something, but
        # every downstream check inherits the uncertainty of an unlocated
        # document, so the officer is told rather than left to infer it.
        return partial(
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

    return success(
        case_id=case_id,
        module=Module.OCR,
        model_version=model_version,
        result=result.to_dict(),
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
