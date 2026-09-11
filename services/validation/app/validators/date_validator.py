"""Date field validation rules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def validate_date_present(field_name: str, value: Any) -> Dict[str, Any]:
    """
    Reports whether a date was read.

    A date that is absent is REVIEW rather than FAIL, for the same reason as an
    absent required field: the rules see only what extraction recovered, and a
    date the OCR could not read is not evidence that the document is wrong. The
    format and ordering checks in this module already treat an absent date this
    way ("not available for comparison"); this makes the presence check
    consistent with them.
    """
    if value is None:
        return {
            "metric": field_name,
            "status": "REVIEW",
            "reason": f"{field_name} was not read from this document",
        }
    if isinstance(value, str) and not value.strip():
        return {
            "metric": field_name,
            "status": "REVIEW",
            "reason": f"{field_name} was read as empty",
        }
    return {
        "metric": field_name,
        "status": "PASS",
        "reason": f"{field_name} is present",
    }


def validate_date_format(field_name: str, value: Any) -> Dict[str, Any]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return {
            "metric": f"{field_name}_format",
            "status": "REVIEW",
            "reason": f"{field_name} not available for format check",
        }
    try:
        datetime.strptime(str(value).strip(), "%Y-%m-%d")
        return {
            "metric": f"{field_name}_format",
            "status": "PASS",
            "reason": f"{field_name} has valid YYYY-MM-DD format",
        }
    except ValueError:
        return {
            "metric": f"{field_name}_format",
            "status": "FAIL",
            "reason": f"{field_name} is not a valid YYYY-MM-DD date",
        }


def validate_date_not_future(field_name: str, value: Any) -> Dict[str, Any]:
    """For DOB / issue dates — should not be in the far future."""
    if value is None:
        return {
            "metric": f"{field_name}_not_future",
            "status": "REVIEW",
            "reason": f"{field_name} not available",
        }
    try:
        dt = datetime.strptime(str(value).strip(), "%Y-%m-%d")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if dt > now:
            return {
                "metric": f"{field_name}_not_future",
                "status": "FAIL",
                "reason": f"{field_name} is in the future",
            }
        return {
            "metric": f"{field_name}_not_future",
            "status": "PASS",
            "reason": f"{field_name} is not in the future",
        }
    except ValueError:
        return {
            "metric": f"{field_name}_not_future",
            "status": "FAIL",
            "reason": f"{field_name} is not a valid date",
        }


def validate_expiry_after_issue(
    issue: Any, expiry: Any
) -> Dict[str, Any]:
    if issue is None or expiry is None:
        return {
            "metric": "expiry_after_issue",
            "status": "REVIEW",
            "reason": "Issue or expiry date not available for comparison",
        }
    try:
        di = datetime.strptime(str(issue).strip(), "%Y-%m-%d")
        de = datetime.strptime(str(expiry).strip(), "%Y-%m-%d")
        if de >= di:
            return {
                "metric": "expiry_after_issue",
                "status": "PASS",
                "reason": "Expiry date is on or after issue date",
            }
        return {
            "metric": "expiry_after_issue",
            "status": "FAIL",
            "reason": "Expiry date is before issue date",
        }
    except ValueError:
        return {
            "metric": "expiry_after_issue",
            "status": "FAIL",
            "reason": "Invalid date format for issue/expiry comparison",
        }


def validate_dob_reasonable(value: Any) -> Dict[str, Any]:
    if value is None:
        return {
            "metric": "dob_reasonable",
            "status": "REVIEW",
            "reason": "Date of birth not available",
        }
    try:
        dt = datetime.strptime(str(value).strip(), "%Y-%m-%d")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        age_years = (now - dt).days / 365.25
        if age_years < 0:
            return {
                "metric": "dob_reasonable",
                "status": "FAIL",
                "reason": "Date of birth is in the future",
            }
        if age_years > 120:
            return {
                "metric": "dob_reasonable",
                "status": "FAIL",
                "reason": "Date of birth implies age over 120 years",
            }
        return {
            "metric": "dob_reasonable",
            "status": "PASS",
            "reason": "Date of birth is within a reasonable range",
        }
    except ValueError:
        return {
            "metric": "dob_reasonable",
            "status": "FAIL",
            "reason": "Date of birth is not a valid date",
        }


def validate_not_expired(value: Any) -> Dict[str, Any]:
    """
    Whether the document is still in date.

    This is the one date rule that is genuinely about the document rather than
    about how well it was read: an expiry date in the past is a fact the officer
    must act on, and it is stated by the document itself. An expiry that cannot
    be read stays REVIEW — not knowing whether a document has expired is not the
    same as knowing it has.

    Expiry is inclusive: a document is valid through the whole of its expiry
    date, so only a date strictly before today is expired.
    """
    if value is None or (isinstance(value, str) and not str(value).strip()):
        return {
            "metric": "not_expired",
            "status": "REVIEW",
            "reason": "Expiry date was not read, so validity could not be checked",
        }
    try:
        expiry = datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return {
            "metric": "not_expired",
            "status": "REVIEW",
            "reason": "Expiry date is not a readable date, so validity could not be checked",
        }

    today = datetime.now(timezone.utc).date()
    if expiry < today:
        days = (today - expiry).days
        return {
            "metric": "not_expired",
            "status": "FAIL",
            "reason": f"Document expired on {expiry.isoformat()} ({days} days ago)",
        }
    return {
        "metric": "not_expired",
        "status": "PASS",
        "reason": f"Document is valid until {expiry.isoformat()}",
    }
