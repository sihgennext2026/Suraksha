"""
schemas.py

Response shapes for the /extract endpoint. Kept separate from main.py so
they're easy to reuse if you add more endpoints later.
"""
import enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class DocumentType(str, enum.Enum):
    """The five document types this pipeline screens. Selection is
    required on every /extract call and drives whether MRZ
    detection/cropping runs at all -- see MRZ_DOCUMENT_TYPES in
    app/main.py. Passport and Visa are ICAO-9303 MRZ-bearing document
    types; Driving License, National ID, and Permit are not, and MUST
    NOT have an MRZ region cropped from them."""
    PASSPORT = "passport"
    VISA = "visa"
    DRIVING_LICENSE = "driving_license"
    NATIONAL_ID = "national_id"
    PERMIT = "permit"


class TextLine(BaseModel):
    text: str
    # Which PP-OCRv5 language family produced this specific line. Only
    # meaningful when a bilingual dual-pass ran (see
    # ExtractResponse.secondary_lang_used) -- otherwise every line shares
    # detected_lang_family and this is redundant but harmless to include.
    lang: Optional[str] = None
    # WORK 3 (additive, backward compatible -- both default to None so
    # nothing that already parses TextLine breaks): per-line OCR
    # recognition confidence (0..1) and axis-aligned bounding box
    # [x1, y1, x2, y2] in the corrected image's coordinate frame. This is
    # the raw evidence app/field_extractor.py's label/value matching runs
    # over -- exposed here too so the response's "raw OCR evidence" is
    # actually complete (text + confidence + bbox), not just text.
    confidence: Optional[float] = None
    bbox: Optional[List[float]] = None


class MachineCodeDetection(BaseModel):
    code_type: str                           # "qr" or "barcode"
    format: Optional[str] = None             # e.g. "QRCode", "Code128"
    crop_path: Optional[str] = None
    detection_method: Optional[str] = None   # "zxing" or "opencv_fallback"


class MachineCodeResult(BaseModel):
    side: str                                # "front" or "back"
    qr_code: bool = False
    bar_code: bool = False
    qr_crop: Optional[str] = None            # first QR crop path (convenience)
    barcode_crop: Optional[str] = None       # first barcode crop path (convenience)
    qr_crops: List[str] = []                 # all QR crop paths
    barcode_crops: List[str] = []            # all barcode crop paths
    detections: List[MachineCodeDetection] = []
    detection_ms: float = 0.0


class Timings(BaseModel):
    orientation_ms: float
    detection_ms: float
    correction_ms: float
    mrz_ocr_ms: float
    field_ocr_ms: float
    # WORK 3 (additive -- defaults to 0.0 so existing Timings(...) call
    # sites in main.py that don't pass it still work unchanged).
    structured_extraction_ms: float = 0.0
    qr_barcode_ms: float = 0.0
    total_ms: float


class ExtractResponse(BaseModel):
    # Which of the 5 supported types the caller selected, and whether MRZ
    # detection/cropping actually ran for it. mrz_processed is only ever
    # true for "passport"/"visa" -- see app/main.py's MRZ_DOCUMENT_TYPES.
    document_type: Optional[str] = None
    mrz_processed: bool = False

    # WORK 1 -- orientation detection/correction (app/orientation.py),
    # run once before detection. orientation_angle_detected is whatever
    # the classifier reported ("0"/"90"/"180"/"270") even when confidence
    # was too low to act on -- orientation_corrected tells you whether a
    # rotation was actually APPLIED (false for "0", and false for any
    # angle when orientation_confidence fell below
    # config.ORIENTATION_MIN_CONFIDENCE). Every downstream box/quad/pixel
    # coordinate in this response (detection_box, detection_quad, debug
    # images) is already in the POST-rotation coordinate frame.
    orientation_angle_detected: Optional[str] = None
    orientation_confidence: Optional[float] = None
    orientation_corrected: bool = False

    detected: bool
    detection_confidence: Optional[float] = None   # mean segmentation-mask probability, 0..1
    detection_box: Optional[List[float]] = None    # [x1, y1, x2, y2] axis-aligned box around the quad
    detection_quad: Optional[List[float]] = None    # [tl_x, tl_y, tr_x, tr_y, br_x, br_y, bl_x, bl_y]
    correction_mode: Optional[str] = None           # "segmentation_quad_warp" | "fallback_axis_aligned_crop"

    # Raw MRZ text lines, untouched -- for the downstream MRZ decoding /
    # comparison module. This API does no parsing or validation of these.
    # UNCHANGED by WORK 3: still a plain list of strings, exactly as
    # before, so nothing consuming mrz_lines today breaks.
    mrz_lines: List[str] = []

    # WORK 3 (additive): the SAME mrz_lines text, but each entry paired
    # with its OCR confidence and bounding box -- i.e. the same raw
    # evidence field_lines already carries. Empty whenever mrz_lines is
    # (non-MRZ document types, or no MRZ detected).
    mrz_line_details: List[TextLine] = []

    # Visible document field text (name, DOB, place of birth, etc.), in
    # whatever script/language(s) the document actually uses. May contain
    # lines from two different OCR passes -- see secondary_lang_used.
    field_lines: List[TextLine] = []
    field_full_text: str = ""

    # Which PP-OCRv5 language family was used as the PRIMARY field-region
    # pass. Exposed for debugging/traceability only, not itself a decoded
    # MRZ value.
    detected_lang_family: Optional[str] = None

    # How that primary language was decided -- "mrz" | "header" |
    # "confidence_race" | "default". See app/lang_fallback.py. Useful for
    # demo/debugging: shows the chain working for MRZ-less document types
    # (driving licenses, IDPs, Aadhaar, MRZ-less visas) instead of just
    # silently landing on a language.
    language_resolution_method: Optional[str] = None
    language_confidence: Optional[float] = None
    language_resolution_debug: Optional[dict] = None

    # Set only when a bilingual dual-pass actually ran (primary language
    # wasn't already the Latin default) -- the second language family
    # that was merged in. None means field_lines came from a single pass.
    secondary_lang_used: Optional[str] = None

    # WORK 3 -- app/field_extractor.py's standardized output, built from
    # BOTH raw evidence sources above (MRZ for passport/visa, label/value
    # matching over field_lines for every type). Keys follow
    # field_extractor.FIELD_SCHEMA_BY_DOC_TYPE[document_type]; a field
    # the document type doesn't have, or that couldn't be found on this
    # particular document, is null -- never guessed. None (not {}) when
    # document_type has no schema entry or detection failed before OCR
    # ran at all.
    structured_fields: Optional[Dict[str, Optional[str]]] = None

    # Per-field provenance for structured_fields: "mrz" |
    # "label_same_line" | "label_next_line" | "standalone_id" | "not_found". Lets the
    # rule-validation module trust MRZ-sourced fields (checksummed fixed
    # layout) more than label-matched ones (heuristic over free text) if
    # it wants to.
    structured_fields_sources: Optional[Dict[str, str]] = None

    machine_code_result: Optional[MachineCodeResult] = None

    timings_ms: Optional[Timings] = None
    message: Optional[str] = None                  # populated when detected == False
