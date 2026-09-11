"""
lang_map.py

Internal-only: maps the 3-letter country code found in MRZ line 1 to the
ISO-style language code PP-OCRv5 needs (via PaddleOCR's `lang` param) to
correctly read this document's VISIBLE FIELD text (not the MRZ itself,
which is always printed in Latin/OCR-B per ICAO 9303, regardless of the
document's issuing country or script).

IMPORTANT: PaddleOCR's `lang` parameter takes a specific ISO-style code
(e.g. "hi", "ar", "ru"), NOT a family name like "devanagari" or "arabic".
Internally it groups many codes into one shared family model -- e.g. any
of "hi", "mr", "ne" all resolve to the same Devanagari recognition model
-- so any single representative code from a family is enough to select
that family's model.

This is a lookup for OCR ENGINE SELECTION only. It reads a fixed-position
substring out of raw MRZ text -- it does not parse, validate, checksum,
or decode any MRZ field. Full MRZ decoding/comparison against the
document's visible fields is owned entirely by a separate module
downstream of this API; this file's output never appears in that logic.

COVERAGE NOTE: this table intentionally does NOT enumerate Latin-script
countries. PP-OCRv5's Latin family already covers 40+ languages
(Western/Central/Eastern European, Turkic-Latin, Southeast-Asian-Latin,
etc.) under one shared model, so any country not listed below correctly
falls through to DEFAULT_LANG rather than needing an explicit entry.
What this table DOES need to enumerate exhaustively is every country
whose official script is NOT Latin -- that's the part a missing entry
would actually break.

Known gaps (PP-OCRv5 does not ship a model for these scripts at all --
no country-code entry can fix this): Hebrew, Ge'ez/Ethiopic, Myanmar,
Khmer, Lao, Georgian, Armenian. Documents in these scripts will only
extract whatever Latin-script text is co-printed alongside them.

Tamil and Telugu are NOT in that gap list -- PP-OCRv5 ships dedicated
models for both (ta_PP-OCRv5_mobile_rec, te_PP-OCRv5_mobile_rec). They
just aren't tied to any single MRZ country code (see
ADDITIONAL_RACE_FAMILIES below) since no ICAO country code maps
1:1 to an Indian state's script.
"""

COUNTRY_TO_LANG = {
    # Devanagari script family ("hi" is the representative code -- also
    # covers Marathi, Nepali under the same shared model)
    "IND": "hi", "NPL": "hi",

    # Arabic script family ("ar"). Per PP-OCRv5's own family grouping this
    # covers Arabic, Persian, Uyghur, and Urdu -- so it's correct for
    # Persian-issuing (IRN, AFG) and Urdu-issuing (PAK) countries too, not
    # just Arabic-language ones.
    "AFG": "ar", "ARE": "ar", "BHR": "ar", "DZA": "ar", "EGY": "ar",
    "IRN": "ar", "IRQ": "ar", "JOR": "ar", "KWT": "ar", "LBN": "ar",
    "LBY": "ar", "MAR": "ar", "OMN": "ar", "PAK": "ar", "PSE": "ar",
    "QAT": "ar", "SAU": "ar", "SDN": "ar", "SOM": "ar", "SYR": "ar",
    "TUN": "ar", "YEM": "ar",

    # Cyrillic-script countries. Deliberately limited to the codes
    # PP-OCRv5's docs explicitly confirm ("ru", "uk", "bg") plus "be"
    # (carried over from the original table). NOT extended to other
    # genuinely-Cyrillic countries (Serbia, Kazakhstan, Mongolia,
    # Kyrgyzstan, Tajikistan, North Macedonia) because I couldn't verify
    # a working PaddleOCR `lang` code for them -- a wrong guess here
    # fails at model-load time, not gracefully. Check
    # https://www.paddleocr.ai (PP-OCRv5 multilingual page, section 4)
    # before adding any of those.
    "RUS": "ru", "UKR": "uk", "BLR": "be", "BGR": "bg",

    # CJK / Japanese -- "ch" is the shared default family (explicit
    # mobile-model pin lives in ocr.py's DocumentOCR._build_engine, to
    # dodge the ~130s/image PP-OCRv5 server model).
    "CHN": "ch", "TWN": "ch", "HKG": "ch", "MAC": "ch", "JPN": "ch",

    # Individually-modeled families -- literal codes PP-OCRv5 recognizes
    # directly, not representative picks from a shared group.
    "KOR": "korean", "PRK": "korean",
    "THA": "th",
    "GRC": "el",
    "CYP": "el",  # Cyprus: Greek/English bilingual in practice; "el" catches the Greek side
    "TUR": "tr",  # Turkish IS Latin-script; "tr" just resolves into the Latin family model
}

