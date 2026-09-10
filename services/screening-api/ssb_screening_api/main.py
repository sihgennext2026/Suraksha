"""
The screening service the officer application talks to.

One endpoint, `POST /screen`, takes the two captures and returns the canonical
case document defined by `contracts/schemas/ssb-screening.schema.json`. The
application renders that document and stores it unchanged; it does not sequence
the modules, and it does not decide what any of them mean.

Run it with:

    uvicorn ssb_screening_api.main:app --host 0.0.0.0 --port 8000

The host matters: the phone reaches this over the local network, so binding to
localhost alone would make it unreachable from the device.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .pipeline import ScreeningPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("ssb.screening")

#: Refuses a capture larger than this before it reaches a model. A phone photo
#: is a few megabytes; anything far beyond that is a mistake or an abuse, and
#: decoding it would tie up the service for every other officer in the queue.
MAX_IMAGE_BYTES = 25 * 1024 * 1024

_pipeline: Optional[ScreeningPipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Loads every model once, at startup.

    A module that cannot load does not stop the service. It is recorded as
    unavailable and reported that way in each case document, because a screening
    that runs three of five modules and says so is more use at a border post
    than a service that refuses to start.
    """
    global _pipeline
    _pipeline = ScreeningPipeline()
    await _pipeline.start()
    log.info("Screening service ready")
    try:
        yield
    finally:
        await _pipeline.stop()


app = FastAPI(
    title="SSB Suraksha screening service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    """
    Which modules can actually produce evidence right now.

    Surfaced so the application — and anyone evaluating the system — can see the
    difference between a module that is running and one that does not exist,
    without having to run a screening to find out.
    """
    if _pipeline is None:
        return JSONResponse(status_code=503, content={"status": "starting"})
    return {"status": "ok", "modules": _pipeline.availability.as_dict()}


async def _read_capture(upload: UploadFile, field: str) -> bytes:
    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail=f"{field} image was empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"{field} image is too large.")
    return data


@app.post("/screen")
async def screen(
    case_id: str = Form(...),
    document_type: str = Form(...),
    document: UploadFile = File(...),
    person: UploadFile = File(...),
):
    """
    Screens one case and returns the assembled document.

    The officer's declared `document_type` is authoritative and is never
    inferred from the image: it selects the rule set, and a document screened
    under the wrong rules would produce a confident, wrong answer.
    """
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="The service is still starting.")

    document_bytes = await _read_capture(document, "Document")
    person_bytes = await _read_capture(person, "Subject")

    try:
        result = await _pipeline.screen(
            case_id=case_id,
            document_type_value=document_type,
            document=document_bytes,
            person=person_bytes,
        )
    except ValueError as error:
        # `parse` rejects a document type the contract does not define.
        raise HTTPException(status_code=400, detail=str(error)) from error

    log.info(
        "Screened %s (%s) -> %s",
        case_id,
        document_type,
        (result.get("risk") or {}).get("result", {}).get("risk_level")
        if (result.get("risk") or {}).get("result")
        else (result.get("risk") or {}).get("status"),
    )
    return result
