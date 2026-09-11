"""
schemas.py

Response shapes for the /extract endpoint. Kept separate from main.py so
they're easy to reuse if you add more endpoints later.
"""
from typing import List, Optional

from pydantic import BaseModel


class TextLine(BaseModel):
    text: str


class Timings(BaseModel):
    detection_ms: float
    correction_ms: float
    ocr_ms: float
    total_ms: float


class ExtractResponse(BaseModel):
    detected: bool
    detection_confidence: Optional[float] = None
    detection_box: Optional[List[float]] = None   # [x1, y1, x2, y2]
    correction_mode: Optional[str] = None          # "cv_contour_warp" | "fallback_axis_aligned_crop"
    lines: List[TextLine] = []
    full_text: str = ""
    timings_ms: Optional[Timings] = None
    message: Optional[str] = None                  # populated when detected == False
