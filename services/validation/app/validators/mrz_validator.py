"""MRZ consistency validation for passports."""

from __future__ import annotations

from typing import Any, Dict, List


def validate_mrz_consistency(
    fields: Dict[str, Any], mrz: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Validate that MRZ-derived data is consistent with visible fields.
    Reported separately from extraction evaluation.
    """
    results: List[Dict[str, Any]] = []

    if not mrz:
        results.append(
            {
                "metric": "mrz_present",
                "status": "REVIEW",
                "reason": "No MRZ data available",
            }
        )
        return results

    results.append(
        {
            "metric": "mrz_present",
            "status": "PASS",
            "reason": "MRZ data is present",
        }
    )

    # Name
    vis_name = fields.get("name")
    mrz_name = mrz.get("name")
    if vis_name and mrz_name:
        v_tokens = set(str(vis_name).upper().split())
        m_tokens = set(
            t for t in str(mrz_name).upper().replace("<", " ").split() if t
        )
        if v_tokens & m_tokens:
            results.append(
                {
                    "metric": "mrz_name_match",
                    "status": "PASS",
                    "reason": "MRZ name matches visible name",
                }
            )
        else:
            results.append(
                {
                    "metric": "mrz_name_match",
                    "status": "FAIL",
                    "reason": "MRZ name does not match visible name",
                }
            )
    else:
        results.append(
            {
                "metric": "mrz_name_match",
                "status": "REVIEW",
                "reason": "Insufficient name data for MRZ comparison",
            }
        )

    # Passport number
    vis_pn = fields.get("passport_number")
    mrz_pn = mrz.get("passport_number")
    if vis_pn and mrz_pn:
        if str(vis_pn).upper().replace(" ", "") == str(mrz_pn).upper().replace(
            " ", ""
        ):
            results.append(
                {
                    "metric": "mrz_passport_number_match",
                    "status": "PASS",
                    "reason": "MRZ passport number matches",
                }
            )
        else:
            results.append(
                {
                    "metric": "mrz_passport_number_match",
                    "status": "FAIL",
                    "reason": "MRZ passport number does not match",
                }
            )
    else:
        results.append(
            {
                "metric": "mrz_passport_number_match",
                "status": "REVIEW",
                "reason": "Insufficient passport number data for MRZ comparison",
            }
        )

    # Dates
    for field in ("date_of_birth", "date_of_expiry"):
        vis = fields.get(field)
        mrz_val = mrz.get(field)
        metric = f"mrz_{field}_match"
        if vis and mrz_val:
            if str(vis) == str(mrz_val):
                results.append(
                    {
                        "metric": metric,
                        "status": "PASS",
                        "reason": f"MRZ {field} matches",
                    }
                )
            else:
                results.append(
                    {
                        "metric": metric,
                        "status": "FAIL",
                        "reason": f"MRZ {field} does not match",
                    }
                )
        else:
            results.append(
                {
                    "metric": metric,
                    "status": "REVIEW",
                    "reason": f"Insufficient {field} data for MRZ comparison",
                }
            )

    return results
