"""
Runs the real screening modules and assembles the canonical case document.

What this file is allowed to do is deliberately narrow. It sequences the
existing pipelines, hands each one's output to the adapter that already knows
how to express it as an `Envelope`, and calls `ssb_contracts.assemble` to fuse
them. It decides nothing about what a similarity means, whether a rule failure
matters, or how a missing module affects the assessment — that policy lives in
the contract package and must stay in one place.

Two modules are absent by design and stay that way:

  * Document forensics. DINOv2 is not implemented — no model, no weights, no
    training data. The mock in `ssb_contracts.services.forensics_mock` is left
    untouched and is NOT used here: replaying invented tamper findings against a
    real capture would put fabricated evidence in front of an officer.
  * Anomaly detection. PatchCore was never built.

Both are reported NOT_AVAILABLE, which the fusion engine treats as an absence of
evidence rather than a finding, so neither can quietly become a pass.
"""

from __future__ import annotations

import io
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import loader

log = logging.getLogger(__name__)

#: Reported when tamper detection is asked for. Kept distinct from a failure:
#: the module did not run because it does not exist, which is not the same as a
#: module that ran and could not finish.
FORENSICS_NOT_IMPLEMENTED = (
    "FORENSICS_NOT_IMPLEMENTED",
    "Tamper detection (DINOv2) is not implemented. This document has not been "
    "examined for tampering.",
)


@dataclass
class OcrOutcome:
    """
    The extraction envelope, plus the raw Phase_1 body it came from.

    Validation needs the extracted text, and the envelope deliberately does not
    carry it — the canonical `OcrResult` is a curated view, not a transport for
    upstream internals. Rather than widen the contract to suit one consumer, the
    raw body is passed alongside it and never leaves this process.
    """

    envelope: Any
    raw: Optional[Dict[str, Any]]


@dataclass
class ModuleAvailability:
    """Why a pipeline is or is not usable, for `GET /health`."""

    ocr: Optional[str] = None
    validation: Optional[str] = None
    face: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        def entry(reason: Optional[str]) -> Dict[str, Any]:
            return {"available": reason is None, "reason": reason}

        return {
            "ocr": entry(self.ocr),
            "validation": entry(self.validation),
            "face_verification": entry(self.face),
            "document_forensics": {
                "available": False,
                "reason": FORENSICS_NOT_IMPLEMENTED[1],
            },
            "anomaly": {
                "available": False,
                "reason": "Anomaly detection (PatchCore) is not implemented.",
            },
        }


#: Phase_1's field names, translated to the vocabulary the rule sets use.
#:
#: The two modules were written independently and name the same things
#: differently — Phase_1 calls a passport's number `document_number`, the
#: passport rule set calls it `passport_number`. Something has to translate, and
#: a rename table is the honest form for it: every entry is a synonym, none
#: derives, combines or reinterprets a value.
#:
#: The document-number field is per-type because the rule sets give it a
#: different name in each, which is why this cannot be one flat mapping.
_COMMON_FIELD_NAMES: Dict[str, str] = {
    "name": "name",
    "date_of_birth": "date_of_birth",
    "nationality": "nationality",
    "issue_date": "date_of_issue",
    "expiry_date": "date_of_expiry",
    "issuing_authority": "issuing_authority",
    "address": "address",
}

_DOCUMENT_NUMBER_NAMES: Dict[str, str] = {
    "passport": "passport_number",
    "visa": "visa_number",
    "driving_license": "license_number",
    "national_id": "national_id_number",
    "permit": "permit_number",
}

#: Names that differ only for one document type.
_PER_TYPE_FIELD_NAMES: Dict[str, Dict[str, str]] = {
    "passport": {"sex": "sex"},
    "national_id": {"sex": "gender"},
    "driving_license": {"father_name": "parent_name"},
}


