"""
String similarity and Character Error Rate (CER) utilities.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple


def normalize_text(s: Optional[str]) -> str:
    """Lowercase, strip, collapse whitespace."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def normalize_number(s: Optional[str]) -> str:
    """Remove whitespace and common separators for number comparison."""
    if s is None:
        return ""
    return re.sub(r"[\s\-]", "", str(s).strip().upper())


def levenshtein_distance(a: str, b: str) -> int:
    """Classic Levenshtein edit distance."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            ins = curr[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(ins, delete, sub))
        prev = curr
    return prev[-1]


def character_error_rate(expected: str, extracted: str) -> float:
    """
    CER = edit_distance / max(len(expected), 1)
    Range [0.0, inf) but typically [0, 1+] .
    """
    if not expected and not extracted:
        return 0.0
    if not expected:
        return 1.0
    dist = levenshtein_distance(expected, extracted)
    return dist / max(len(expected), 1)


def similarity_score(expected: str, extracted: str) -> float:
    """
    Normalized similarity = 1 - CER (clamped to [0, 1]).
    """
    cer = character_error_rate(expected, extracted)
    return max(0.0, 1.0 - cer)


def compare_text(
    expected: Optional[str],
    extracted: Optional[str],
    field_type: str = "text",
) -> Tuple[str, float, float]:
    """
    Compare two text values.
    Returns (match_type, accuracy, cer)
    match_type: exact | normalized | none
    """
    if expected is None and extracted is None:
        return "exact", 1.0, 0.0
    if expected is None or extracted is None:
        return "none", 0.0, 1.0

    exp_s = str(expected)
    ext_s = str(extracted)

    if exp_s == ext_s:
        return "exact", 1.0, 0.0

    if field_type in ("name", "text", "address"):
        if normalize_text(exp_s) == normalize_text(ext_s):
            return "normalized", 1.0, character_error_rate(
                normalize_text(exp_s), normalize_text(ext_s)
            )
    elif field_type in ("number", "license_number", "passport_number",
                        "visa_number", "national_id_number", "permit_number"):
        if normalize_number(exp_s) == normalize_number(ext_s):
            return "normalized", 1.0, 0.0

    # Partial similarity
    if field_type in ("name", "text", "address"):
        n_exp = normalize_text(exp_s)
        n_ext = normalize_text(ext_s)
        cer = character_error_rate(n_exp, n_ext)
        acc = similarity_score(n_exp, n_ext)
    else:
        cer = character_error_rate(exp_s, ext_s)
        acc = similarity_score(exp_s, ext_s)

    return "none", acc, cer
