"""
field_labels_i18n.py

Maintainable field-label -> canonical-field mapping for MULTIPLE
languages/scripts, consumed by app/field_extractor.py's label/value
spatial matching (see that module's docstring for how a matched label
line is turned into a field value).

WHY THIS EXISTS AS ITS OWN MODULE
----------------------------------
field_extractor.py's original label patterns were English-only. Indian
state-issued documents (this pipeline's primary deployment target -- see
app/lang_map.py) are frequently printed purely in a native script (Tamil,
Hindi/Devanagari, ...) with no English at all, or with native-script text
that OCR reads as its own separate line from any English co-printed
alongside it (see app/lang_fallback.py's bilingual dual-pass merge). A
label-matcher that only recognizes "Name:" finds nothing at all on a
purely-Tamil document, even when the OCR text itself (பெயர்:) was read
correctly.

This module does NOT translate documents. It only records, for each
canonical field this pipeline extracts, every printed LABEL string
(in every supported language) that is known to represent that field --
see field_extractor.py's "Do NOT translate the entire document" note.

HOW TO ADD A NEW LANGUAGE OR LABEL
-----------------------------------
1. Find (or add) the canonical field's entry in FIELD_LABELS_I18N below.
2. Add a new key for the language. Using the SAME family code
   app/lang_map.py's OCR routing already uses for that script (e.g. "ta"
   for Tamil, "hi" for Devanagari, "ch" for CJK) isn't strictly required
   for matching to work -- patterns_for() flattens everything into one
   combined list regardless of language -- but keeping the same codes
   means the label text here and the OCR `lang` tag the matching line
   will actually carry stay consistent for anyone maintaining this file.
3. Add the label text(s) for that language as a list of strings:
     - Latin-script languages (English, French, Spanish, ... -- anything
       PP-OCRv5 groups into the "fr" family, see lang_map.py) use
       \\b-bounded, case-insensitive REGEX patterns, same style as the
       existing entries, so e.g. "Name" doesn't also match inside
       "Surname".
     - Non-Latin scripts (Tamil, Devanagari, CJK, ...) use PLAIN LITERAL
       strings -- no regex metacharacters, no \\b (Unicode word-boundary
       behavior around combining scripts like Tamil is unreliable).
       patterns_for() regex-escapes these automatically.
4. Nothing else in this file, and nothing in field_extractor.py, needs to
   change -- patterns_for(field) picks up the new entry immediately, and
   FIELD_LABELS in field_extractor.py is built FROM this module.

Coverage here is deliberately not exhaustive for every world language --
it covers English plus every language this pipeline's OCR stage can
actually recognize as a distinct script family for its stated deployment
target (ta/Tamil, hi/Hindi-Devanagari) with high-confidence standard
document terminology, plus French/Spanish/Chinese as worked examples of
extending to further languages/scripts. Add more following the pattern
above as needed.
"""
from __future__ import annotations

import re
from typing import Dict, List

