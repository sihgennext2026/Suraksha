"""
Document OCR Field Extraction, Evaluation and Validation Service.
Backend/API only — no frontend.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document OCR Field Extraction, Evaluation & Validation Service",
    description=(
        "Backend evaluation service. Accepts raw OCR JSON, extracts document fields "
        "using document-specific extractors, evaluates against expected ground truth "
        "across multiple cases, and runs deterministic document validation. "
        "Document type must be provided by the caller. "
        "Supports: passport, driving_license, visa, national_id, permit."
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["Document Processing"])


@app.get("/")
async def root():
    """API root — backend only."""
    return {
        "service": "document_validation_service",
        "version": "1.1.0",
        "mode": "backend_api_only",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "evaluate": "POST /api/v1/evaluate  {document_type}",
            "evaluate_case": "POST /api/v1/evaluate/case  {document_type, ocr}",
            "extract": "POST /api/v1/extract  {document_type, ocr}",
            "validate": "POST /api/v1/validate  {document_type, fields}",
            "process": "POST /api/v1/process  {document_type, ocr}",
            "document_types": "GET /api/v1/document-types",
        },
        "cli": "python evaluate.py --document-type driving_license",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "document_validation_service",
        "version": "1.1.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