def _validation_fields(document_type_value: str, response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates Phase_1's extracted fields into the rule sets' vocabulary.

    Phase_1 has already done extraction — MRZ decoding for passports and visas,
    label matching over the OCR lines otherwise — and its `structured_fields` is
    that result. Handing the raw lines to the validation service's own extractor
    instead would run a second, weaker extraction over the same evidence and
    discard what the MRZ already established, which is how a passport whose name
    and dates were read correctly still came out as six missing required fields.

    A field neither source found stays absent rather than being guessed, so the
    rules report it missing — which is the truth about the document.
    """
    structured = response.get("structured_fields") or {}
    fields: Dict[str, Any] = {}

    for source, target in _COMMON_FIELD_NAMES.items():
        value = structured.get(source)
        if value:
            fields[target] = value

    for source, target in _PER_TYPE_FIELD_NAMES.get(document_type_value, {}).items():
        value = structured.get(source)
        if value:
            fields[target] = value

    number = structured.get("document_number")
    target = _DOCUMENT_NUMBER_NAMES.get(document_type_value)
    if number and target:
        fields[target] = number

    # A visa carries both its own number and the passport it is affixed to.
    passport_number = structured.get("passport_number")
    if passport_number:
        fields["passport_number"] = passport_number

    return fields


def _validation_mrz(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    The MRZ block the consistency rule reads, or None when there is no MRZ.

    None is meaningful here: the rule reports `mrz_present: REVIEW` for a
    document that should have had one, and a document type that never has one
    is not penalised for its absence.
    """
    lines = [line for line in (response.get("mrz_lines") or []) if line]
    if not lines:
        return None

    structured = response.get("structured_fields") or {}
    sources = response.get("structured_fields_sources") or {}

    # Only fields the MRZ itself produced belong here. Including a label-matched
    # value would make the consistency check compare the visible text with
    # itself and always agree.
    mrz: Dict[str, Any] = {"raw_lines": lines}
    for source, target in (
        ("name", "name"),
        ("document_number", "passport_number"),
        ("date_of_birth", "date_of_birth"),
        ("expiry_date", "date_of_expiry"),
    ):
        if sources.get(source) == "mrz" and structured.get(source):
            mrz[target] = structured[source]
    return mrz


class ScreeningPipeline:
    """
    Holds the loaded models for the life of the process.

    Every pipeline here loads ONNX or Paddle weights, which takes seconds. They
    are constructed once at startup and reused; a per-request construction would
    make every screening pay that cost.
    """

    def __init__(self) -> None:
        self.contracts = loader.load_contracts()
        from ssb_contracts import adapters  # noqa: WPS433 - needs the path set above

        self.adapters = adapters
        self.availability = ModuleAvailability()

        self._phase1 = None
        self._phase1_lifespan = None
        self._extractors = None
        self._validator_module = None
        self._rules_dir: Optional[Path] = None
        self._face = None

    # -- startup ---------------------------------------------------------

    async def start(self) -> None:
        """
        Loads each pipeline independently.

        One module failing to load must not take the service down: the contract
        can express "this module produced nothing", so a missing pipeline
        degrades that module to NOT_AVAILABLE and the rest of the screening
        still runs.
        """
        try:
            self._phase1 = loader.load_phase1()
            # Phase_1 loads its models in a FastAPI lifespan hook rather than at
            # import, so entering that context is what makes /extract usable.
            self._phase1_lifespan = self._phase1.lifespan(self._phase1.app)
            await self._phase1_lifespan.__aenter__()
            log.info("Extraction pipeline ready (Phase_1)")
        except Exception as error:
            self._phase1 = None
            self.availability.ocr = f"{type(error).__name__}: {error}"
            log.warning("Extraction pipeline unavailable: %s", error)

        try:
            self._extractors, self._validator_module, self._rules_dir = loader.load_validation()
            log.info("Validation rules ready")
        except Exception as error:
            self._extractors = None
            self.availability.validation = f"{type(error).__name__}: {error}"
            log.warning("Validation unavailable: %s", error)

        try:
            faceverify = loader.load_faceverify()
            self._face = faceverify.FaceVerificationPipeline()
            log.info("Face verification ready (SCRFD + ArcFace R50)")
        except Exception as error:
            self._face = None
            self.availability.face = f"{type(error).__name__}: {error}"
            log.warning("Face verification unavailable: %s", error)

    async def stop(self) -> None:
        if self._phase1_lifespan is not None:
            try:
                await self._phase1_lifespan.__aexit__(None, None, None)
            except Exception:  # pragma: no cover - shutdown best effort
                log.warning("Phase_1 shutdown did not complete cleanly")
            self._phase1_lifespan = None

    # -- modules ---------------------------------------------------------

    async def _run_ocr(self, case_id: str, document_type: Any, image: bytes) -> "OcrOutcome":
        """Phase_1: orientation, U-Net detection, perspective warp, PP-OCRv5, MRZ/QR."""
        adapter = self.adapters.ocr_phase1

        if self._phase1 is None:
            return OcrOutcome(
                adapter.from_failure(
                    case_id=case_id,
                    code="EXTRACTION_UNAVAILABLE",
                    message="The extraction service is not running. No fields were read.",
                ),
                None,
            )

        # An unsupported type never reaches the model: the adapter answers from
        # the contract's own support table, so the reason the officer sees is the
        # contract's, not a guess made here.
        supported, _ = self.contracts.supports(self.contracts.Module.OCR, document_type)
        if not supported:
            return OcrOutcome(adapter.from_extract_response(case_id, document_type, {}), None)

        try:
            from fastapi import UploadFile

            upload = UploadFile(filename="document.jpg", file=io.BytesIO(image))
            phase1_type = self._phase1.DocumentType(document_type.value)
            response = await self._phase1.extract(
                file=upload,
                document_type=phase1_type,
                save_debug=False,
                assume_precropped=False,
            )
            body = response.model_dump() if hasattr(response, "model_dump") else dict(response)
            return OcrOutcome(adapter.from_extract_response(case_id, document_type, body), body)
        except Exception:
            log.exception("Extraction failed")
            return OcrOutcome(
                adapter.from_failure(
                    case_id=case_id,
                    code="EXTRACTION_ERROR",
                    message="Field extraction could not complete for this capture.",
                ),
                None,
            )

    def _run_validation(self, case_id: str, document_type: Any, ocr: "OcrOutcome") -> Any:
        """backend/validation: deterministic rules over the extracted fields."""
        adapter = self.adapters.validation_backend

        if self._validator_module is None:
            return adapter.unavailable(
                case_id=case_id,
                reason_code="VALIDATION_UNAVAILABLE",
                message="The validation service is not running. No rules were applied.",
            )

        # Rules run on extracted fields. With no fields there is nothing to
        # check, and reporting checks that never ran would be an invention.
        raw = ocr.raw
        if raw is None:
            return adapter.unavailable(
                case_id=case_id,
                reason_code="NO_EXTRACTED_FIELDS",
                message="Extraction produced no fields, so no rules could be applied.",
            )

        try:
            structured: Dict[str, Any] = {
                "document_type": document_type.value,
                "fields": _validation_fields(document_type.value, raw),
            }
            mrz = _validation_mrz(raw)
            if mrz:
                structured["mrz"] = mrz

            validator = self._validator_module.DocumentValidator(rules_dir=self._rules_dir)
            output = validator.validate(structured)
            return adapter.from_validator_output(case_id, document_type, output)
        except Exception:
            log.exception("Validation failed")
            return adapter.from_failure(
                case_id=case_id,
                code="VALIDATION_ERROR",
                message="The rule checks could not complete for this document.",
            )

    def _run_face(self, case_id: str, document: bytes, person: bytes) -> Any:
        """
        SCRFD detection, five-point alignment, ArcFace R50, cosine similarity.

        The document portrait is extracted by the face pipeline's own
        `crop_portrait` step, which is what it was built to do — it takes the
        document photograph and locates the printed portrait within it.
        """
        adapter = self.adapters.face_arcface

        if self._face is None:
            return adapter.from_failure(
                case_id=case_id,
                code="FACE_UNAVAILABLE",
                message="Face verification is not running. The portrait was not compared.",
            )

        # The pipeline reads from disk, so the captures are written to a
        # temporary directory that is removed as soon as the comparison ends.
        # Nothing about the subject outlives the request here.
        with tempfile.TemporaryDirectory(prefix="ssb-face-") as workspace:
            document_path = Path(workspace) / "document.jpg"
            person_path = Path(workspace) / "person.jpg"
            document_path.write_bytes(document)
            person_path.write_bytes(person)

            try:
                result = self._face.verify(str(document_path), str(person_path))
                return adapter.from_verification_result(case_id, result)
            except Exception as error:
                log.exception("Face verification failed")
                # A face the detector could not find is a real, common outcome
                # at a counter, and it is reported as an absence of evidence
                # rather than as a non-match.
                return adapter.from_failure(
                    case_id=case_id,
                    code="FACE_COMPARISON_FAILED",
                    message=str(error) or "The portrait comparison could not complete.",
                )

    def _forensics_unavailable(self, case_id: str) -> Any:
        code, message = FORENSICS_NOT_IMPLEMENTED
        return self.contracts.not_available(
            case_id=case_id,
            module=self.contracts.Module.DOCUMENT_FORENSICS,
            reason_code=code,
            message=message,
        )

    # -- case ------------------------------------------------------------

    async def screen(
        self,
        case_id: str,
        document_type_value: str,
        document: bytes,
        person: bytes,
    ) -> Dict[str, Any]:
        document_type = self.contracts.parse(document_type_value)

        ocr = await self._run_ocr(case_id, document_type, document)
        validation = self._run_validation(case_id, document_type, ocr)
        face = self._run_face(case_id, document, person)

        result = self.contracts.assemble(
            case_id=case_id,
            document_type=document_type,
            ocr=ocr.envelope,
            validation=validation,
            face_verification=face,
            document_forensics=self._forensics_unavailable(case_id),
        )
        return result.to_dict()
