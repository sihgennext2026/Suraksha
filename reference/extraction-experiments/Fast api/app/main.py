"""
main.py

FastAPI service wiring the three pipeline stages together:

    upload image -> DocumentDetector (best.onnx)
                 -> perspective correction (contour-based, from the real box)
                 -> DocumentOCR (PP-OCRv5, pretrained, local model files)
                 -> JSON response

Models are loaded ONCE at startup (not per-request) via FastAPI's lifespan
hook, since loading PaddleOCR/onnxruntime per-request would make every call
take seconds just to warm up.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from . import config
from .detector import DocumentDetector
from .ocr import DocumentOCR
from .perspective import correct_from_detection
from .schemas import ExtractResponse, TextLine, Timings

# Populated at startup, used by every request -- see lifespan() below.
_state = {"detector": None, "ocr": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading document detector (best.onnx) ...")
    _state["detector"] = DocumentDetector()
    print("Loading PP-OCRv5 (local model files, offline) ...")
    _state["ocr"] = DocumentOCR()
    print("Models loaded. Ready.")
    yield
    _state.clear()


app = FastAPI(
    title="Document Detection + Perspective Correction + OCR API",
    description="YOLOv12s (ONNX) document detection -> perspective correction -> PP-OCRv5 (pretrained).",
    version="1.0.0",
    lifespan=lifespan,
)


def _read_upload_to_bgr(raw_bytes: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return image_bgr


@app.get("/health")
def health():
    ready = _state["detector"] is not None and _state["ocr"] is not None
    return {"status": "ok" if ready else "loading"}


@app.post("/extract", response_model=ExtractResponse)
async def extract(
    file: UploadFile = File(..., description="Photo containing a document"),
    save_debug: bool = Query(False, description="If true, saves original/crop/corrected images "
                                                  "to api_debug_output/ for visual inspection"),
):
    detector: DocumentDetector = _state["detector"]
    ocr: DocumentOCR = _state["ocr"]
    if detector is None or ocr is None:
        raise HTTPException(status_code=503, detail="Models are still loading, try again shortly.")

    raw_bytes = await file.read()
    image_bgr = _read_upload_to_bgr(raw_bytes)
    if image_bgr is None:
        raise HTTPException(status_code=400, detail="Could not decode the uploaded file as an image.")

    total_t0 = time.perf_counter()

    # --- Stage 1: detection ---
    t0 = time.perf_counter()
    box = detector.detect(image_bgr)
    detection_ms = (time.perf_counter() - t0) * 1000.0

    if box is None:
        return ExtractResponse(
            detected=False,
            message="No document detected above the confidence threshold.",
            timings_ms=Timings(detection_ms=detection_ms, correction_ms=0.0, ocr_ms=0.0,
                                total_ms=(time.perf_counter() - total_t0) * 1000.0),
        )

    x1, y1, x2, y2, conf = box

    # --- Stage 2: perspective correction ---
    debug_prefix = None
    if save_debug:
        os.makedirs(config.DEBUG_OUTPUT_DIR, exist_ok=True)
        stem = os.path.splitext(file.filename or "upload")[0]
        debug_prefix = os.path.join(config.DEBUG_OUTPUT_DIR, f"{stem}_{int(time.time())}")

    t0 = time.perf_counter()
    corrected_image, correction_mode, _quad = correct_from_detection(image_bgr, box, debug_prefix=debug_prefix)
    correction_ms = (time.perf_counter() - t0) * 1000.0

    if corrected_image is None:
        return ExtractResponse(
            detected=True,
            detection_confidence=float(conf),
            detection_box=[float(x1), float(y1), float(x2), float(y2)],
            correction_mode=correction_mode,
            message="Detection succeeded but the crop was empty; nothing to run OCR on.",
            timings_ms=Timings(detection_ms=detection_ms, correction_ms=correction_ms, ocr_ms=0.0,
                                total_ms=(time.perf_counter() - total_t0) * 1000.0),
        )

    if save_debug:
        cv2.imwrite(f"{debug_prefix}__original.jpg", image_bgr)
        cv2.imwrite(f"{debug_prefix}__corrected.jpg", corrected_image)

    # --- Stage 3: OCR ---
    texts, _scores, _polys, ocr_ms = ocr.run(corrected_image)

    lines = [TextLine(text=t) for t in texts]
    full_text = " ".join(texts)

    total_ms = (time.perf_counter() - total_t0) * 1000.0

    return ExtractResponse(
        detected=True,
        detection_confidence=float(conf),
        detection_box=[float(x1), float(y1), float(x2), float(y2)],
        correction_mode=correction_mode,
        lines=lines,
        full_text=full_text,
        timings_ms=Timings(detection_ms=detection_ms, correction_ms=correction_ms,
                            ocr_ms=ocr_ms, total_ms=total_ms),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})