# canonical_field -> { lang_family_code: [labels] }
# Latin-family ("fr") entries are already-valid regex (word-bounded,
# case-insensitive via patterns_for()/the caller's re.IGNORECASE compile).
# Non-Latin entries are plain literal label strings -- see
# _compile_literal() / patterns_for() below for how they become regex.
FIELD_LABELS_I18N: Dict[str, Dict[str, List[str]]] = {
    "surname": {
        "fr": [r"\bsurname\b", r"\blast\s*name\b", r"\bfamily\s*name\b"],
    },
    "given_name": {
        "fr": [r"\bgiven\s*names?\b", r"\bfirst\s*names?\b", r"\bpr[eé]nom\b"],
    },
    "name": {
        "fr": [
            r"\bfull\s*name\b", r"\bholder'?s?\s*name\b", r"\bname\s*of\s*holder\b",
            r"\bnom\b", r"\bnombre\b", r"\bname\b",
        ],
        "ta": ["பெயர்"],
        "hi": ["नाम"],
        "ch": ["姓名"],
    },
    "father_name": {
        "fr": [
            r"\bfather'?s?\s*name\b", r"\bname\s*of\s*father\b",
            r"\bson/?daughter/?wife\s*of\b",
            r"\bs/?d/?w\s*of\b",
            r"\bnom\s*du\s*p[eè]re\b", r"\bnombre\s*del\s*padre\b",
        ],
        "ta": ["தந்தையின் பெயர்", "தந்தை பெயர்"],
        "hi": ["पिता का नाम", "पिता नाम"],
        "ch": ["父亲姓名"],
    },
    "date_of_birth": {
        "fr": [
            r"\bdate\s*of\s*birth\b", r"\bd\.?\s*[o0]\.?\s*b\.?\b", r"\bbirth\s*date\b",
            r"\bdate\s*de\s*naissance\b", r"\bfecha\s*de\s*nacimiento\b",
        ],
        "ta": ["பிறந்த தேதி", "பிறந்த திகதி", "பிறந்த நாள்"],
        "hi": ["जन्म तिथि", "जन्मतिथि"],
        "ch": ["出生日期"],
    },
    "sex": {
        "fr": [r"\bsex\b", r"\bgender\b", r"\bsexe\b", r"\bsexo\b"],
        "ta": ["பாலினம்"],
        "hi": ["लिंग"],
        "ch": ["性别"],
    },
    "nationality": {
        "fr": [r"\bnationality\b", r"\bnationalit[eé]\b", r"\bnacionalidad\b"],
        "ta": ["குடியுரிமை", "நாட்டுரிமை"],
        "hi": ["राष्ट्रीयता"],
        "ch": ["国籍"],
    },
    "issue_date": {
        "fr": [
            r"\bdate\s*of\s*issue\b", r"\bissue\s*date\b", r"\bissued\s+on\b",
            r"\bdate\s*de\s*d[eé]livrance\b", r"\bfecha\s*de\s*emisi[oó]n\b",
        ],
        "ta": ["வழங்கிய தேதி"],
        "hi": ["जारी करने की तिथि", "जारी तिथि"],
        "ch": ["签发日期"],
    },
    "expiry_date": {
        "fr": [
            r"\bdate\s*of\s*expiry\b", r"\bexpiry\s*date\b", r"\bexpiration\s*date\b",
            r"\bvalid\s*(?:until|thru|till)\b",
            r"\bvalidity\s*\((?:nt|non[- ]?transport|tr|transport)\)",
            r"\bvalidity\b",
            r"\bexpires?\s+on\b", r"\bexpires?\b", r"\bvalid\s*upto\b",
            r"\bdate\s*d'?expiration\b", r"\bfecha\s*de\s*caducidad\b", r"\bfecha\s*de\s*vencimiento\b",
        ],
        "ta": ["காலாவதி தேதி", "கால முடிவு தேதி"],
        "hi": ["समाप्ति तिथि", "वैधता तिथि"],
        "ch": ["有效期至", "截止日期"],
    },
    "issuing_authority": {
        "fr": [
            r"\bissuing\s*authority\b", r"\bauthority\b",
            r"\bautorit[eé]\s*de\s*d[eé]livrance\b", r"\bautoridad\s*emisora\b",
        ],
        "ta": ["வழங்கும் அதிகாரம்"],
        "hi": ["जारीकर्ता प्राधिकरण"],
        "ch": ["签发机关"],
    },
    "address": {
        "fr": [r"\baddress\b", r"\badresse\b", r"\bdirecci[oó]n\b"],
        "ta": ["முகவரி"],
        "hi": ["पता"],
        "ch": ["地址"],
    },
    "categories": {
        "fr": [
            r"\bcategor(?:y|ies)\b", r"\bvehicle\s*class(?:es)?\b", r"\bclass(?:es)?\s*of\s*vehicle\b",
        ],
    },
}

# Family codes treated as "Latin/English-equivalent" -- used by
# field_extractor.py to decide which of two same-field matches (e.g. one
# Tamil, one English) becomes the primary value vs. the "*_native"
# evidence field. Must include lang_map.DEFAULT_LANG ("fr"), since that's
# the actual OCR family code the pipeline's Latin pass is tagged with;
# "en" is included defensively in case any caller ever tags lines that
# way directly.
LATIN_FAMILY_CODES = {"fr", "en"}


def _compile_literal(text: str) -> str:
    """Turns a plain native-script label string into a safe regex
    pattern fragment (metacharacter-escaped, no word-boundary anchors --
    see module docstring for why non-Latin scripts skip \\b)."""
    return re.escape(text)


def patterns_for(field: str) -> List[str]:
    """All label patterns for `field`, across every language currently
    registered for it in FIELD_LABELS_I18N, flattened into one list of
    regex-pattern strings ready for re.compile(..., re.IGNORECASE).
    Latin-family entries are used as-is; non-Latin literal strings are
    regex-escaped. Returns [] for a field with no entries at all."""
    per_lang = FIELD_LABELS_I18N.get(field, {})
    out: List[str] = []
    for lang_code, entries in per_lang.items():
        for entry in entries:
            out.append(entry if lang_code in LATIN_FAMILY_CODES else _compile_literal(entry))
    return out
