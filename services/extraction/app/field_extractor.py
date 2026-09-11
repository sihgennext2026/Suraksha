"""
field_extractor.py

WORK 3: converts the pipeline's raw OCR output (MRZ text lines + field-region
text lines, however many scripts/languages they're in) into a small set of
STANDARDIZED, per-document-type fields for a downstream rule-validation
module -- without touching how those raw lines were produced.

This file does NOT:
  - redesign or re-run MRZ detection/cropping (app/main.py's existing
    MRZ_DOCUMENT_TYPES branch, and detector.py/perspective.py, are
    untouched)
  - redesign document-type selection (schemas.DocumentType, chosen by the
    caller, is only ever READ here)
  - change language routing/OCR (app/lang_fallback.py, app/ocr.py are only
    consumed for their output, not modified)
  - invent values: every field returned is either a raw substring of an
    OCR'd line, or a normalized reformatting of one (date format, MRZ
    "SURNAME<<GIVEN" -> "SURNAME, GIVEN") -- nothing is guessed from
    world knowledge (e.g. no "issuing_authority" is ever filled in from
    the fact that a document says "INDIA"; it's only filled from an
    actual "Issuing Authority" / similar label on the document itself).

Two independent evidence sources feed the same output field, and either
(or both) may be used, per document type:

  1. MRZ (Passport/Visa only -- exactly the document types that already
     get an MRZ region cropped+OCR'd upstream). ICAO 9303 TD1/TD2/TD3
     fixed-offset decoding of the RAW MRZ text this pipeline already
     produces. Reliable for name/DOB/sex/document number/nationality/
     expiry date -- MRZ never encodes issue date, issuing authority, or
     address, so those always fall through to (2) for MRZ-bearing
     documents too.
  2. Label/value spatial matching over the field-region OCR lines --
     find a line that looks like a field LABEL ("Date of Birth", "DOB",
     "Licence No.", ...), then take the VALUE either as trailing text on
     that same line, or as the nearest following line (using each line's
     OCR bounding box for "nearest"). This is the ONLY source for
     Driving License / National ID / Permit, which have no MRZ at all.

MRZ is preferred over label matching wherever both are available for the
same field, since MRZ is a fixed, checksummed layout while label matching
is a heuristic over free-form printed text.

MULTILINGUAL LABELS (additive): label/value matching no longer assumes
English-only labels. Every label pattern this module matches against
comes from app/field_labels_i18n.py -- a maintainable, per-language
label dictionary (see that module's docstring for how to extend it to
more languages/labels without touching this file). This is what lets a
purely-Tamil driving licence (பெயர்:, தந்தையின் பெயர்:, பிறந்த தேதி:, ...)
extract the same canonical fields as an English one.

NAME HANDLING (additive): when a document prints a person's name twice
in two different scripts (e.g. Tamil "பெயர்: நேரேந்திரன்" AND English
"Name: Narendran" as two separate OCR'd lines), both are kept: the
Latin-script value becomes `name`, and the non-Latin value is preserved
as `name_native` evidence rather than being discarded or incorrectly
merged with it. Passport/Visa MRZ decoding is also additionally split
into `surname` / `given_name` (alongside the existing combined `name`),
since the MRZ "SURNAME<<GIVEN" separator already gives that split for
free.

FATHER'S NAME (additive): `father_name` is label/value-matched the same
way as every other non-MRZ field (MRZ never encodes it), using the same
multilingual label dictionary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from . import field_labels_i18n
from .schemas import DocumentType

# --------------------------------------------------------------------------- #
# Standardized output schema per document type (additive -- see module
# docstring: fields not present on a given document type are simply not in
# its dict; nothing is padded in as null-by-convention beyond this list).
# Mirrors the example schemas in the WORK 3 spec. Not rigid -- extend this
# dict (and FIELD_LABELS / DOC_NUMBER_LABELS below) as new document types
# or countries are added; nothing else in this file needs to change to do
# that.
# --------------------------------------------------------------------------- #
FIELD_SCHEMA_BY_DOC_TYPE: Dict[DocumentType, List[str]] = {
    DocumentType.PASSPORT: [
        "name", "name_native", "surname", "given_name", "father_name",
        "date_of_birth", "sex", "document_number", "nationality",
        "issue_date", "expiry_date", "issuing_authority",
    ],
    DocumentType.VISA: [
        "name", "name_native", "surname", "given_name",
        "date_of_birth", "passport_number", "visa_number",
        "nationality", "issue_date", "expiry_date",
    ],
    DocumentType.DRIVING_LICENSE: [
        "name", "name_native", "father_name", "date_of_birth", "sex", "document_number",
        "issue_date", "expiry_date", "address", "categories",
    ],
    DocumentType.NATIONAL_ID: [
        "name", "name_native", "father_name", "date_of_birth", "sex", "document_number", "nationality",
        "issue_date", "expiry_date",
    ],
    DocumentType.PERMIT: [
        "name", "name_native", "father_name", "date_of_birth", "document_number",
        "issue_date", "expiry_date", "issuing_authority",
    ],
}
# name_native, surname, given_name are NEVER label/value-matched on their
# own -- name_native only ever comes from a second script match on the
# SAME "name" label pass (see _find_name_and_native below), and
# surname/given_name only ever come from MRZ decoding (parse_mrz). A
# document type without MRZ (Driving License/National ID/Permit) simply
# never populates surname/given_name, same as any other field that
# genuinely isn't present.


@dataclass
class FieldLineLike:
    """Structural shape this module needs from each field-region OCR line
    -- matches app/lang_fallback.MergedLine (text, score, poly, lang)
    without importing it directly, so this module has no hard dependency
    on lang_fallback's internals."""
    text: str
    score: float
    poly: list
    lang: str


def bbox_from_poly(poly: Optional[list]) -> Optional[List[float]]:
    """[x1, y1, x2, y2] axis-aligned box around an OCR polygon, or None
    if the polygon is missing/empty. Shared with main.py so raw
    field_lines/mrz_line_details in the API response carry the same
    bounding boxes this module uses internally."""
    if not poly:
        return None
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    if not xs or not ys:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def _line_center_and_height(bbox: Optional[List[float]]) -> Tuple[float, float, float]:
    if bbox is None:
        return 0.0, 0.0, 0.0
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0, max(1.0, y2 - y1)


