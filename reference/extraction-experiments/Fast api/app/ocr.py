"""
ocr.py

Wraps PP-OCRv5 (pretrained, no fine-tuning) behind a small class.

Uses the MOBILE variant (PP-OCRv5_mobile_det / PP-OCRv5_mobile_rec),
not the server variant, because the server models turned out to be too
slow for this hardware in practice (~130s/image even with CPU
acceleration on -- the server recognition model is a large transformer
built for GPU servers, not laptop CPUs). Mobile models are the ones
PaddleOCR actually designed for lightweight/edge deployment.

These aren't in your local model folders yet, so the first run of this
downloads them once (a few MB) and caches them under
C:\\Users\\<you>\\.paddlex\\official_models\\ -- every run after that is
fully offline again, same as the textline-orientation model earlier.
"""
import time
from typing import List, Tuple

import numpy as np
from paddleocr import PaddleOCR

from . import config


class DocumentOCR:
    """Loads PP-OCRv5 det+rec once; call .run(image_bgr) per request."""

    def __init__(self):
        self.engine = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False,   # perspective correction already ran upstream
            use_doc_unwarping=False,              # ditto -- avoid double warping
            use_textline_orientation=False,       # perspective correction already handles orientation
            enable_mkldnn=True,                   # CPU acceleration
            device=config.DEVICE,
        )

    def run(self, image_bgr: np.ndarray) -> Tuple[List[str], List[float], List[list], float]:
        """Returns (texts, confidences, polygons, latency_ms)."""
        t0 = time.perf_counter()
        result = self.engine.predict(image_bgr)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        texts, scores, polys = [], [], []
        for res in result:
            payload = res.get("res", res) if isinstance(res, dict) else res
            texts = list(payload.get("rec_texts", []))
            scores = [float(s) for s in payload.get("rec_scores", [])]
            polys_raw = payload.get("rec_polys", payload.get("dt_polys", []))
            polys = [np.array(p).tolist() for p in polys_raw]
        return texts, scores, polys, latency_ms