# Scripts that exist WITHIN a single MRZ country code's territory but
# can't be disambiguated by that code alone -- MRZ line 1 only ever
# reports "IND", never which state (and therefore which official script)
# actually issued the document. COUNTRY_TO_LANG's "IND": "hi" above stays
# the best single guess when an MRZ is present and valid (Hindi/
# Devanagari is India's most common script, and Indian passports print
# Hindi/English nationally regardless of state), but state-issued
# documents without an MRZ (driving licenses, state IDs) are exactly
# where this matters: Tamil Nadu issues in Tamil, Andhra Pradesh/
# Telangana in Telugu, etc. Devanagari cannot read Tamil or Telugu text
# at all -- it's a different script, not a close-enough approximation.
#
# These are deliberately NOT added as COUNTRY_TO_LANG entries (there's no
# country code to tie them to), but ARE added to the confidence-race
# candidate pool below, so app/lang_fallback.py's Step 3 race (used for
# exactly this MRZ-less case) gets a real chance at them instead of the
# family being structurally unreachable.
ADDITIONAL_RACE_FAMILIES = ["ta", "te"]  # Tamil, Telugu -- both real,
# separate PP-OCRv5 model families (ta_PP-OCRv5_mobile_rec,
# te_PP-OCRv5_mobile_rec), not sub-variants of "hi"/Devanagari.

# WORK 2 (Tamil OCR fix): India has no single national script for
# state-issued documents (driving licences, non-ICAO national IDs like
# Aadhaar) -- MRZ/header country code "IND" alone cannot tell you
# whether the document is Devanagari, Tamil, or Telugu. This is the
# small candidate pool app/lang_fallback.py races over specifically when
# it sees country == "IND" from header detection, instead of assuming
# "hi" outright (see the "header_india_script_race" branch there for why
# that assumption was silently breaking Tamil recognition). "hi" stays
# first since it IS the most common case; the race still gives ta/te a
# real, fast shot instead of being unreachable.
INDIA_SCRIPT_CANDIDATES = ["hi"] + ADDITIONAL_RACE_FAMILIES  # ["hi", "ta", "te"]

# "fr" is a representative pick from the Latin-script family -- any
# Latin-script code (de, es, it, nl, pl, pt, tr, ...) resolves to the
# same shared model. This is the correct answer (not just a fallback)
# for the large majority of ICAO member states, and is also the
# naturally correct choice for International Driving Permits, which
# print in Latin script by Geneva Convention design.
DEFAULT_LANG = "fr"

# Every distinct family code this table actively routes to, used by
# app/lang_fallback.py as the candidate universe for its confidence-race
# fallback step (MRZ absent/invalid AND header text inconclusive).
#
# WORK 2 BUGFIX: this list used to be [DEFAULT_LANG] + everything else
# sorted alphabetically. That silently doomed Tamil: alphabetically "ta"
# sits behind "ar", "be", "bg", "ch", "el" -- past
# config.CONFIDENCE_RACE_MAX_CANDIDATES (6) -- so app/lang_fallback.py's
# Step-3 confidence race could NEVER actually reach the Tamil family,
# regardless of image content, even though ADDITIONAL_RACE_FAMILIES was
# already (correctly) included in the underlying set. DEFAULT_LANG and
# INDIA_SCRIPT_CANDIDATES are now placed first -- both because this
# pipeline's primary deployment target is Indian identity documents, and
# so ta/te are always well inside the candidate cap -- with every
# remaining family following in the same alphabetical order as before.
_priority_families = [DEFAULT_LANG] + INDIA_SCRIPT_CANDIDATES
_remaining_families = sorted(
    (set(COUNTRY_TO_LANG.values()) | set(ADDITIONAL_RACE_FAMILIES)) - set(_priority_families)
)
ALL_LANG_FAMILIES = _priority_families + _remaining_families


def peek_country_code(mrz_line1: str) -> str:
    """Reads the issuing-country substring at its fixed MRZ position
    (characters 3-5 of line 1 in a TD3/passport MRZ; same offset for
    TD1/TD2). Raw character slice for engine selection only -- not a
    decode, no structure/checksum validation performed here."""
    if not mrz_line1 or len(mrz_line1) < 5:
        return ""
    return mrz_line1[2:5].replace("<", "").strip().upper()


def lang_for_mrz_line1(mrz_line1: str) -> str:
    """Returns the PaddleOCR `lang` code for this document's visible
    fields, based on the MRZ's issuing-country code. Falls back to
    DEFAULT_LANG if the code is missing, blank, or not yet mapped.

    NOTE: main.py no longer calls this directly for field-language
    routing -- app/lang_fallback.py validates the MRZ's format first and
    calls peek_country_code() itself, since this MRZ-only path can't
    handle document types with no MRZ at all (driving licenses, IDPs,
    Aadhaar, many visas). Kept here for anything else that still wants a
    one-shot MRZ->lang lookup."""
    code = peek_country_code(mrz_line1)
    if not code:
        return DEFAULT_LANG
    return COUNTRY_TO_LANG.get(code, DEFAULT_LANG)