# --------------------------------------------------------------------------- #
# Date normalization -> YYYY-MM-DD
# --------------------------------------------------------------------------- #

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_DATE_ISO = re.compile(r"\b(\d{4})[-/.\s]+(\d{1,2})[-/.\s]+(\d{1,2})\b")
_DATE_DMY_NUM = re.compile(r"\b(\d{1,2})[-/.\s]+(\d{1,2})[-/.\s]+(\d{2,4})\b")
_DATE_DMY_TEXT = re.compile(
    r"\b(\d{1,2})[\s/.-]*([A-Za-z]{3,9})\.?[\s/.-]*(\d{2,4})\b"
)
_DATE_MDY_TEXT = re.compile(
    r"\b([A-Za-z]{3,9})\.?[\s/.-]*(\d{1,2})[,\s/.-]*(\d{2,4})\b"
)


def _to_iso(year: int, month: int, day: int) -> Optional[str]:
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def normalize_date(raw: str) -> Optional[str]:
    """Best-effort normalization of a date SUBSTRING already found on the
    document into YYYY-MM-DD. Returns None (never a guess) if nothing
    resembling a date is found. Handles the common printed formats seen
    across passports/visas/driving licences/national IDs:
    DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY, YYYY-MM-DD, "18 MAR 2007",
    "MAR 18, 2007". Two-digit years are expanded 19xx/20xx using the
    same "no future birth dates, no 19xx expiry dates" heuristic MRZ
    parsers commonly use (see parse_mrz._expand_year for the MRZ-specific
    variant, which additionally knows which field it's expanding)."""
    if not raw:
        return None
    text = raw.strip()

    m = _DATE_ISO.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        result = _to_iso(y, mo, d)
        if result:
            return result

    m = _DATE_DMY_TEXT.search(text)
    if m:
        d, mon_raw, y = m.group(1), m.group(2), m.group(3)
        mo = _MONTHS.get(mon_raw.lower())
        if mo:
            year = int(y) if len(y) == 4 else _expand_two_digit_year(int(y))
            return _to_iso(year, mo, int(d))

    m = _DATE_MDY_TEXT.search(text)
    if m:
        mon_raw, d, y = m.group(1), m.group(2), m.group(3)
        mo = _MONTHS.get(mon_raw.lower())
        if mo:
            year = int(y) if len(y) == 4 else _expand_two_digit_year(int(y))
            return _to_iso(year, mo, int(d))

    m = _DATE_DMY_NUM.search(text)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(y) if len(y) == 4 else _expand_two_digit_year(int(y))
        # Printed (non-MRZ) dates on these document types are overwhelmingly
        # DD-MM-YYYY (ICAO/most-of-world convention) rather than MM-DD-YYYY;
        # if the first number can't be a day (>12 rules out month-first) this
        # is unambiguous either way.
        if a > 12 >= b:
            day, month = a, b
        elif b > 12 >= a:
            day, month = b, a
        else:
            day, month = a, b  # ambiguous 2-digit/2-digit -- default to DD-MM
        return _to_iso(year, month, day)

    return None


def _expand_two_digit_year(yy: int) -> int:
    """19xx if that would put the year in the past relative to a fixed
    reasonable cutoff, else 20xx. Only used for PRINTED dates (see
    normalize_date) -- MRZ dates use the field-aware variant below
    because the correct pivot differs between a birth date (person could
    genuinely be 90+) and an expiry date (documents aren't valid for 90+
    years)."""
    return 1900 + yy if yy > 50 else 2000 + yy


# --------------------------------------------------------------------------- #
# MRZ (ICAO 9303) fixed-offset parsing -- TD1 (3x30), TD2 (2x36), TD3 (2x44)
#
# This is NEW code for the structured-output layer only. It does not touch,
# call, or replace the existing MRZ region detection/cropping/OCR in
# app/main.py (mrz_region crop + ocr.run(..., lang=DEFAULT_LANG)), and does
# not replace app/lang_fallback.py's MRZFormat/validate_mrz (that stays the
# language-routing signal it already is). This is a second, independent
# consumer of the same raw mrz_lines strings, producing decoded FIELDS
# instead of a language-routing confidence score.
# --------------------------------------------------------------------------- #

_MRZ_CHARSET = re.compile(r"^[A-Z0-9<]+$")


@dataclass
class MRZFields:
    name: Optional[str] = None
    # Additive: the same "<<"-separated MRZ name field, pre-split, so
    # callers that want surname/given_name separately (see the
    # COMMON STRUCTURED OUTPUT example schema in the WORK 3 spec) don't
    # have to re-parse `name` themselves.
    surname: Optional[str] = None
    given_name: Optional[str] = None
    document_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_country: Optional[str] = None


