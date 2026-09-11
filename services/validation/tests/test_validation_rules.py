"""
Rule semantics that must not regress.

The distinction these cover is the one the whole screening contract rests on:
a field that was never read is not evidence against the document. Extraction
recovers what the camera and OCR allow, and a rule that treats an unread field
as a failure turns a poor photograph into a fraud finding.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.validators.date_validator import (  # noqa: E402
    validate_date_present,
    validate_not_expired,
)
from app.validators.required_validator import validate_required_fields  # noqa: E402


class TestUnreadFieldsAreNotFailures:
    def test_a_missing_required_field_is_inconclusive_not_a_failure(self):
        [result] = validate_required_fields({}, ["date_of_issue"])

        # A genuine passport whose issue date could not be read off the page
        # used to be marked INVALID at HIGH severity for exactly this.
        assert result["status"] == "REVIEW"
        assert "not read" in result["reason"]

    def test_an_empty_required_field_is_also_inconclusive(self):
        [result] = validate_required_fields({"name": "   "}, ["name"])
        assert result["status"] == "REVIEW"

    def test_a_field_that_was_read_still_passes(self):
        [result] = validate_required_fields({"name": "HUSEYNLI, ORKHAN"}, ["name"])
        assert result["status"] == "PASS"

    def test_a_missing_date_is_inconclusive(self):
        assert validate_date_present("date_of_issue", None)["status"] == "REVIEW"
        assert validate_date_present("date_of_issue", "  ")["status"] == "REVIEW"

    def test_a_present_date_passes(self):
        assert validate_date_present("date_of_birth", "1975-03-15")["status"] == "PASS"


class TestExpiry:
    def test_a_document_past_its_expiry_fails(self):
        expired = (date.today() - timedelta(days=1)).isoformat()
        result = validate_not_expired(expired)

        # This is a fact stated by the document, so it is a genuine finding.
        assert result["status"] == "FAIL"
        assert expired in result["reason"]

    def test_a_document_expiring_today_is_still_valid(self):
        # Validity runs through the whole of the expiry date.
        result = validate_not_expired(date.today().isoformat())
        assert result["status"] == "PASS"

    def test_a_future_expiry_passes(self):
        future = (date.today() + timedelta(days=365)).isoformat()
        assert validate_not_expired(future)["status"] == "PASS"

    def test_an_unread_expiry_is_inconclusive_not_expired(self):
        # Not knowing whether a document has expired is not the same as
        # knowing that it has.
        assert validate_not_expired(None)["status"] == "REVIEW"
        assert validate_not_expired("")["status"] == "REVIEW"

    def test_an_unreadable_expiry_is_inconclusive(self):
        assert validate_not_expired("not-a-date")["status"] == "REVIEW"


class TestNoRuleFailsOnAbsence:
    """
    The invariant behind every rule above: a capture the camera could not read
    is never evidence against the document. Only a value that was read and is
    wrong, or a fact the document itself states, may FAIL.
    """

    def test_a_whitespace_only_value_is_inconclusive_not_a_failure(self):
        from app.validators.format_validator import validate_required_string

        assert validate_required_string("name", "   ")["status"] == "REVIEW"
        assert validate_required_string("name", None)["status"] == "REVIEW"
        assert validate_required_string("name", "RAVI")["status"] == "PASS"

    def test_no_validator_returns_fail_for_an_absent_value(self):
        import inspect
        from app.validators import date_validator, format_validator, required_validator

        for module in (date_validator, format_validator):
            for name, fn in inspect.getmembers(module, inspect.isfunction):
                if not name.startswith("validate_"):
                    continue
                params = list(inspect.signature(fn).parameters)
                args = ["field"] * (len(params) - 1) + [None]
                result = fn(*args) if len(params) > 1 else fn(None)
                statuses = result if isinstance(result, list) else [result]
                for entry in statuses:
                    assert entry["status"] != "FAIL", f"{module.__name__}.{name} failed on None"
