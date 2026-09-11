"""
ocr.py

Wraps PP-OCRv5 (pretrained, no fine-tuning) behind a small class.

Loads one engine PER LANGUAGE FAMILY, lazily and cached, so the pipeline
can read visible field text in whatever script a given document uses
(Latin, Devanagari, Arabic, Cyrillic, Tamil, Telugu, etc.) instead of
being locked to English/Chinese only. See app/lang_map.py for how a
language family is chosen for a given document (via the MRZ country
code) -- this file only knows how to load and run an engine once told
which family to use; it does no language detection itself.

MOBILE models only, everywhere -- and this stays true automatically for
multilingual families, not just by convention:
- For the default "ch" family (Simplified/Traditional Chinese, Pinyin,
  English, Japanese), PP-OCRv5 ships BOTH a mobile and a much larger
  server variant. The server rec model turned out to be too slow for
  this hardware in practice (~130s/image even with CPU acceleration --
  it's a large transformer built for GPU servers, not laptop CPUs), so
  the "ch" engine explicitly pins the mobile det+rec model names to
  avoid ever silently picking the server one.
- For every OTHER language family (Latin, Arabic, Devanagari, Cyrillic,
  Tamil, Telugu, Greek, Korean, Thai, ...), PP-OCRv5 only ships MOBILE
  recognition models -- no server-sized alternative exists for these at
  all. So passing `lang=<family>` for those can't accidentally resolve
  to a slow server model; there isn't one to resolve to.

Model files aren't all in your local folders yet. The first time a new
language family is used, PaddleX downloads that family's small model
files (a few MB) and caches them under
C:\\Users\\<you>\\.paddlex\\official_models\\ -- every run after that is
fully offline again, same as the textline-orientation model earlier.
Consider warming up (pre-loading) every family you expect to need ahead
of a live demo/deployment, so no request pays a download cost.
"""
import time
from typing import Dict, List, Tuple

import numpy as np
from paddleocr import PaddleOCR

from . import config

# The "default" language family -- covers Simplified/Traditional Chinese,
# Pinyin, English, and Japanese in one model. This is the only family
# where PP-OCRv5 also ships a (slow) server variant, hence the explicit
# mobile pin below.
DEFAULT_LANG = "ch"


class DocumentOCR:
    """Loads PP-OCRv5 engines lazily, one per language family, and
    caches each after first use. Call .run(image_bgr, lang=...) per
    request with whichever family the document needs."""

    def __init__(self):
        self._engines: Dict[str, PaddleOCR] = {}

    def _build_engine(self, lang: str) -> PaddleOCR:
        common_kwargs = dict(
            use_doc_orientation_classify=False,   # perspective correction already ran upstream
            use_doc_unwarping=False,              # ditto -- avoid double warping
            use_textline_orientation=False,       # perspective correction already handles orientation
            enable_mkldnn=True,                  # required for fast inference on this
                                                   # PaddlePaddle version; disabling it
                                                   # causes a ~4x slowdown. Note:
                                                   # PP-OCRv5_mobile_det crashes with mkldnn
                                                   # on this version (oneDNN/PIR
                                                   # ArrayAttribute bug), so non-"ch"
                                                   # languages use the server det model
                                                   # which is mkldnn-compatible.
            device=config.DEVICE,
        )

        if lang == DEFAULT_LANG:
            # Explicit mobile pin -- this is the one family with a server
            # alternative, so name both models directly to guarantee we
            # never load the ~130s/image server variant.
            return PaddleOCR(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="PP-OCRv5_mobile_rec",
                **common_kwargs,
            )

        # Every other family (latin, devanagari, arabic, cyrillic, ta,
        # te, el, korean, th, ...) is mobile-only in PP-OCRv5, so simply
        # letting PaddleOCR resolve the family by `lang` is safe -- it
        # cannot land on a slow server model; there isn't one to resolve to.
        # ocr_version must be given explicitly here: PaddleOCR can't
        # resolve a lang family to a model set without knowing which
        # OCR generation's model list to search.
        return PaddleOCR(lang=lang, ocr_version="PP-OCRv5", **common_kwargs)

    def _get_engine(self, lang: str) -> PaddleOCR:
        if lang not in self._engines:
            self._engines[lang] = self._build_engine(lang)
        return self._engines[lang]

    def run(self, image_bgr: np.ndarray, lang: str = DEFAULT_LANG) -> Tuple[List[str], List[float], List[list], float]:
        """Returns (texts, confidences, polygons, latency_ms) for the
        given image, using the engine for `lang` (loaded/cached on first
        use). Pass the language family the document actually needs --
        see app/lang_map.py for choosing one from the MRZ country code."""
        engine = self._get_engine(lang)

        t0 = time.perf_counter()
        result = engine.predict(image_bgr)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        texts, scores, polys = [], [], []
        for res in result:
            payload = res.get("res", res) if isinstance(res, dict) else res
            texts = list(payload.get("rec_texts", []))
            scores = [float(s) for s in payload.get("rec_scores", [])]
            polys_raw = payload.get("rec_polys", payload.get("dt_polys", []))
            polys = [np.array(p).tolist() for p in polys_raw]
        return texts, scores, polys, latency_ms

    def warm_up(self, langs: List[str]) -> None:
        """Optional: pre-load a list of language engines ahead of time
        (e.g. at server startup) so the first real request for a given
        language doesn't pay the one-time model download/load cost."""
        for lang in langs:
            self._get_engine(lang)