def _clean_mrz_lines(mrz_lines: Sequence[str]) -> List[str]:
    lines = [ln.strip().upper().replace(" ", "") for ln in (mrz_lines or []) if ln and ln.strip()]
    # Tolerate OCR noise (stray non-MRZ characters) rather than rejecting
    # the whole line -- but require the line to be MOSTLY the MRZ charset
    # before trusting it at all.
    kept = []
    for ln in lines:
        valid = sum(1 for c in ln if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
        if ln and valid / len(ln) >= 0.85:
            kept.append(ln)
    return kept


def _mrz_name_field(raw: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """"SURNAME<<GIVEN<NAMES<<<<..." -> ("SURNAME, GIVEN NAMES",
    "SURNAME", "GIVEN NAMES"). Falls back to splitting on a single "<"
    when OCR drops one of the two chevrons (common: "HUSEYNLI<ORKHAN"
    instead of "HUSEYNLI<<ORKHAN"). Returns (None, None, None) only
    when no plausible split exists at all."""
    raw = raw.rstrip("<")
    if "<<" in raw:
        surname, _, given = raw.partition("<<")
    elif "<" in raw:
        parts = [p for p in raw.split("<") if p]
        if not parts:
            return None, None, None
        surname = parts[0]
        given = "<".join(parts[1:])
    else:
        return None, None, None
    surname = surname.replace("<", " ").strip()
    given = given.replace("<", " ").strip()
    given = re.sub(r"\s+", " ", given)
    surname = re.sub(r"\s+", " ", surname)
    if not surname:
        return None, None, None
    full = f"{surname}, {given}" if given else surname
    return full, surname, (given or None)


def _mrz_date(yymmdd: str, *, field: str) -> Optional[str]:
    """YYMMDD -> YYYY-MM-DD. `field` picks the century pivot: a birth
    date can legitimately be up to ~100 years in the past, an expiry
    date on a currently-scanned document can't realistically be from the
    1900s. Returns None on anything that isn't 6 digits or isn't a
    plausible calendar date."""
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mo, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    if not (1 <= mo <= 12 and 1 <= dd <= 31):
        return None
    if field == "expiry":
        # Expiry dates on a document being scanned today are essentially
        # never pre-2000; treat the pivot as "always 20xx".
        year = 2000 + yy
    else:  # "birth"
        import datetime
        current_yy = datetime.date.today().year % 100
        year = 1900 + yy if yy > current_yy else 2000 + yy
    return _to_iso(year, mo, dd)


def _mrz_sex(code: str) -> Optional[str]:
    code = code.strip("<").strip()
    if code in ("M", "F", "X"):
        return code
    return None


def parse_mrz(mrz_lines: Sequence[str]) -> Optional[MRZFields]:
    """Decodes whichever of TD1/TD2/TD3 the (already OCR'd, already
    upstream-cropped) MRZ lines look like. Returns None if the lines
    don't resemble any known MRZ format closely enough to trust --
    never a partially-guessed result."""
    lines = _clean_mrz_lines(mrz_lines)
    if len(lines) == 3 and all(len(ln) >= 28 for ln in lines):
        return _parse_td1(lines)
    if len(lines) == 2:
        max_len = max(len(l) for l in lines)
        avg_len = sum(len(l) for l in lines) / 2
        # Try TD3 first when ANY line is clearly TD3-length (>= 42).
        # OCR often truncates trailing '<' from line 1, making it shorter
        # than 44 while line 2 stays full-length. avg_len would wrongly
        # route this to TD2; max_len catches it.
        if max_len >= 42:
            result = _parse_td3(lines)
            if result is not None:
                return result
        if avg_len >= 34:
            return _parse_td2(lines)
    return None


def _parse_td3(lines: List[str]) -> Optional[MRZFields]:
    l1, l2 = (lines[0] + "<" * 44)[:44], (lines[1] + "<" * 44)[:44]
    if l1[0] not in "PV":
        return None
    fields = MRZFields()
    fields.issuing_country = l1[2:5].replace("<", "")
    fields.name, fields.surname, fields.given_name = _mrz_name_field(l1[5:44])
    fields.document_number = l2[0:9].replace("<", "") or None
    fields.nationality = l2[10:13].replace("<", "") or None
    fields.date_of_birth = _mrz_date(l2[13:19], field="birth")
    fields.sex = _mrz_sex(l2[20:21])
    fields.expiry_date = _mrz_date(l2[21:27], field="expiry")
    return fields


def _parse_td2(lines: List[str]) -> Optional[MRZFields]:
    l1, l2 = (lines[0] + "<" * 36)[:36], (lines[1] + "<" * 36)[:36]
    if l1[0] not in "PV":
        return None
    fields = MRZFields()
    fields.issuing_country = l1[2:5].replace("<", "")
    fields.name, fields.surname, fields.given_name = _mrz_name_field(l1[5:36])
    fields.document_number = l2[0:9].replace("<", "") or None
    fields.nationality = l2[10:13].replace("<", "") or None
    fields.date_of_birth = _mrz_date(l2[13:19], field="birth")
    fields.sex = _mrz_sex(l2[20:21])
    fields.expiry_date = _mrz_date(l2[21:27], field="expiry")
    return fields


def _parse_td1(lines: List[str]) -> Optional[MRZFields]:
    l1 = (lines[0] + "<" * 30)[:30]
    l2 = (lines[1] + "<" * 30)[:30]
    l3 = (lines[2] + "<" * 30)[:30]
    if l1[0] not in "PVIAC":
        return None
    fields = MRZFields()
    fields.issuing_country = l1[2:5].replace("<", "")
    fields.document_number = l1[5:14].replace("<", "") or None
    fields.date_of_birth = _mrz_date(l2[0:6], field="birth")
    fields.sex = _mrz_sex(l2[7:8])
    fields.expiry_date = _mrz_date(l2[8:14], field="expiry")
    fields.nationality = l2[15:18].replace("<", "") or None
    fields.name, fields.surname, fields.given_name = _mrz_name_field(l3)
    return fields


# --------------------------------------------------------------------------- #
# Label/value spatial matching over field-region OCR lines
# --------------------------------------------------------------------------- #

# Label patterns for every canonical field this module can fill by
# label/value matching -- sourced from app/field_labels_i18n.py, which is
# the actual maintainable, multilingual label dictionary (English, Tamil,
# Hindi/Devanagari, Chinese, French, Spanish today -- see that module's
# docstring for how to add more languages/labels). To extend the set of
# fields or languages this module recognizes, edit
# field_labels_i18n.FIELD_LABELS_I18N; nothing else in THIS file needs to
# change.
FIELD_LABELS: Dict[str, List[str]] = {
    field: field_labels_i18n.patterns_for(field)
    for field in (
        "name", "surname", "given_name", "father_name", "date_of_birth", "sex",
        "nationality", "issue_date", "expiry_date", "issuing_authority",
        "address", "categories",
    )
}

# document_number's label differs by document type (a driving licence says
# "Licence No.", a national ID says "ID No.", etc.) -- and for Visa the
# schema splits it into passport_number / visa_number instead of a single
# document_number. Checked BEFORE the generic fallback at the end of this
# dict.
DOC_NUMBER_LABELS: Dict[DocumentType, List[str]] = {
    DocumentType.PASSPORT: [r"\bpassport\s*no\.?\b", r"\bpassport\s*number\b", r"\bdocument\s*no\.?\b"],
    DocumentType.DRIVING_LICENSE: [
        r"\bd\.?l\.?\s*no\.?\b", r"\blicen[cs]e\s*no\.?\b", r"\blicen[cs]e\s*number\b",
        r"\bdriving\s*licen[cs]e\s*no\.?\b",
        r"\bepic\s*no\.?\b", r"\bvoter\s*id\s*no\.?\b", r"\bcard\s*no\.?\b",
        r"\bid\s*no\.?\b",
    ],
    DocumentType.NATIONAL_ID: [
        r"\bid\s*no\.?\b", r"\bidentity\s*no\.?\b", r"\bcard\s*no\.?\b", r"\baadhaar\s*no\.?\b",
        r"\bunique\s*id\s*no\.?\b", r"\bepic\s*no\.?\b", r"\bvoter\s*id\s*no\.?\b",
    ],
    DocumentType.PERMIT: [r"\bpermit\s*no\.?\b", r"\bpermit\s*number\b"],
}
PASSPORT_NUMBER_LABELS = [r"\bpassport\s*no\.?\b", r"\bpassport\s*number\b"]
VISA_NUMBER_LABELS = [r"\bvisa\s*no\.?\b", r"\bvisa\s*number\b", r"\bapplication\s*no\.?\b"]

_ALL_LABEL_PATTERNS = [pat for pats in FIELD_LABELS.values() for pat in pats] + \
    [pat for pats in DOC_NUMBER_LABELS.values() for pat in pats] + \
    PASSPORT_NUMBER_LABELS + VISA_NUMBER_LABELS
_ALL_LABEL_RE = [re.compile(p, re.IGNORECASE) for p in _ALL_LABEL_PATTERNS]


def _looks_like_a_label_line(text: str) -> bool:
    """True if `text` itself looks like it's (mostly/only) a field label
    rather than a value -- used to stop the "value is the next line"
    heuristic from grabbing another field's label instead of an actual
    value when a label has no trailing value on its own line."""
    stripped = text.strip()
    if not stripped:
        return True
    for pat in _ALL_LABEL_RE:
        m = pat.search(stripped)
        if m and len(stripped) - (m.end() - m.start()) <= 3:
            return True
    return False


_MIN_VALUE_CONFIDENCE = 0.6
_MAX_VALUE_HEIGHT_RATIO = 3.5


def _is_plausible_value(line: '_Line', ref_line: Optional['_Line'] = None) -> bool:
    """False for OCR fragments that are almost certainly not real field
    values: very low confidence (likely noise from a signature/photo
    region) or abnormally tall bounding boxes (signature strokes that
    span multiple text rows)."""
    if line.score < _MIN_VALUE_CONFIDENCE:
        return False
    if ref_line is not None and line.bbox is not None and ref_line.bbox is not None:
        _, _, h_val = _line_center_and_height(line.bbox)
        _, _, h_ref = _line_center_and_height(ref_line.bbox)
        if h_ref > 0 and h_val / h_ref > _MAX_VALUE_HEIGHT_RATIO:
            return False
    return True


@dataclass
class _Line:
    text: str
    score: float
    lang: str
    bbox: Optional[List[float]]


def _sorted_lines(field_lines: Sequence[FieldLineLike]) -> List[_Line]:
    lines = [_Line(l.text, l.score, l.lang, bbox_from_poly(l.poly)) for l in field_lines]
    # Reading order approximation: top-to-bottom, then left-to-right.
    # Good enough for the single-column label:value layouts these
    # document types overwhelmingly use; genuinely multi-column layouts
    # (e.g. a two-column Aadhaar back) may occasionally pair a label with
    # the wrong neighboring value -- see the vertical-proximity guard in
    # _find_label_value below, which is what keeps that failure mode rare
    # rather than eliminating it outright.
    def key(l: _Line):
        _, cy, _ = _line_center_and_height(l.bbox)
        cx, _, _ = _line_center_and_height(l.bbox)
        return (round(cy / 10.0), cx)
    return sorted(lines, key=key)


def _extract_value_from_label_match(pattern: re.Pattern, line_text: str) -> Optional[str]:
    m = pattern.search(line_text)
    if not m:
        return None
    trailing = line_text[m.end():]
    trailing = trailing.lstrip(" :.-–—|")
    trailing = trailing.strip()
    return trailing or None


def _on_same_visual_line(a: _Line, b: _Line) -> bool:
    """True when two OCR fragments sit on the same horizontal text row
    (vertical centers within half a line-height of each other)."""
    if a.bbox is None or b.bbox is None:
        return False
    _, ya, ha = _line_center_and_height(a.bbox)
    _, yb, hb = _line_center_and_height(b.bbox)
    threshold = max(ha, hb) * 0.6
    return abs(ya - yb) <= threshold


def _horizontally_adjacent(a: _Line, b: _Line) -> bool:
    """True when two same-row fragments are close enough horizontally to
    be part of the same printed field (not separate columns). Prevents
    merging "Date of issue" with "Date of expiry" in multi-column
    passport layouts where both are on the same row but far apart."""
    if a.bbox is None or b.bbox is None:
        return True
    if b.bbox[2] < a.bbox[0]:
        return False
    gap = b.bbox[0] - a.bbox[2]
    if gap <= 0:
        return True
    _, _, h = _line_center_and_height(a.bbox)
    return gap < h * 1.5


def _column_aligned(label: _Line, value: _Line) -> bool:
    """True if the value is roughly in the same horizontal column as the
    label. Used in Phase 2 (next-line search) to prevent grabbing a
    value from a different column in multi-column layouts (e.g., picking
    up "29-07-2026" from the Issue-Date column as the value for
    "Validity (NT)" which is in the adjacent column). Checks that the
    value's LEFT EDGE starts within the label's horizontal span (extended
    by half the label width on each side)."""
    if label.bbox is None or value.bbox is None:
        return True
    lx1, _, lx2, _ = label.bbox
    vx1, _, vx2, _ = value.bbox
    lw = max(lx2 - lx1, 1)
    pad = lw * 0.5
    return lx1 - pad <= vx1 <= lx2 + pad


def _collect_same_row_continuation(lines: List[_Line], start: int, consumed: set) -> str:
    """Starting from lines[start], concatenate any following unconsumed
    fragments that sit on the same visual row AND are horizontally
    adjacent (OCR often splits a single printed line into multiple
    text fragments)."""
    parts = [lines[start].text.strip()]
    j = start + 1
    while (j < len(lines) and j not in consumed
           and _on_same_visual_line(lines[start], lines[j])
           and _horizontally_adjacent(lines[j - 1], lines[j])):
        parts.append(lines[j].text.strip())
        j += 1
    return " ".join(parts)


def _find_all_label_matches(
    lines: List[_Line], patterns: List[str]
) -> List[Tuple[str, float, str, str]]:
    """Like the (former) single-match _find_label_value, but returns
    EVERY label match found for `patterns`, not just the first --
    (value, confidence, source, line_lang) per match, one entry per
    distinct label line, in reading order. `source` is
    "label_same_line" or "label_next_line"; `line_lang` is the matched
    label line's OCR language-family tag (e.g. "ta", "fr" -- see
    app/lang_fallback.py), used by _find_name_and_native() below to tell
    a native-script match from a Latin-script one. A label line already
    consumed by one match (as either the label or the next-line value)
    is not reused by a later pattern.

    Handles OCR-split labels: when a label like "Father's Name:" is
    split across two adjacent fragments on the same visual row, the
    fragments are joined before pattern matching."""
    if not patterns:
        return []
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    matches: List[Tuple[str, float, str, str]] = []
    consumed: set = set()
    for i, line in enumerate(lines):
        if i in consumed:
            continue

        # Build candidate texts: the line itself, plus the line merged
        # with same-row, horizontally-adjacent neighbors (handles OCR
        # splitting a label across multiple fragments, e.g. "Father's"
        # + "Name:"). The adjacency check prevents merging across
        # separate columns in multi-column layouts.
        candidates: List[Tuple[str, List[int]]] = [(line.text, [i])]
        if (i + 1 < len(lines) and (i + 1) not in consumed
                and _on_same_visual_line(line, lines[i + 1])
                and _horizontally_adjacent(line, lines[i + 1])):
            merged = line.text.rstrip() + " " + lines[i + 1].text.lstrip()
            candidates.append((merged, [i, i + 1]))
            if (i + 2 < len(lines) and (i + 2) not in consumed
                    and _on_same_visual_line(line, lines[i + 2])
                    and _horizontally_adjacent(lines[i + 1], lines[i + 2])):
                merged3 = merged.rstrip() + " " + lines[i + 2].text.lstrip()
                candidates.append((merged3, [i, i + 1, i + 2]))

        matched = False

        # Phase 1: try all candidates for same-line value. Wider
        # merged candidates (e.g. "Name: Narendran") capture values
        # the OCR split from their label into a separate fragment.
        first_matching_cand = None
        for cand_text, cand_indices in candidates:
            if matched:
                break
            for pat in compiled:
                if not pat.search(cand_text):
                    continue
                if first_matching_cand is None:
                    first_matching_cand = (pat, cand_indices)
                same_line_value = _extract_value_from_label_match(pat, cand_text)
                if same_line_value and len(same_line_value) >= 2:
                    last_idx = cand_indices[-1]
                    extra = _collect_same_row_continuation(lines, last_idx, consumed | set(cand_indices))
                    extra_trimmed = extra[len(lines[last_idx].text.strip()):].strip()
                    if extra_trimmed:
                        same_line_value = same_line_value + " " + extra_trimmed
                    value_lang = lines[cand_indices[-1]].lang if len(cand_indices) > 1 else line.lang
                    matches.append((same_line_value, line.score, "label_same_line", value_lang))
                    for idx in cand_indices:
                        consumed.add(idx)
                    matched = True
                break

        # Phase 2: no same-line value found — search forward for a
        # value on a DIFFERENT row. Skips same-row neighbors (other
        # column headers in multi-column layouts) and implausible
        # fragments (signatures, low-confidence noise).
        if not matched and first_matching_cand is not None:
            _, cand_indices = first_matching_cand
            last_idx = cand_indices[-1]
            all_consumed = consumed | set(cand_indices)
            for k in range(last_idx + 1, min(last_idx + 6, len(lines))):
                if k in all_consumed:
                    continue
                nxt = lines[k]
                if _on_same_visual_line(line, nxt):
                    continue
                if _looks_like_a_label_line(nxt.text):
                    break
                if not _is_plausible_value(nxt, ref_line=line):
                    continue
                if not _column_aligned(line, nxt):
                    continue
                _, y_label, h_label = _line_center_and_height(line.bbox)
                _, y_next, _ = _line_center_and_height(nxt.bbox)
                if line.bbox is not None and nxt.bbox is not None and abs(y_next - y_label) > 4 * h_label:
                    break
                value = _collect_same_row_continuation(lines, k, all_consumed)
                if value.strip():
                    extra_consumed = {k}
                    j = k + 1
                    while j < len(lines) and j not in consumed and _on_same_visual_line(lines[k], lines[j]):
                        extra_consumed.add(j)
                        j += 1
                    matches.append((value.strip(), nxt.score, "label_next_line", nxt.lang))
                    for idx in cand_indices:
                        consumed.add(idx)
                    consumed.update(extra_consumed)
                    matched = True
                    break
    return matches


def _find_label_value(lines: List[_Line], patterns: List[str]) -> Optional[Tuple[str, float, str]]:
    """Returns (value_text, confidence, source) for the best field match
    among `patterns`, or None if no label was found at all. Prefers a
    Latin-family match when available -- bilingual documents (e.g. Tamil +
    English) print both scripts, and the Latin/English value is more
    universally useful as the primary structured field."""
    matches = _find_all_label_matches(lines, patterns)
    if not matches:
        return None
    latin = next((m for m in matches if m[3] in field_labels_i18n.LATIN_FAMILY_CODES), None)
    best = latin or matches[0]
    value, score, source, _line_lang = best
    return value, score, source


def _find_name_and_native(
    lines: List[_Line], patterns: List[str]
) -> Optional[Tuple[str, Optional[str], float, str]]:
    """Name-specific matching: a document may print the SAME person's
    name twice, in two different scripts, as two separate OCR'd lines
    (a Tamil "பெயர்:" line and an English "Name:" line -- see this
    module's "NAME HANDLING" docstring section). Returns
    (name_value, name_native_value_or_None, confidence, source).

    Prefers the Latin-script match as the primary `name` (consistent
    with this pipeline's existing convention -- e.g. MRZ-sourced names
    are always Latin), and surfaces any distinct non-Latin match as
    `name_native` evidence rather than discarding it or merging it into
    `name`. If only one script matched, or both matches are identical
    text, `name_native` is None (nothing extra to add). Returns None if
    no "name" label was found in any language at all."""
    matches = _find_all_label_matches(lines, patterns)
    if not matches:
        return None
    latin = next((m for m in matches if m[3] in field_labels_i18n.LATIN_FAMILY_CODES), None)
    native = next(
        (m for m in matches
         if m[3] not in field_labels_i18n.LATIN_FAMILY_CODES
         and _has_non_latin_chars(m[0])),
        None,
    )
    if latin and native and native[0].strip() != latin[0].strip():
        return latin[0], native[0], latin[1], latin[2]
    primary = latin or native or matches[0]
    return primary[0], None, primary[1], primary[2]


# Native-script sex/gender values -> the M/F/X convention this module
# already normalizes English values to (see the WORK 3 spec's own
# example, which prints "sex": "Male" -- kept as single-letter here
# instead, matching the existing, already-downstream-consumed
# convention; this only ADDS recognition of non-Latin values, it does
# not change what gets returned for a value already handled below).
_NATIVE_SEX_VALUES: Dict[str, str] = {
    "ஆண்": "M", "பெண்": "F",       # Tamil
    "पुरुष": "M", "महिला": "F", "स्त्री": "F",  # Hindi/Devanagari
    "男": "M", "女": "F",           # Chinese
}


def _has_non_latin_chars(text: str) -> bool:
    """True if `text` contains at least one character outside the
    Basic Latin + Latin Extended ranges — i.e. actually looks like a
    non-Latin script rather than a Latin misread tagged with a non-Latin
    OCR engine."""
    for ch in text:
        if ord(ch) > 0x024F and not ch.isspace() and ch not in '.:/-,()[]':
            return True
    return False


def _sex_from_text(text: str) -> Optional[str]:
    stripped = text.strip()
    if stripped in _NATIVE_SEX_VALUES:
        return _NATIVE_SEX_VALUES[stripped]
    t = stripped.upper()
    if t in ("M", "F", "X"):
        return t
    if "FEMALE" in t or re.search(r"\bF\b", t):
        return "F"
    if "MALE" in t or re.search(r"\bM\b", t):
        return "M"
    return None


_STANDALONE_SEX_RE = re.compile(
    r"^(?:MALE|FEMALE|ஆண்|பெண்|पुरुष|महिला|स्त्री|男|女)"
    r"(?:[/\s]*(?:MALE|FEMALE|ஆண்|பெண்|पुरुष|महिला|स्त्री|男|女))?$",
    re.IGNORECASE,
)


def _find_standalone_sex(lines: List[_Line]) -> Optional[Tuple[str, float, str]]:
    """Fallback for documents like Aadhaar that print sex as a standalone
    value ("MALE", "ஆண்/MALE") without a label prefix like "Sex:"."""
    for i, line in enumerate(lines):
        text = line.text.strip()
        merged = text
        if len(text) <= 4 and i + 1 < len(lines) and _on_same_visual_line(line, lines[i + 1]):
            merged = text + lines[i + 1].text.strip()
        for candidate in (merged, text):
            cleaned = candidate.replace("/", "").replace(" ", "")
            if _STANDALONE_SEX_RE.match(cleaned):
                sex = _sex_from_text(candidate)
                if sex:
                    return sex, line.score, "standalone_sex"
    return None


def _find_unlabeled_name(lines: List[_Line], dob_patterns: List[str]) -> Optional[Tuple[str, Optional[str], float, str]]:
    """Fallback for documents like Aadhaar that print the name without a
    "Name:" label. Finds the DOB line, then returns the name-like text
    lines immediately above it. Returns (name, name_native_or_None,
    confidence, source) or None."""
    if not dob_patterns:
        return None
    compiled = [re.compile(p, re.IGNORECASE) for p in dob_patterns]

    dob_idx = None
    dob_line = None
    for i, line in enumerate(lines):
        for pat in compiled:
            if pat.search(line.text):
                dob_idx = i
                dob_line = line
                break
        if dob_idx is not None:
            break
    if dob_idx is None or dob_idx < 1 or dob_line is None:
        return None

    name_latin = None
    name_native = None
    consumed: set = set()
    search_start = max(dob_idx - 8, 0)
    for k in range(search_start, dob_idx):
        if k in consumed:
            continue
        cand = lines[k]
        text = cand.text.strip()
        if cand.score < 0.7:
            continue
        if _on_same_visual_line(cand, dob_line):
            continue
        if re.match(r"^[\d\s./:,-]+$", text):
            continue
        if any(p.search(text) for p in compiled):
            continue
        if not any(c.isalpha() for c in text):
            continue
        same_row = _collect_same_row_continuation(lines, k, {dob_idx} | consumed)
        consumed.add(k)
        j = k + 1
        while (j < len(lines) and j not in consumed
               and _on_same_visual_line(lines[k], lines[j])
               and _horizontally_adjacent(lines[j - 1], lines[j])):
            consumed.add(j)
            j += 1
        if any(p.search(same_row) for p in compiled):
            continue
        if _looks_like_a_label_line(same_row):
            continue
        if len(same_row.strip()) < 2:
            continue
        if _has_non_latin_chars(same_row):
            name_native = same_row
        else:
            name_latin = same_row

    if name_latin:
        return name_latin, name_native, 0.8, "positional_above_dob"
    if name_native:
        return name_native, None, 0.8, "positional_above_dob"
    return None


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #

def _extend_address_value(fields: Dict[str, Optional[str]], lines: List[_Line]) -> None:
    """Appends continuation lines to an already-extracted address value.
    Addresses on Indian documents often span 2-3 lines; the label/value
    matcher only captures the first line. This finds the line matching
    the current address text and collects subsequent non-label lines that
    are vertically close and left-aligned with the address value."""
    addr = fields["address"]
    addr_line = None
    addr_idx = None
    for i, line in enumerate(lines):
        if addr.startswith(line.text.strip()) or line.text.strip().startswith(addr[:30]):
            addr_line = line
            addr_idx = i
            break
    if addr_line is None or addr_idx is None:
        return
    _, y_addr, h_addr = _line_center_and_height(addr_line.bbox)
    ax1 = addr_line.bbox[0] if addr_line.bbox else 0
    parts = []
    for k in range(addr_idx + 1, min(addr_idx + 4, len(lines))):
        nxt = lines[k]
        if _on_same_visual_line(addr_line, nxt):
            continue
        if _looks_like_a_label_line(nxt.text):
            break
        if not _is_plausible_value(nxt, ref_line=addr_line):
            break
        _, y_nxt, _ = _line_center_and_height(nxt.bbox)
        if abs(y_nxt - y_addr) > 3 * h_addr:
            break
        nx1 = nxt.bbox[0] if nxt.bbox else 0
        if abs(nx1 - ax1) > h_addr * 4:
            break
        parts.append(nxt.text.strip())
        y_addr = y_nxt
    if parts:
        fields["address"] = addr + " " + " ".join(parts)


def _looks_like_nationality(text: str) -> bool:
    """True if `text` plausibly names a nationality or country. Rejects
    disclaimer-paragraph fragments that match a nationality label keyword
    (e.g. Tamil "குடியுரிமை" inside the Aadhaar disclaimer) but whose
    value is clearly not a country name."""
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped.split()) > 3:
        return False
    if any(ch in stripped for ch in '.;:!?()[]{}'):
        return False
    digit_count = sum(ch.isdigit() for ch in stripped)
    if digit_count > 0:
        return False
    alpha_count = sum(ch.isalpha() for ch in stripped)
    if alpha_count < 2:
        return False
    return True


_GOV_OF_RE = re.compile(
    r"\bgovernment\s+of\s+(\w[\w\s]{1,30}?)(?:\s*$|\s*[,.])",
    re.IGNORECASE,
)
_REPUBLIC_OF_RE = re.compile(
    r"\brepublic\s+of\s+(\w[\w\s]{1,30}?)(?:\s*$|\s*[,.])",
    re.IGNORECASE,
)

_COUNTRY_TO_NATIONALITY: Dict[str, str] = {
    "india": "INDIAN",
    "pakistan": "PAKISTANI",
    "bangladesh": "BANGLADESHI",
    "sri lanka": "SRI LANKAN",
    "nepal": "NEPALESE",
    "china": "CHINESE",
    "japan": "JAPANESE",
    "korea": "KOREAN",
    "france": "FRENCH",
    "germany": "GERMAN",
    "italy": "ITALIAN",
    "spain": "SPANISH",
    "brazil": "BRAZILIAN",
    "mexico": "MEXICAN",
    "canada": "CANADIAN",
    "australia": "AUSTRALIAN",
    "russia": "RUSSIAN",
    "south africa": "SOUTH AFRICAN",
    "nigeria": "NIGERIAN",
    "egypt": "EGYPTIAN",
    "indonesia": "INDONESIAN",
    "malaysia": "MALAYSIAN",
    "thailand": "THAI",
    "philippines": "FILIPINO",
    "vietnam": "VIETNAMESE",
    "turkey": "TURKISH",
    "iran": "IRANIAN",
    "iraq": "IRAQI",
    "saudi arabia": "SAUDI",
    "united kingdom": "BRITISH",
    "united states": "AMERICAN",
}


def _find_nationality_from_header(lines: List[_Line]) -> Optional[str]:
    """Fallback: infer nationality from header text like
    "Government of India". Only checks the top portion of the document
    (first ~10 lines by reading order) where headers appear. Also merges
    adjacent same-row fragments since OCR often splits "Government" and
    "of India" into separate lines."""
    header = lines[:10]
    texts_to_check: List[str] = []
    for i, line in enumerate(header):
        merged = _collect_same_row_continuation(header, i, set())
        texts_to_check.append(merged)
    for i in range(len(header) - 1):
        texts_to_check.append(header[i].text.strip() + " " + header[i + 1].text.strip())
    for text in texts_to_check:
        for pat in (_GOV_OF_RE, _REPUBLIC_OF_RE):
            m = pat.search(text)
            if m:
                country = m.group(1).strip().lower()
                nat = _COUNTRY_TO_NATIONALITY.get(country)
                if nat:
                    return nat
                return country.upper()
    return None


_STANDALONE_DOC_NUMBER_RE = re.compile(
    r"^[A-Z]{2,4}\d{5,12}$"
    r"|^[A-Z]\d{7,14}$"
    r"|^\d{4}\s?\d{4}\s?\d{4}$"
    r"|^[A-Z]{2}\d{13,15}$"
)

_AADHAAR_FRAGMENT_RE = re.compile(r"^\d{4}(\s\d{4}){0,2}$")


def _find_standalone_doc_number(lines: List[_Line]) -> Optional[Tuple[str, float, str]]:
    """Fallback: find a line whose entire text looks like a document/ID
    number (e.g. "RRJ3578119", "A1234567", Aadhaar "1234 5678 9012",
    Indian DL "TN10 20260007941") but has no recognizable label. Only
    used when label-based matching already failed.

    Also handles Aadhaar numbers split across adjacent OCR lines (e.g.
    "3671" + "8891 3257") by merging same-row digit fragments."""
    for line in lines:
        text = line.text.strip()
        compact = text.replace(" ", "")
        if _STANDALONE_DOC_NUMBER_RE.match(compact):
            return compact, line.score, "standalone_id"

    for i, line in enumerate(lines):
        text = line.text.strip()
        if not _AADHAAR_FRAGMENT_RE.match(text):
            continue
        merged = text
        for j in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[j].text.strip()
            if not _AADHAAR_FRAGMENT_RE.match(nxt):
                break
            if not _on_same_visual_line(line, lines[j]):
                break
            merged = merged + " " + nxt
        compact = merged.replace(" ", "")
        if len(compact) == 12 and compact.isdigit():
            return merged, line.score, "standalone_id"
    return None


@dataclass
class StructuredFieldResult:
    fields: Dict[str, Optional[str]]
    # Per-field provenance: "mrz", "label_same_line", "label_next_line",
    # or "not_found" -- lets the downstream rule-validation module weigh
    # MRZ-sourced fields (checksummed layout) differently from
    # label-matched ones (heuristic over free text) if it wants to.
    sources: Dict[str, str]


def extract_structured_fields(
    document_type: DocumentType,
    mrz_lines: Sequence[str],
    field_lines: Sequence[FieldLineLike],
) -> StructuredFieldResult:
    """Builds the standardized field dict for one document, per
    FIELD_SCHEMA_BY_DOC_TYPE[document_type]. Uses MRZ (Passport/Visa
    only) where available, then fills anything MRZ doesn't cover (or
    every field, for the three non-MRZ document types) from label/value
    matching over `field_lines`. A field the document doesn't have --
    or that neither source found -- is None, never guessed.
    """
    schema = FIELD_SCHEMA_BY_DOC_TYPE.get(document_type, [])
    fields: Dict[str, Optional[str]] = {name: None for name in schema}
    sources: Dict[str, str] = {name: "not_found" for name in schema}

    mrz = None
    if document_type in (DocumentType.PASSPORT, DocumentType.VISA):
        mrz = parse_mrz(mrz_lines)

    if mrz is not None:
        mrz_to_schema = {
            "name": "name",
            "surname": "surname",
            "given_name": "given_name",
            "date_of_birth": "date_of_birth",
            "sex": "sex",
            "nationality": "nationality",
            "expiry_date": "expiry_date",
        }
        # Visa's schema calls the MRZ document-number field
        # "passport_number" (see WORK-3-spec example schema);
        # Passport's schema calls it "document_number" directly.
        if document_type == DocumentType.PASSPORT:
            mrz_to_schema["document_number"] = "document_number"
        elif document_type == DocumentType.VISA:
            mrz_to_schema["document_number"] = "visa_number"

        for mrz_attr, schema_key in mrz_to_schema.items():
            if schema_key not in fields:
                continue
            value = getattr(mrz, mrz_attr)
            if value:
                fields[schema_key] = value
                sources[schema_key] = "mrz"

    lines = _sorted_lines(field_lines)

    _DATE_FIELDS = {"date_of_birth", "issue_date", "expiry_date"}

    for schema_key in schema:
        if fields.get(schema_key) and schema_key not in _DATE_FIELDS:
            continue  # already filled from MRZ; dates try label matching too

        if schema_key in ("surname", "given_name"):
            patterns = FIELD_LABELS.get(schema_key)
            if patterns:
                found = _find_label_value(lines, patterns)
                if found:
                    raw_value, _score, source = found
                    fields[schema_key] = raw_value
                    sources[schema_key] = source
            continue

        if schema_key == "name":
            found_name = _find_name_and_native(lines, FIELD_LABELS.get("name", []))
            if found_name is None:
                found_name = _find_unlabeled_name(lines, FIELD_LABELS.get("date_of_birth", []))
            if found_name is None:
                continue
            name_value, native_value, _score, source = found_name
            fields["name"] = name_value
            sources["name"] = source
            if native_value and "name_native" in fields:
                fields["name_native"] = native_value
                sources["name_native"] = source
            continue

        if schema_key == "name_native":
            # Reached even when "name" itself was already filled from
            # MRZ above (Passport/Visa) -- MRZ never carries a native
            # script, so a native-script "name"-labelled line on the
            # visible page (e.g. a Tamil name printed alongside an
            # MRZ-bearing passport) is still worth surfacing here as
            # evidence, independent of where `name` came from.
            if fields.get("name_native"):
                continue
            name_matches = _find_all_label_matches(lines, FIELD_LABELS.get("name", []))
            native = next(
                (m for m in name_matches
                 if m[3] not in field_labels_i18n.LATIN_FAMILY_CODES
                 and _has_non_latin_chars(m[0])),
                None,
            )
            if native and native[0].strip() != (fields.get("name") or "").strip():
                fields["name_native"] = native[0]
                sources["name_native"] = native[2]
            continue

        if schema_key == "document_number":
            patterns = DOC_NUMBER_LABELS.get(document_type, [r"\bno\.?\s*[:.]?"])
        elif schema_key == "passport_number":
            patterns = PASSPORT_NUMBER_LABELS
        elif schema_key == "visa_number":
            patterns = VISA_NUMBER_LABELS
        else:
            patterns = FIELD_LABELS.get(schema_key)
        if not patterns:
            continue

        if schema_key in _DATE_FIELDS:
            all_matches = _find_all_label_matches(lines, patterns)
            for raw_value, _score, source, _lang in all_matches:
                normalized = normalize_date(raw_value)
                if normalized:
                    fields[schema_key] = normalized
                    sources[schema_key] = source
                    break
            continue

        found = _find_label_value(lines, patterns)
        if not found and schema_key in ("document_number", "passport_number", "visa_number"):
            found = _find_standalone_doc_number(lines)
        if not found and schema_key == "sex":
            standalone = _find_standalone_sex(lines)
            if standalone:
                fields["sex"] = standalone[0]
                sources["sex"] = standalone[2]
            continue
        if not found:
            continue
        raw_value, _score, source = found

        if schema_key == "sex":
            sex = _sex_from_text(raw_value)
            if sex:
                fields[schema_key] = sex
                sources[schema_key] = source
        elif schema_key == "nationality":
            if not _looks_like_nationality(raw_value):
                continue
            fields[schema_key] = raw_value
            sources[schema_key] = source
        else:
            fields[schema_key] = raw_value
            sources[schema_key] = source

    if "name" in fields and not fields.get("name"):
        surname = fields.get("surname")
        given = fields.get("given_name")
        if surname:
            fields["name"] = f"{surname}, {given}" if given else surname
            sources["name"] = sources.get("surname", "not_found")

    if "address" in fields and fields.get("address"):
        _extend_address_value(fields, lines)

    if "nationality" in fields and not fields.get("nationality"):
        header_nat = _find_nationality_from_header(lines)
        if header_nat:
            fields["nationality"] = header_nat
            sources["nationality"] = "header_country"

    return StructuredFieldResult(fields=fields, sources=sources)
