"""
main.py

FastAPI service wiring the pipeline stages together:

    upload image -> orientation detection + correction (WORK 1,
                    app/orientation.py -- a tiny 4-class classifier,
                    PP-LCNet_x1_0_doc_ori, run once on the full photo;
                    NOT four full pipeline runs, NOT EXIF-only) -> the
                    rest of the pipeline (detection, correction, OCR)
                    then runs on the ROTATED image, so every coordinate
                    downstream is already in the corrected frame
                 -> DocumentDetector (document_detector.onnx, U-Net
                    segmentation -- outputs the document's 4 corners
                    directly from its mask contour)
                 -> perspective correction (single homography warp from
                    those corners; see app/perspective.py)
                 -> split corrected image into MRZ band / field region
                    -- ONLY for document_type in {"passport", "visa"};
                    every other document_type skips this entirely and
                    uses the full corrected image as the field region
                    (see MRZ_DOCUMENT_TYPES below)
                 -> DocumentOCR pass 1: MRZ band, "latin" family
                    (MRZ is always Latin/OCR-B per ICAO 9303, regardless
                    of the document's issuing country or script -- this
                    API returns the raw MRZ text only; it does NOT parse,
                    validate, or decode it. That's owned by a separate
                    downstream module.)
                 -> resolve field-region PRIMARY language via
                    app/lang_fallback.py: MRZ (validated) -> header
                    country text -> confidence race across every family
                    in lang_map.ALL_LANG_FAMILIES -> default. Needed
                    because not every document type has an MRZ to derive
                    language from (driving licenses, IDPs, many visas,
                    non-ICAO national IDs like Aadhaar).
                 -> DocumentOCR pass 2: field region, resolved language,
                    PLUS a bilingual dual-pass merge in the Latin family
                    when the resolved language isn't already Latin --
                    driving licenses / Aadhaar / many national IDs print
                    native script and English side by side, so a single
                    winning language would otherwise lose one of them.
                 -> structured field extraction (WORK 3, app/field_extractor.py):
                    converts the SAME raw mrz_texts / merged_lines above
                    into a standardized per-document-type field dict
                    (name, date_of_birth, document_number, ...) via MRZ
                    decoding (passport/visa) and/or label-value matching
                    over the field-region OCR lines. No extra OCR calls.
                 -> JSON response: mrz_lines + field_lines kept separate
                    (each now also carrying confidence + bbox), each
                    field_line tagged with which pass produced it, PLUS
                    structured_fields / structured_fields_sources (WORK 3)

Models are loaded ONCE at startup (not per-request) via FastAPI's lifespan
hook, since loading PaddleOCR/onnxruntime per-request would make every call
take seconds just to warm up.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps
import io

from . import config
from . import field_extractor
from . import lang_map
from . import lang_fallback
from . import qr_barcode
from .detector import DocumentDetector
from .ocr import DocumentOCR
from .orientation import OrientationCorrector
from .perspective import correct_from_quad
from .schemas import (DocumentType, ExtractResponse, MachineCodeDetection,
                      MachineCodeResult, TextLine, Timings)

# Populated at startup, used by every request -- see lifespan() below.
_state = {"orientation": None, "detector": None, "ocr": None}

# The only two document types that carry an ICAO-9303 MRZ. Every other
# supported type (driving_license, national_id, permit) must never have
# an MRZ region cropped or OCR'd -- see the branch in extract() below.
MRZ_DOCUMENT_TYPES = {DocumentType.PASSPORT, DocumentType.VISA}

# Every language family this pipeline can route to (see lang_map.py) is
# warmed up at startup, not just a handful -- otherwise the FIRST request
# that resolves to an under-warmed family (via header detection or the
# confidence race) pays a cold model-load/download stall instead of a
# fast cached call. Trade-off: startup time and memory both scale with
# len(lang_map.ALL_LANG_FAMILIES) now (~11 mobile models instead of 5) --
# each is small, but measure this on your actual demo machine.
WARM_UP_LANGS = lang_map.ALL_LANG_FAMILIES


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading orientation classifier (PP-LCNet_x1_0_doc_ori) ...")
    _state["orientation"] = OrientationCorrector()
    print("Loading document detector (document_detector.onnx, U-Net segmentation) ...")
    _state["detector"] = DocumentDetector()
    print("Loading PP-OCRv5 (local model files, offline) ...")
    ocr = DocumentOCR()
    print(f"Warming up OCR language families: {WARM_UP_LANGS} ...")
    ocr.warm_up(WARM_UP_LANGS)
    _state["ocr"] = ocr
    print("Models loaded. Ready.")
    yield
    _state.clear()


app = FastAPI(
    title="Document Detection + Perspective Correction + Multilingual OCR API",
    description="U-Net/ResNet34 (ONNX) document segmentation -> perspective correction -> "
                 "PP-OCRv5 (pretrained), split into MRZ text (raw, for downstream "
                 "decoding) and visible field text -- automatic language routing "
                 "across every document type (passport, visa, permit, national "
                 "ID, driving license) with a header-text / confidence-race "
                 "fallback for MRZ-less documents, plus a bilingual dual-pass "
                 "merge for documents that print native script and English "
                 "side by side. Also returns standardized structured fields "
                 "(name/DOB/document number/... per document type) alongside "
                 "the raw OCR evidence, via MRZ decoding and label-value "
                 "matching (WORK 3).",
    version="2.3.0",
    lifespan=lifespan,
)


def _read_upload_to_bgr(raw_bytes: bytes) -> Optional[np.ndarray]:
    """Decodes an uploaded image, correcting for EXIF orientation first --
    phone photos are frequently stored sideways with an EXIF tag telling
    viewers how to display them upright. cv2.imdecode ignores that tag,
    which previously fed the detector a rotated image and caused it to
    miss the document entirely."""
    try:
        pil_image = Image.open(io.BytesIO(raw_bytes))
        pil_image = ImageOps.exif_transpose(pil_image)
        pil_image = pil_image.convert("RGB")
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    except Exception:
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _split_mrz_and_field_regions(corrected_image: np.ndarray):
    """Splits the corrected document image into a bottom MRZ band and
    the field region above it, per config.MRZ_CROP_RATIO. Only ever
    called for document_type in MRZ_DOCUMENT_TYPES -- see extract()."""
    h, w = corrected_image.shape[:2]
    mrz_crop_y = int(h * (1 - config.MRZ_CROP_RATIO))
    mrz_crop_y = max(0, min(mrz_crop_y, h))
    mrz_region = corrected_image[mrz_crop_y:h, 0:w]
    field_region = corrected_image[0:mrz_crop_y, 0:w]
    return mrz_region, field_region


#: Long-lived, single-worker pools. See the comment in `extract` — Paddle
#: predictors must be called from the thread that created them, so the OCR
#: branch is pinned to one worker for the life of the process.
_OCR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")
_QR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qr")


@app.get("/health")
def health():
    ready = (_state["orientation"] is not None and _state["detector"] is not None
             and _state["ocr"] is not None)
    return {"status": "ok" if ready else "loading"}


def _qr_result_to_schema(result: qr_barcode.QRBarcodeResult) -> MachineCodeResult:
    """Converts the internal QRBarcodeResult to the API response schema."""
    return MachineCodeResult(
        side=result.side,
        qr_code=result.qr_code,
        bar_code=result.bar_code,
        qr_crop=result.qr_crops[0] if result.qr_crops else None,
        barcode_crop=result.barcode_crops[0] if result.barcode_crops else None,
        qr_crops=result.qr_crops,
        barcode_crops=result.barcode_crops,
        detections=[
            MachineCodeDetection(
                code_type=d.code_type,
                format=d.format_name,
                crop_path=d.crop_path,
                detection_method=d.detection_method,
            )
            for d in result.detections
        ],
        detection_ms=round(result.detection_ms, 1),
    )


def _run_qr_barcode_branch(corrected_image: np.ndarray, side: str, request_id: str) -> qr_barcode.QRBarcodeResult:
    """Runs QR/barcode detection + cropping on the corrected image.
    Thread-safe -- no shared mutable state."""
    output_dir = os.path.join(config.QR_BARCODE_OUTPUT_DIR, request_id, side, "qr_barcode")
    result = qr_barcode.detect_and_crop(corrected_image, side=side, output_dir=output_dir)
    json_path = os.path.join(output_dir, "machine_codes.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(qr_barcode.result_to_json(result), f, indent=2, ensure_ascii=False)
    return result


def _run_ocr_branch(
    ocr: DocumentOCR,
    corrected_image: np.ndarray,
    document_type: DocumentType,
    mrz_document_types: set,
    save_debug: bool,
    debug_prefix: Optional[str],
) -> dict:
    """Runs the full OCR pipeline (MRZ split -> MRZ OCR -> language
    resolution -> field OCR -> structured extraction) on the corrected
    image. Returns a dict with all OCR results. Thread-safe as long as
    the PaddleOCR engines are not being modified concurrently (they
    aren't -- they're loaded once at startup and only read here)."""
    mrz_processed = document_type in mrz_document_types

    if mrz_processed:
        mrz_region, field_region = _split_mrz_and_field_regions(corrected_image)
    else:
        mrz_region = None
        field_region = corrected_image

    if save_debug:
        if mrz_region is not None:
            cv2.imwrite(f"{debug_prefix}__mrz_region.jpg", mrz_region)
        cv2.imwrite(f"{debug_prefix}__field_region.jpg", field_region)

    if mrz_processed:
        mrz_texts, mrz_scores, mrz_polys, mrz_ocr_ms = ocr.run(mrz_region, lang=lang_map.DEFAULT_LANG)
    else:
        mrz_texts, mrz_scores, mrz_polys, mrz_ocr_ms = [], [], [], 0.0

    t0 = time.perf_counter()
    resolution = lang_fallback.resolve_field_language(
        ocr=ocr, mrz_lines=mrz_texts, field_region=field_region,
    )
    lang_resolution_ms = (time.perf_counter() - t0) * 1000.0

    merged_lines, field_ocr_ms, secondary_lang = lang_fallback.run_field_ocr(
        ocr=ocr, resolution=resolution, field_region=field_region,
    )

    field_lines = [
        TextLine(text=m.text, lang=m.lang, confidence=m.score,
                 bbox=field_extractor.bbox_from_poly(m.poly))
        for m in merged_lines
    ]
    field_full_text = " ".join(m.text for m in merged_lines)

    mrz_line_details = [
        TextLine(text=t, lang=lang_map.DEFAULT_LANG, confidence=s,
                 bbox=field_extractor.bbox_from_poly(p))
        for t, s, p in zip(mrz_texts, mrz_scores, mrz_polys)
    ]

    t0 = time.perf_counter()
    structured_result = field_extractor.extract_structured_fields(
        document_type=document_type, mrz_lines=mrz_texts, field_lines=merged_lines,
    )
    structured_extraction_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "mrz_processed": mrz_processed,
        "mrz_texts": mrz_texts,
        "mrz_line_details": mrz_line_details,
        "mrz_ocr_ms": mrz_ocr_ms + lang_resolution_ms,
        "field_lines": field_lines,
        "field_full_text": field_full_text,
        "field_ocr_ms": field_ocr_ms,
        "resolution": resolution,
        "secondary_lang": secondary_lang,
        "structured_result": structured_result,
        "structured_extraction_ms": structured_extraction_ms,
    }


@app.post("/extract", response_model=ExtractResponse)
async def extract(
    file: UploadFile = File(..., description="Photo containing a document"),
    document_type: DocumentType = Query(..., description="Document type being uploaded. Required -- "
                                                            "the caller must explicitly select this "
                                                            "before uploading. Controls whether MRZ "
                                                            "detection/cropping runs at all: only "
                                                            "'passport' and 'visa' get an MRZ region "
                                                            "cropped and OCR'd; 'driving_license', "
                                                            "'national_id', and 'permit' never do."),
    save_debug: bool = Query(False, description="If true, saves original/crop/corrected images "
                                                  "to api_debug_output/ for visual inspection"),
    assume_precropped: bool = Query(False, description="If true, force-skip detection/correction "
                                                          "and OCR the uploaded image as-is, "
                                                          "bypassing even the automatic "
                                                          "background check. Normally you don't "
                                                          "need this -- the pipeline already "
                                                          "detects a lack of background on its "
                                                          "own and skips correction accordingly; "
                                                          "this is only for forcing that behavior "
                                                          "regardless of what the background "
                                                          "check decides."),
):
    orientation: OrientationCorrector = _state["orientation"]
    detector: DocumentDetector = _state["detector"]
    ocr: DocumentOCR = _state["ocr"]
    if orientation is None or detector is None or ocr is None:
        raise HTTPException(status_code=503, detail="Models are still loading, try again shortly.")

    raw_bytes = await file.read()
    image_bgr = _read_upload_to_bgr(raw_bytes)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode the uploaded file as an image.")

    total_t0 = time.perf_counter()

    debug_prefix = None
    if save_debug:
        os.makedirs(config.DEBUG_OUTPUT_DIR, exist_ok=True)
        stem = os.path.splitext(file.filename or "upload")[0]
        debug_prefix = os.path.join(config.DEBUG_OUTPUT_DIR, f"{stem}_{int(time.time())}")

    # --- Stage 0: orientation detection + correction (WORK 1) ---
    # Runs unconditionally, even under assume_precropped -- a precropped
    # image can still have been captured/scanned sideways or upside
    # down, and this only costs one small classifier forward pass either
    # way. Everything from here on (detection, correction, OCR, debug
    # images) operates on the POST-rotation image -- image_bgr is
    # reassigned in place so no downstream code needs to know orientation
    # correction happened at all.
    if save_debug:
        cv2.imwrite(f"{debug_prefix}__uploaded_pre_orientation.jpg", image_bgr)

    t0 = time.perf_counter()
    image_bgr, orientation_angle, orientation_confidence, orientation_corrected = orientation.correct(image_bgr)
    orientation_ms = (time.perf_counter() - t0) * 1000.0
    # orientation_corrected now comes DIRECTLY from OrientationCorrector.correct()
    # (its `applied` return value) instead of being re-derived here from
    # angle/confidence -- that re-derivation was exactly the bug: it assumed
    # "confident guess" == "rotation actually applied", which stopped being
    # true once correct() started reverting via its self-consistency check.
    # See app/orientation.py's module docstring for the real-image bug this
    # fixes.

    if assume_precropped:
        detection_ms = 0.0
        correction_ms = 0.0
        quad, conf, (x1, y1, x2, y2) = None, None, (0.0, 0.0, float(image_bgr.shape[1]), float(image_bgr.shape[0]))
        corrected_image, correction_mode = image_bgr, "skipped_assume_precropped"
        if save_debug:
            cv2.imwrite(f"{debug_prefix}__original.jpg", image_bgr)
            cv2.imwrite(f"{debug_prefix}__corrected.jpg", corrected_image)
    else:
        # --- Stage 1: detection (U-Net segmentation -> document quad) ---
        t0 = time.perf_counter()
        detection = detector.detect(image_bgr)
        detection_ms = (time.perf_counter() - t0) * 1000.0

        if detection is None:
            return ExtractResponse(
                document_type=document_type.value,
                orientation_angle_detected=orientation_angle,
                orientation_confidence=orientation_confidence,
                orientation_corrected=orientation_corrected,
                detected=False,
                message="No document detected (segmentation mask had no plausible document region).",
                timings_ms=Timings(orientation_ms=orientation_ms, detection_ms=detection_ms, correction_ms=0.0,
                                    mrz_ocr_ms=0.0, field_ocr_ms=0.0,
                                    total_ms=(time.perf_counter() - total_t0) * 1000.0),
            )

        quad, conf, (x1, y1, x2, y2) = detection

        # --- Stage 2: perspective correction (single warp from the quad) ---
        # quad/x1..y2 above are already in the POST-rotation image's
        # coordinate frame -- detector.detect() ran on the rotated
        # image_bgr, so there's no separate coordinate-mapping step
        # needed here to account for orientation correction.
        t0 = time.perf_counter()
        corrected_image, correction_mode, _rect = correct_from_quad(image_bgr, quad, debug_prefix=debug_prefix)
        correction_ms = (time.perf_counter() - t0) * 1000.0

        if corrected_image is None:
            return ExtractResponse(
                document_type=document_type.value,
                orientation_angle_detected=orientation_angle,
                orientation_confidence=orientation_confidence,
                orientation_corrected=orientation_corrected,
                detected=True,
                detection_confidence=float(conf),
                detection_box=[float(x1), float(y1), float(x2), float(y2)],
                detection_quad=quad.flatten().tolist(),
                correction_mode=correction_mode,
                message="Detection succeeded but the crop was empty; nothing to run OCR on.",
                timings_ms=Timings(orientation_ms=orientation_ms, detection_ms=detection_ms, correction_ms=correction_ms,
                                    mrz_ocr_ms=0.0, field_ocr_ms=0.0,
                                    total_ms=(time.perf_counter() - total_t0) * 1000.0),
            )

        if save_debug:
            cv2.imwrite(f"{debug_prefix}__original.jpg", image_bgr)
            cv2.imwrite(f"{debug_prefix}__corrected.jpg", corrected_image)

    # --- Parallel execution: QR/barcode branch + OCR branch ---
    # Both branches receive the SAME corrected_image (computed once above).
    # QR/barcode detection is CPU-lightweight (ZXing ~tens of ms, OpenCV
    # fallback ~hundreds of ms) and shares no mutable state with OCR, so
    # running them concurrently in threads is safe: numpy arrays are
    # read-only for both, and PaddleOCR engines were loaded once at startup.
    #
    # The two branches use the long-lived single-worker pools declared above
    # rather than a per-request executor. A fresh pool handed OCR to a new
    # thread on every call, and a PaddleOCR engine cached from an earlier
    # request then ran on a thread that had not created it, which surfaced as
    # an intermittent `RuntimeError: Unknown exception` from paddle on roughly
    # one call in three. Pinning OCR to one worker keeps every predictor on the
    # thread that built it while leaving the QR branch genuinely parallel.
    request_id = f"{os.path.splitext(file.filename or 'upload')[0]}_{int(time.time())}"

    qr_future = _QR_EXECUTOR.submit(
        _run_qr_barcode_branch, corrected_image, "front", request_id,
    )
    ocr_future = _OCR_EXECUTOR.submit(
        _run_ocr_branch, ocr, corrected_image, document_type,
        MRZ_DOCUMENT_TYPES, save_debug, debug_prefix,
    )
    qr_result = qr_future.result()
    ocr_result = ocr_future.result()

    total_ms = (time.perf_counter() - total_t0) * 1000.0

    return ExtractResponse(
        document_type=document_type.value,
        mrz_processed=ocr_result["mrz_processed"],
        orientation_angle_detected=orientation_angle,
        orientation_confidence=orientation_confidence,
        orientation_corrected=orientation_corrected,
        detected=True,
        detection_confidence=(float(conf) if conf is not None else None),
        detection_box=[float(x1), float(y1), float(x2), float(y2)],
        detection_quad=(quad.flatten().tolist() if quad is not None else None),
        correction_mode=correction_mode,
        mrz_lines=ocr_result["mrz_texts"],
        mrz_line_details=ocr_result["mrz_line_details"],
        field_lines=ocr_result["field_lines"],
        field_full_text=ocr_result["field_full_text"],
        detected_lang_family=ocr_result["resolution"].lang,
        language_resolution_method=ocr_result["resolution"].method,
        language_confidence=ocr_result["resolution"].confidence,
        language_resolution_debug=ocr_result["resolution"].debug,
        secondary_lang_used=ocr_result["secondary_lang"],
        structured_fields=ocr_result["structured_result"].fields,
        structured_fields_sources=ocr_result["structured_result"].sources,
        machine_code_result=_qr_result_to_schema(qr_result),
        timings_ms=Timings(
            orientation_ms=orientation_ms,
            detection_ms=detection_ms,
            correction_ms=correction_ms,
            mrz_ocr_ms=ocr_result["mrz_ocr_ms"],
            field_ocr_ms=ocr_result["field_ocr_ms"],
            structured_extraction_ms=ocr_result["structured_extraction_ms"],
            qr_barcode_ms=qr_result.detection_ms,
            total_ms=total_ms,
        ),
    )


@app.post("/extract-back")
async def extract_back(
    file: UploadFile = File(..., description="Photo of the BACK side of a document"),
    document_type: DocumentType = Query(..., description="Document type (same as front upload)"),
    save_debug: bool = Query(False, description="Save debug images"),
    assume_precropped: bool = Query(False, description="Skip detection/correction"),
):
    """Back-side document processing: orientation -> detection -> perspective
    correction -> PP-OCRv5 field OCR -> structured extraction -> QR/barcode.

    MRZ processing is deliberately absent rather than merely skipped. An ICAO
    9303 machine-readable zone is a property of a document's biodata page; there
    is no such thing as an MRZ on the reverse, so the back never splits an MRZ
    band and never reports mrz_lines. The OCR branch is shared with the front
    and given an empty MRZ-type set, which is what turns that off."""
    orientation_model: OrientationCorrector = _state["orientation"]
    detector: DocumentDetector = _state["detector"]
    ocr: DocumentOCR = _state["ocr"]
    if orientation_model is None or detector is None or ocr is None:
        raise HTTPException(status_code=503, detail="Models are still loading, try again shortly.")

    raw_bytes = await file.read()
    image_bgr = _read_upload_to_bgr(raw_bytes)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode the uploaded file as an image.")

    total_t0 = time.perf_counter()

    debug_prefix = None
    if save_debug:
        os.makedirs(config.DEBUG_OUTPUT_DIR, exist_ok=True)
        stem = os.path.splitext(file.filename or "upload_back")[0]
        debug_prefix = os.path.join(config.DEBUG_OUTPUT_DIR, f"{stem}_{int(time.time())}")
        cv2.imwrite(f"{debug_prefix}__uploaded_pre_orientation.jpg", image_bgr)

    t0 = time.perf_counter()
    image_bgr, orientation_angle, orientation_confidence, orientation_corrected = orientation_model.correct(image_bgr)
    orientation_ms = (time.perf_counter() - t0) * 1000.0

    if assume_precropped:
        detection_ms = 0.0
        correction_ms = 0.0
        corrected_image = image_bgr
    else:
        t0 = time.perf_counter()
        detection = detector.detect(image_bgr)
        detection_ms = (time.perf_counter() - t0) * 1000.0

        if detection is None:
            return JSONResponse(content={
                "side": "back",
                "document_type": document_type.value,
                "detected": False,
                "orientation_angle_detected": orientation_angle,
                "orientation_corrected": orientation_corrected,
                "machine_code_result": {
                    "side": "back", "qr_code": False, "bar_code": False,
                    "qr_crop": None, "barcode_crop": None,
                },
                "message": "No document detected on back side.",
                "timings_ms": {
                    "orientation_ms": round(orientation_ms, 1),
                    "detection_ms": round(detection_ms, 1),
                    "total_ms": round((time.perf_counter() - total_t0) * 1000.0, 1),
                },
            })

        quad, conf, (x1, y1, x2, y2) = detection

        t0 = time.perf_counter()
        corrected_image, correction_mode, _rect = correct_from_quad(image_bgr, quad, debug_prefix=debug_prefix)
        correction_ms = (time.perf_counter() - t0) * 1000.0

        if corrected_image is None:
            return JSONResponse(content={
                "side": "back",
                "document_type": document_type.value,
                "detected": True,
                "machine_code_result": {
                    "side": "back", "qr_code": False, "bar_code": False,
                    "qr_crop": None, "barcode_crop": None,
                },
                "message": "Detection succeeded but crop was empty.",
                "timings_ms": {
                    "orientation_ms": round(orientation_ms, 1),
                    "detection_ms": round(detection_ms, 1),
                    "correction_ms": round(correction_ms, 1),
                    "total_ms": round((time.perf_counter() - total_t0) * 1000.0, 1),
                },
            })

        if save_debug:
            cv2.imwrite(f"{debug_prefix}__original.jpg", image_bgr)
            cv2.imwrite(f"{debug_prefix}__corrected.jpg", corrected_image)

    request_id = f"{os.path.splitext(file.filename or 'upload_back')[0]}_{int(time.time())}"

    # Same two long-lived pools the front uses, for the same reason: the Paddle
    # engines must be called from the thread that built them.
    qr_future = _QR_EXECUTOR.submit(
        _run_qr_barcode_branch, corrected_image, "back", request_id,
    )
    ocr_future = _OCR_EXECUTOR.submit(
        _run_ocr_branch, ocr, corrected_image, document_type,
        set(),  # no MRZ on a reverse side -- see the docstring above
        save_debug, debug_prefix,
    )
    qr_result = qr_future.result()
    ocr_result = ocr_future.result()

    total_ms = (time.perf_counter() - total_t0) * 1000.0

    mc = _qr_result_to_schema(qr_result)
    resolution = ocr_result["resolution"]
    structured = ocr_result["structured_result"]

    return JSONResponse(content={
        "side": "back",
        "document_type": document_type.value,
        "detected": True,
        "orientation_angle_detected": orientation_angle,
        "orientation_confidence": orientation_confidence,
        "orientation_corrected": orientation_corrected,
        "field_lines": [line.model_dump() for line in ocr_result["field_lines"]],
        "field_full_text": ocr_result["field_full_text"],
        "detected_lang_family": resolution.lang,
        "language_resolution_method": resolution.method,
        "language_confidence": resolution.confidence,
        "secondary_lang_used": ocr_result["secondary_lang"],
        "structured_fields": structured.fields,
        "structured_fields_sources": structured.sources,
        "machine_code_result": mc.model_dump(),
        "timings_ms": {
            "orientation_ms": round(orientation_ms, 1),
            "detection_ms": round(detection_ms, 1),
            "correction_ms": round(correction_ms, 1),
            "field_ocr_ms": round(ocr_result["field_ocr_ms"], 1),
            "structured_extraction_ms": round(ocr_result["structured_extraction_ms"], 1),
            "qr_barcode_ms": round(qr_result.detection_ms, 1),
            "total_ms": round(total_ms, 1),
        },
    })


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    import traceback
    traceback.print_exception(type(exc), exc, exc.__traceback__)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})
