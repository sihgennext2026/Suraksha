"""
lang_fallback.py

Unified language-resolution fallback chain for the field-region OCR pass,
plus a bilingual dual-pass merge, used because two separate problems show
up across passport / visa / permit / national ID / driving license:

  (1) Not every document type has an MRZ to derive language from (driving
      licenses usually don't, IDPs never do, many visas don't, non-ICAO
      national IDs like Aadhaar don't).
  (2) Several document types print TWO scripts side by side (native
      script + Latin/English) -- driving licenses and Aadhaar especially
      -- so picking one "winning" language and discarding the rest
      always loses whichever script didn't win.

Language resolution chain (cheapest / most reliable first):
    1. MRZ format validation -> trust MRZ-derived language only if the
       OCR'd MRZ region actually looks like MRZ (right line count/length
       for TD1/TD2/TD3, restricted A-Z0-9< character set, sane structure).
       This does NOT decode or checksum MRZ -- that stays owned entirely
       by the separate downstream MRZ module, same as lang_map.py's own
       docstring already promises.
    2. Header country detection -> if MRZ is absent/invalid, OCR a Latin-
       script header band and pattern-match against known ICAO country
       codes / country names. SPECIAL CASE (WORK 2 Tamil fix): country
       "IND" does NOT resolve straight to Hindi here anymore -- India has
       no single national script for state-issued documents, so IND
       triggers a small sub-race across lang_map.INDIA_SCRIPT_CANDIDATES
       (hi/ta/te) instead. See the "IND" branch below for why this was
       the actual root cause of Tamil OCR failing (it wasn't a Tamil
       model problem -- Tamil was never being selected at all).
    3. Confidence race -> if still ambiguous, run the field region
       through every family in lang_map.ALL_LANG_FAMILIES (not just a
       hardcoded handful) and keep whichever gives the highest mean
       PP-OCRv5 recognition confidence, with an early exit once one
       candidate is clearly good enough.
    4. Default fallback -> lang_map.DEFAULT_LANG ("fr", the shared Latin
       family representative). Also the naturally correct answer for
       IDPs, which print in Latin script by Geneva Convention design.

Bilingual dual-pass (run_field_ocr): once a primary language is resolved,
if it isn't already the Latin default, a second pass in the Latin family
is run over the SAME field-region crop and merged in via bounding-box
overlap -- lines the two passes agree are the same physical text line
keep whichever scored higher; lines only one pass found are genuinely
different script regions and are kept from both. This is what actually
recovers the English/Latin side of a bilingual driving license or Aadhaar
card instead of silently dropping it.

Every step reports *why* it decided what it decided, so /extract can
surface language_resolution_method / language_confidence / per-line
`lang` tags for debugging and demo purposes, without touching the MRZ
decode path at all.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Tuple, Dict

import numpy as np

from . import config
from . import lang_map
from .ocr import DocumentOCR

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Step 1: MRZ format validation
# --------------------------------------------------------------------------- #

class MRZFormat(str, Enum):
    TD1 = "TD1"   # national ID cards: 3 lines x 30 chars
    TD2 = "TD2"   # some visas/IDs:    2 lines x 36 chars
    TD3 = "TD3"   # passports:         2 lines x 44 chars
    UNKNOWN = "UNKNOWN"


_MRZ_SPECS: Dict[MRZFormat, Tuple[int, int]] = {
    MRZFormat.TD1: (3, 30),
    MRZFormat.TD2: (2, 36),
    MRZFormat.TD3: (2, 44),
}

_DOC_TYPE_CHARS = set("PVIACR")  # first char of line 1: Passport/Visa/ID/etc -- permissive on purpose
_VALID_MRZ_CHARSET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")


@dataclass
class MRZValidation:
    is_valid: bool
    confidence: float           # 0.0-1.0, how much to trust this as a *language* signal
    detected_format: MRZFormat
    reason: str


def validate_mrz(mrz_lines: List[str]) -> MRZValidation:
    """
    Sanity-checks the OCR'd MRZ region (as returned by DocumentOCR.run(),
    i.e. one string per detected text line) before trusting it for
    language routing. This is a format check only -- no checksums, no
    field parsing. The downstream MRZ decoding module owns all of that;
    this function never sees or influences its output.
    """
    lines = [ln.strip().upper() for ln in (mrz_lines or []) if ln and ln.strip()]
    if not lines:
        return MRZValidation(False, 0.0, MRZFormat.UNKNOWN, "empty MRZ region")

    if len(lines) not in (2, 3):
        return MRZValidation(False, 0.0, MRZFormat.UNKNOWN,
                              f"unexpected line count: {len(lines)}")

    if len(lines) == 3:
        fmt = MRZFormat.TD1
    else:
        avg_len = sum(len(l) for l in lines) / len(lines)
        fmt = MRZFormat.TD3 if avg_len > 40 else MRZFormat.TD2

    expected_lines, expected_len = _MRZ_SPECS[fmt]
    if len(lines) != expected_lines:
        return MRZValidation(False, 0.0, fmt, "line count doesn't match inferred format")

    joined = "".join(lines)
    valid_chars = sum(1 for c in joined if c in _VALID_MRZ_CHARSET)
    char_ratio = valid_chars / max(len(joined), 1)

    length_ok = all(abs(len(l) - expected_len) <= config.MRZ_LINE_LENGTH_TOLERANCE for l in lines)
    doc_type_ok = bool(lines[0]) and lines[0][0] in _DOC_TYPE_CHARS
    has_filler_run = "<<" in joined  # name/field separator, present in virtually all real MRZ

    checks_passed = sum([
        char_ratio >= config.MRZ_CHAR_VALIDITY_RATIO,
        length_ok,
        doc_type_ok,
        has_filler_run,
    ])
    confidence = checks_passed / 4.0
    is_valid = confidence >= 0.75  # 3 of 4 checks

    reason = (f"format={fmt.value} char_ratio={char_ratio:.2f} "
              f"length_ok={length_ok} doc_type_ok={doc_type_ok} filler={has_filler_run}")

    return MRZValidation(is_valid, confidence, fmt, reason)


# --------------------------------------------------------------------------- #
# Step 2: header country detection (Latin-script fallback)
# --------------------------------------------------------------------------- #

# Common full country names that show up on document headers, mapped to
# the same MRZ-style 3-letter codes lang_map.COUNTRY_TO_LANG keys on.
# Extend alongside lang_map.py as you add more countries there.
_COUNTRY_NAME_HINTS: Dict[str, str] = {
    "INDIA": "IND", "BHARAT": "IND",
    "NEPAL": "NPL",
    "UNITED ARAB EMIRATES": "ARE",
    "AFGHANISTAN": "AFG",
    "BAHRAIN": "BHR",
    "ALGERIA": "DZA",
    "EGYPT": "EGY",
    "IRAN": "IRN",
    "IRAQ": "IRQ",
    "JORDAN": "JOR",
    "KUWAIT": "KWT",
    "LEBANON": "LBN",
    "LIBYA": "LBY",
    "MOROCCO": "MAR",
    "OMAN": "OMN",
    "PAKISTAN": "PAK",
    "PALESTINE": "PSE",
    "QATAR": "QAT",
    "SAUDI ARABIA": "SAU",
    "SUDAN": "SDN",
    "SOMALIA": "SOM",
    "SYRIA": "SYR",
    "TUNISIA": "TUN",
    "YEMEN": "YEM",
    "RUSSIA": "RUS", "RUSSIAN FEDERATION": "RUS",
    "UKRAINE": "UKR",
    "BELARUS": "BLR",
    "BULGARIA": "BGR",
    "CHINA": "CHN",
    "TAIWAN": "TWN",
    "HONG KONG": "HKG",
    "MACAU": "MAC", "MACAO": "MAC",
    "JAPAN": "JPN",
    "SOUTH KOREA": "KOR", "REPUBLIC OF KOREA": "KOR",
    "NORTH KOREA": "PRK",
    "THAILAND": "THA",
    "GREECE": "GRC",
    "CYPRUS": "CYP",
    "TURKEY": "TUR", "TURKIYE": "TUR",
    "BANGLADESH": "BGD",
    "SRI LANKA": "LKA",
    "UNITED STATES": "USA", "UNITED STATES OF AMERICA": "USA",
    "UNITED KINGDOM": "GBR",
    "FRANCE": "FRA",
}

# Any 3-letter code lang_map already knows how to route is a valid
# header-detected signal, even though most of them (Latin-script
# countries) aren't explicit keys in COUNTRY_TO_LANG -- those just
# resolve through its DEFAULT_LANG.
_KNOWN_ICAO_CODES = set(lang_map.COUNTRY_TO_LANG.keys()) | set(_COUNTRY_NAME_HINTS.values())


def detect_country_from_header(header_text: str) -> Optional[str]:
    """
    Scans Latin-script header text for a recognizable issuing-country
    signal: either a bare 3-letter ICAO code as a whole token, or a known
    country name. Returns an MRZ-style 3-letter country code (feedable
    into lang_map.COUNTRY_TO_LANG), or None if nothing matched.
    """
    if not header_text:
        return None

    text = header_text.upper()

    tokens = set(t.strip(".,()[]") for t in text.split())
    for tok in tokens:
        if len(tok) == 3 and tok.isalpha() and tok in _KNOWN_ICAO_CODES:
            return tok

    for name in sorted(_COUNTRY_NAME_HINTS, key=len, reverse=True):
        if name in text:
            return _COUNTRY_NAME_HINTS[name]

    return None


# --------------------------------------------------------------------------- #
# Step 3: confidence race across candidate language engines
# --------------------------------------------------------------------------- #

@dataclass
class CandidateResult:
    lang: str
    mean_confidence: float
    line_count: int
    # Full OCR output for this candidate, kept so a later stage that needs
    # this exact (lang, field_region) pass again doesn't have to pay for
    # a second full OCR call -- see run_field_ocr()'s cache lookup below.
    texts: List[str] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    polys: List[list] = field(default_factory=list)


def _mean(scores: List[float]) -> float:
    return sum(scores) / len(scores) if scores else 0.0


def race_candidates(
    ocr: DocumentOCR,
    field_region: np.ndarray,
    candidates: Optional[List[str]] = None,
    early_exit: float = None,
) -> Tuple[str, float, List[CandidateResult]]:
    """
    Runs the field region through candidate language engines (via the
    same cached DocumentOCR instance the rest of the pipeline uses),
    stopping early if one clears `early_exit` mean confidence.

    Defaults to lang_map.ALL_LANG_FAMILIES -- i.e. EVERY family this
    pipeline knows how to route to, not a hardcoded shortlist -- capped
    at config.CONFIDENCE_RACE_MAX_CANDIDATES to bound worst-case latency
    when both MRZ and header detection came up empty.
    """
    candidates = candidates or lang_map.ALL_LANG_FAMILIES
    if config.CONFIDENCE_RACE_MAX_CANDIDATES:
        candidates = candidates[:config.CONFIDENCE_RACE_MAX_CANDIDATES]
    early_exit = config.CONFIDENCE_RACE_EARLY_EXIT if early_exit is None else early_exit

    results: List[CandidateResult] = []
    for lang in candidates:
        texts, scores, polys, _ms = ocr.run(field_region, lang=lang)
        conf = _mean(scores)
        results.append(CandidateResult(lang, conf, len(texts), texts=texts, scores=scores, polys=polys))
        logger.info("lang candidate race: lang=%s mean_conf=%.3f lines=%d", lang, conf, len(texts))

        if conf >= early_exit:
            break

    best = max(results, key=lambda r: r.mean_confidence)
    return best.lang, best.mean_confidence, results


# --------------------------------------------------------------------------- #
# Top-level language resolver
# --------------------------------------------------------------------------- #

@dataclass
class LanguageResolution:
    lang: str
    method: str                 # "mrz" | "header" | "confidence_race" | "default"
    confidence: float
    debug: dict = field(default_factory=dict)
    # Populated only when method == "confidence_race" or "default" (both
    # run race_candidates internally). Lets run_field_ocr() below reuse an
    # already-computed pass instead of re-OCRing the same field_region in
    # the same language a second time.
    race_results: List[CandidateResult] = field(default_factory=list)


def resolve_field_language(
    ocr: DocumentOCR,
    mrz_lines: List[str],
    field_region: np.ndarray,
    candidate_langs: Optional[List[str]] = None,
) -> LanguageResolution:
    """
    Single entry point for main.py's language-decision step. Runs the
    fallback chain only as far as it needs to:

        MRZ valid?  -> use it.
        else header country readable?  -> use it.
        else confidence race across lang_map.ALL_LANG_FAMILIES.
        else lang_map.DEFAULT_LANG.

    `field_region` is the already-cropped, already-perspective-corrected
    field area (everything above the MRZ band, per config.MRZ_CROP_RATIO).
    The header band used in step 2 is derived from its top slice.
    """
    # --- Step 1: MRZ, if present, must pass format validation first ---
    validation = validate_mrz(mrz_lines)
    if validation.is_valid:
        country = lang_map.peek_country_code(mrz_lines[0].strip().upper())
        if country:
            resolved_lang = lang_map.COUNTRY_TO_LANG.get(country, lang_map.DEFAULT_LANG)
            return LanguageResolution(
                lang=resolved_lang, method="mrz", confidence=validation.confidence,
                debug={"country": country, "mrz_check": validation.reason},
            )
        logger.info("MRZ passed format validation but no country substring found: %s", validation.reason)
    else:
        logger.info("MRZ absent/invalid, falling back: %s", validation.reason)

    # --- Step 2: header-based country detection (Latin/English pass) ---
    h = field_region.shape[0]
    header_h = max(1, int(h * config.HEADER_CROP_RATIO))
    header_region = field_region[0:header_h, :]

    header_texts, _h_scores, _h_polys, _h_ms = ocr.run(header_region, lang=lang_map.DEFAULT_LANG)
    header_text = " ".join(header_texts)
    country = detect_country_from_header(header_text)
    if country:
        # WORK 2 BUGFIX (this was the actual cause of Tamil OCR failing):
        # country == "IND" used to fall straight through to
        # lang_map.COUNTRY_TO_LANG["IND"] == "hi" (Devanagari) and return
        # immediately here -- Step 3's confidence race (which DOES know
        # about "ta"/"te") never even ran for Indian documents, because
        # Step 2 already "succeeded". Since almost every Indian document
        # prints "INDIA" / "GOVT OF INDIA" / "REPUBLIC OF INDIA" somewhere
        # in its header, this silently routed EVERY Indian document --
        # including Tamil Nadu driving licences, Tamil national IDs, and
        # Tamil permits -- through the Devanagari recognizer, no matter
        # what script was actually printed. That recognizer was never
        # going to produce correct Tamil text; it wasn't built to. Tamil
        # itself was never broken -- it was simply unreachable.
        #
        # India has no single national script for state-issued documents
        # (see lang_map.INDIA_SCRIPT_CANDIDATES' docstring), so for IND
        # specifically, race the field region across the small Hindi /
        # Tamil / Telugu pool instead of assuming Hindi. This is cheap
        # (at most 3 extra OCR calls, with the same early-exit as any
        # other race) and offline -- no new models, no cloud calls.
        if country == "IND":
            best_lang, best_conf, race_results = race_candidates(
                ocr, field_region, lang_map.INDIA_SCRIPT_CANDIDATES,
            )
            if best_conf >= config.CONFIDENCE_RACE_MIN_ACCEPT:
                return LanguageResolution(
                    lang=best_lang, method="header_india_script_race", confidence=best_conf,
                    debug={"country": country, "header_text_sample": header_text[:120],
                           "candidates": [(r.lang, round(r.mean_confidence, 3)) for r in race_results]},
                    race_results=race_results,
                )
            # None of hi/ta/te scored well enough to trust the race --
            # fall back to the previous behaviour (hi) rather than
            # guessing further; this only happens for genuinely poor
            # scans where none of the three families read confidently.
            return LanguageResolution(
                lang=lang_map.COUNTRY_TO_LANG.get(country, lang_map.DEFAULT_LANG),
                method="header", confidence=0.5,
                debug={"country": country, "header_text_sample": header_text[:120],
                       "note": "India script race inconclusive (all below "
                               "CONFIDENCE_RACE_MIN_ACCEPT), defaulted to hi",
                       "candidates": [(r.lang, round(r.mean_confidence, 3)) for r in race_results]},
                race_results=race_results,
            )

        resolved_lang = lang_map.COUNTRY_TO_LANG.get(country, lang_map.DEFAULT_LANG)
        return LanguageResolution(
            lang=resolved_lang, method="header", confidence=0.75,  # heuristic, not measured
            debug={"country": country, "header_text_sample": header_text[:120]},
        )

    # --- Step 3: confidence race across every known family ---
    best_lang, best_conf, all_results = race_candidates(ocr, field_region, candidate_langs)
    if best_conf >= config.CONFIDENCE_RACE_MIN_ACCEPT:
        return LanguageResolution(
            lang=best_lang, method="confidence_race", confidence=best_conf,
            debug={"candidates": [(r.lang, round(r.mean_confidence, 3)) for r in all_results]},
            race_results=all_results,
        )

    # --- Step 4: default fallback (also the correct answer for IDPs) ---
    return LanguageResolution(
        lang=lang_map.DEFAULT_LANG, method="default", confidence=0.0,
        debug={"reason": "MRZ absent/invalid, header inconclusive, race below acceptance threshold",
               "candidates": [(r.lang, round(r.mean_confidence, 3)) for r in all_results]},
        race_results=all_results,
    )


# --------------------------------------------------------------------------- #
# Bilingual dual-pass merge
# --------------------------------------------------------------------------- #

@dataclass
class MergedLine:
    text: str
    score: float
    poly: list
    lang: str   # which engine produced this specific line


def _bbox(poly: list) -> Tuple[float, float, float, float]:
    xs = [pt[0] for pt in poly]
    ys = [pt[1] for pt in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def merge_bilingual_passes(
    primary: Tuple[List[str], List[float], List[list]],
    primary_lang: str,
    secondary: Tuple[List[str], List[float], List[list]],
    secondary_lang: str,
    iou_threshold: float = None,
) -> List[MergedLine]:
    """
    Merges two OCR passes over the SAME field-region crop (different
    language engines) into one line list -- needed because driving
    licenses, Aadhaar, and many national IDs print native script and
    Latin/English side by side, so a single "winning" language always
    loses whichever script it didn't cover.

    Lines whose bounding boxes substantially overlap are treated as the
    same physical text line (both engines read the same printed line,
    just with different accuracy) -- keep whichever pass scored higher.
    Lines with no overlapping counterpart are genuinely different text
    (the other script's region) and are kept from both passes.
    """
    iou_threshold = config.DUAL_PASS_IOU_THRESHOLD if iou_threshold is None else iou_threshold
    p_texts, p_scores, p_polys = primary
    s_texts, s_scores, s_polys = secondary

    merged: List[MergedLine] = [
        MergedLine(t, sc, poly, primary_lang)
        for t, sc, poly in zip(p_texts, p_scores, p_polys)
    ]
    merged_bboxes = [_bbox(m.poly) for m in merged]

    for t, sc, poly in zip(s_texts, s_scores, s_polys):
        bbox = _bbox(poly)
        best_iou, best_idx = 0.0, -1
        for i, mb in enumerate(merged_bboxes):
            iou = _iou(bbox, mb)
            if iou > best_iou:
                best_iou, best_idx = iou, i

        if best_iou >= iou_threshold:
            if sc > merged[best_idx].score:
                merged[best_idx] = MergedLine(t, sc, poly, secondary_lang)
        else:
            merged.append(MergedLine(t, sc, poly, secondary_lang))
            merged_bboxes.append(bbox)

    return merged


def _cached_pass(resolution: "LanguageResolution", lang: str):
    """Looks for an already-computed (texts, scores, polys) for this exact
    (lang, field_region) pass inside resolution.race_results -- the
    confidence race in resolve_field_language() already OCR'd the SAME
    field_region crop in several languages, including almost always the
    winning one and lang_map.DEFAULT_LANG (it's always the first
    candidate tried, per lang_map.ALL_LANG_FAMILIES' construction).
    Reusing that avoids paying for a full duplicate OCR call here.
    Returns None if no cached pass exists for this language (e.g.
    resolution came from the cheap "mrz"/"header" methods, which never
    ran the race at all)."""
    for r in resolution.race_results:
        if r.lang == lang:
            return r.texts, r.scores, r.polys
    return None


def run_field_ocr(
    ocr: DocumentOCR,
    resolution: LanguageResolution,
    field_region: np.ndarray,
) -> Tuple[List[MergedLine], float, Optional[str]]:
    """
    Runs field-region OCR using the resolved primary language. If that
    language isn't already the Latin default, also runs a second pass in
    the Latin family over the same crop and merges the two -- this is
    what actually recovers the English/Latin side of a bilingual driving
    license or national ID instead of silently dropping it.

    Either pass is skipped in favor of a cache hit from the confidence
    race (see _cached_pass()) whenever resolve_field_language() already
    computed the exact same (lang, field_region) OCR pass while deciding
    which language to use -- no need to run it twice.

    Returns (merged_lines, total_field_ocr_ms, secondary_lang_or_None).
    """
    cached_primary = _cached_pass(resolution, resolution.lang)
    if cached_primary is not None:
        p_texts, p_scores, p_polys = cached_primary
        total_ms = 0.0
    else:
        t0 = time.perf_counter()
        p_texts, p_scores, p_polys, _p_ms = ocr.run(field_region, lang=resolution.lang)
        total_ms = (time.perf_counter() - t0) * 1000.0

    if not config.DUAL_PASS_ENABLED or resolution.lang == lang_map.DEFAULT_LANG:
        merged = [MergedLine(t, s, p, resolution.lang) for t, s, p in zip(p_texts, p_scores, p_polys)]
        return merged, total_ms, None

    cached_secondary = _cached_pass(resolution, lang_map.DEFAULT_LANG)
    if cached_secondary is not None:
        s_texts, s_scores, s_polys = cached_secondary
    else:
        t0 = time.perf_counter()
        s_texts, s_scores, s_polys, _s_ms = ocr.run(field_region, lang=lang_map.DEFAULT_LANG)
        total_ms += (time.perf_counter() - t0) * 1000.0

    merged = merge_bilingual_passes(
        (p_texts, p_scores, p_polys), resolution.lang,
        (s_texts, s_scores, s_polys), lang_map.DEFAULT_LANG,
    )
    return merged, total_ms, lang_map.DEFAULT_LANG
