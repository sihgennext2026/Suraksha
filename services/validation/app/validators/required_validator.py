"""Required-field validation driven by rule configuration."""

from __future__ import annotations

from typing import Any, Dict, List


def validate_required_fields(
    fields: Dict[str, Any], required: List[str]
) -> List[Dict[str, Any]]:
    """
    Checks that each required field carries a value.

    A field that is absent is reported REVIEW, not FAIL. The rules run on what
    extraction managed to read, and an absent field has two indistinguishable
    causes: the document genuinely lacks it, or the camera and OCR could not
    recover it. Only the first is evidence against the document, and nothing
    here can tell them apart.

    Calling it FAIL conflated the two, and the cost was not theoretical: a
    genuine passport whose name, number, nationality, date of birth and expiry
    all cross-checked against its MRZ was still marked INVALID at HIGH severity
    because the issue date — which an ICAO 9303 MRZ does not carry — could not
    be read off the printed page.

    REVIEW puts it in front of the officer, which is the correct outcome for
    something the system cannot resolve on its own.
    """
    results = []
    for fname in required:
        val = fields.get(fname)
        if val is None:
            results.append(
                {
                    "metric": f"required_{fname}",
                    "status": "REVIEW",
                    "reason": (
                        f"Required field '{fname}' was not read from this document. "
                        f"Confirm it against the document itself."
                    ),
                }
            )
        elif isinstance(val, str) and not val.strip():
            results.append(
                {
                    "metric": f"required_{fname}",
                    "status": "REVIEW",
                    "reason": (
                        f"Required field '{fname}' was read as empty. "
                        f"Confirm it against the document itself."
                    ),
                }
            )
        else:
            results.append(
                {
                    "metric": f"required_{fname}",
                    "status": "PASS",
                    "reason": f"Required field '{fname}' is present",
                }
            )
    return results
