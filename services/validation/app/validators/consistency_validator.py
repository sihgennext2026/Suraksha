"""Cross-field consistency checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


def validate_date_consistency(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    dob = fields.get("date_of_birth")
    issue = fields.get("date_of_issue")
    expiry = fields.get("date_of_expiry")

    if dob and issue:
        try:
            d_dob = datetime.strptime(str(dob), "%Y-%m-%d")
            d_issue = datetime.strptime(str(issue), "%Y-%m-%d")
            if d_issue < d_dob:
                results.append(
                    {
                        "metric": "issue_after_dob",
                        "status": "FAIL",
                        "reason": "Issue date is before date of birth",
                    }
                )
            else:
                results.append(
                    {
                        "metric": "issue_after_dob",
                        "status": "PASS",
                        "reason": "Issue date is after date of birth",
                    }
                )
        except ValueError:
            results.append(
                {
                    "metric": "issue_after_dob",
                    "status": "REVIEW",
                    "reason": "Could not parse dates for DOB/issue comparison",
                }
            )

    if issue and expiry:
        try:
            d_issue = datetime.strptime(str(issue), "%Y-%m-%d")
            d_exp = datetime.strptime(str(expiry), "%Y-%m-%d")
            if d_exp < d_issue:
                results.append(
                    {
                        "metric": "expiry_after_issue",
                        "status": "FAIL",
                        "reason": "Expiry is before issue date",
                    }
                )
            else:
                results.append(
                    {
                        "metric": "expiry_after_issue",
                        "status": "PASS",
                        "reason": "Expiry is on or after issue date",
                    }
                )
        except ValueError:
            results.append(
                {
                    "metric": "expiry_after_issue",
                    "status": "REVIEW",
                    "reason": "Could not parse dates for issue/expiry comparison",
                }
            )

    return results
