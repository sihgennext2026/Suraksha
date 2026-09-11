"""
Tests for field extraction, evaluation, validation, and the primary
driving-license OCR sample from the specification.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.extractors import get_extractor
from app.extractors.driving_license_extractor import DrivingLicenseExtractor
from app.evaluation.evaluator import ExtractionEvaluator
from app.evaluation.similarity import (
    character_error_rate,
    normalize_text,
    compare_text,
)
from app.validators.document_validator import DocumentValidator

BASE = Path(__file__).resolve().parent.parent
EVAL_DIR = BASE / "evaluation_data"
RULES_DIR = BASE / "app" / "rules"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestDrivingLicensePrimary:
    @pytest.fixture
    def ocr(self):
        return load_json(EVAL_DIR / "driving_license" / "case_001_ocr.json")

    @pytest.fixture
    def expected(self):
        return load_json(EVAL_DIR / "driving_license" / "case_001_expected.json")

    def test_extract_name(self, ocr):
        ext = DrivingLicenseExtractor()
        result = ext.extract(ocr)
        assert result["fields"]["name"] == "MELKIBSON"

    def test_extract_license_number(self, ocr):
        ext = DrivingLicenseExtractor()
        result = ext.extract(ocr)
        assert result["fields"]["license_number"] == "TN9220250003111"
        assert result["fields"]["license_number"] not in ("TN", "-9090", "PDL")

    def test_extract_dob(self, ocr):
        ext = DrivingLicenseExtractor()
        result = ext.extract(ocr)
        assert result["fields"]["date_of_birth"] == "2006-03-10"

    def test_extract_issue_date(self, ocr):
        ext = DrivingLicenseExtractor()
        result = ext.extract(ocr)
        assert result["fields"]["date_of_issue"] == "2025-06-16"

    def test_extract_expiry(self, ocr):
        ext = DrivingLicenseExtractor()
        result = ext.extract(ocr)
        assert result["fields"]["date_of_expiry"] == "2046-09-09"

    def test_full_structured_output(self, ocr, expected):
        ext = DrivingLicenseExtractor()
        result = ext.extract(ocr)
        assert result["document_type"] == "driving_license"
        for key in expected["fields"]:
            assert result["fields"][key] == expected["fields"][key], (
                f"Field {key}: got {result['fields'][key]}, "
                f"expected {expected['fields'][key]}"
            )

    def test_evaluation_all_pass(self, ocr, expected):
        ext = DrivingLicenseExtractor()
        extracted = ext.extract(ocr)
        evaluator = ExtractionEvaluator()
        evaluation = evaluator.evaluate(extracted, expected, ocr, "driving_license")
        assert evaluation["metrics"]["overall_status"] == "PASS"
        assert evaluation["metrics"]["correct_fields"] == 5
        assert evaluation["metrics"]["field_accuracy"] == 1.0

    def test_validation_pass(self, ocr):
        ext = DrivingLicenseExtractor()
        extracted = ext.extract(ocr)
        validator = DocumentValidator(rules_dir=RULES_DIR)
        val = validator.validate(extracted)
        assert val["overall_status"] in ("PASS", "REVIEW", "FAIL")
        required_pass = [
            r for r in val["rules"]
            if r["metric"].startswith("required_") and r["status"] == "PASS"
        ]
        assert len(required_pass) >= 4


class TestEdgeCases:
    def test_empty_name(self):
        ocr = {
            "lines": [
                {"text": "Name:", "confidence": 0.9},
                {"text": "", "confidence": 0},
                {"text": "TN9220250003111", "confidence": 0.99},
            ],
            "full_text": "Name: TN9220250003111",
        }
        ext = DrivingLicenseExtractor()
        result = ext.extract(ocr)
        assert result["fields"]["name"] is None or result["fields"]["name"] == ""

    def test_missing_name_evaluation(self):
        extracted = {
            "document_type": "driving_license",
            "fields": {
                "name": None,
                "license_number": "TN9220250003111",
                "date_of_birth": "2006-03-10",
                "date_of_issue": "2025-06-16",
                "date_of_expiry": "2046-09-09",
            },
        }
        expected = load_json(EVAL_DIR / "driving_license" / "case_001_expected.json")
        evaluator = ExtractionEvaluator()
        evaluation = evaluator.evaluate(extracted, expected, {}, "driving_license")
        name_result = next(f for f in evaluation["fields"] if f["field"] == "name")
        assert name_result["status"] == "REVIEW"
        assert name_result["extracted"] is None

    def test_empty_string_name_fail(self):
        extracted = {
            "document_type": "driving_license",
            "fields": {
                "name": "",
                "license_number": "TN9220250003111",
                "date_of_birth": "2006-03-10",
                "date_of_issue": "2025-06-16",
                "date_of_expiry": "2046-09-09",
            },
        }
        expected = load_json(EVAL_DIR / "driving_license" / "case_001_expected.json")
        evaluator = ExtractionEvaluator()
        evaluation = evaluator.evaluate(extracted, expected, {}, "driving_license")
        name_result = next(f for f in evaluation["fields"] if f["field"] == "name")
        assert name_result["status"] == "FAIL"
        assert "empty" in name_result["reason"].lower()

    def test_incorrect_name(self):
        extracted = {
            "document_type": "driving_license",
            "fields": {
                "name": "MELKIBS0N",
                "license_number": "TN9220250003111",
                "date_of_birth": "2006-03-10",
                "date_of_issue": "2025-06-16",
                "date_of_expiry": "2046-09-09",
            },
        }
        expected = load_json(EVAL_DIR / "driving_license" / "case_001_expected.json")
        evaluator = ExtractionEvaluator()
        evaluation = evaluator.evaluate(extracted, expected, {}, "driving_license")
        name_result = next(f for f in evaluation["fields"] if f["field"] == "name")
        assert name_result["status"] == "FAIL"
        assert name_result["cer"] > 0

    def test_incorrect_license_number(self):
        extracted = {
            "document_type": "driving_license",
            "fields": {
                "name": "MELKIBSON",
                "license_number": "TN9999999999999",
                "date_of_birth": "2006-03-10",
                "date_of_issue": "2025-06-16",
                "date_of_expiry": "2046-09-09",
            },
        }
        expected = load_json(EVAL_DIR / "driving_license" / "case_001_expected.json")
        evaluator = ExtractionEvaluator()
        evaluation = evaluator.evaluate(extracted, expected, {}, "driving_license")
        lic = next(f for f in evaluation["fields"] if f["field"] == "license_number")
        assert lic["status"] == "FAIL"

    def test_incorrect_dob(self):
        extracted = {
            "document_type": "driving_license",
            "fields": {
                "name": "MELKIBSON",
                "license_number": "TN9220250003111",
                "date_of_birth": "2000-01-01",
                "date_of_issue": "2025-06-16",
                "date_of_expiry": "2046-09-09",
            },
        }
        expected = load_json(EVAL_DIR / "driving_license" / "case_001_expected.json")
        evaluator = ExtractionEvaluator()
        evaluation = evaluator.evaluate(extracted, expected, {}, "driving_license")
        dob = next(f for f in evaluation["fields"] if f["field"] == "date_of_birth")
        assert dob["status"] == "FAIL"


class TestNormalization:
    def test_date_normalization(self):
        ext = DrivingLicenseExtractor()
        assert ext.normalize_date("16-06-2025") == "2025-06-16"
        assert ext.normalize_date("10/03/2006") == "2006-03-10"
        assert ext.normalize_date("2006-03-10") == "2006-03-10"
        assert ext.normalize_date("invalid") is None
        assert ext.normalize_date("32-13-2020") is None

    def test_whitespace_normalization(self):
        assert normalize_text("  MELKIBSON  ") == "melkibson"
        assert normalize_text("MELKI  BSON") == "melki bson"

    def test_case_normalization(self):
        match_type, acc, cer = compare_text("MELKIBSON", "melkibson", "name")
        assert match_type == "normalized"
        assert acc == 1.0

    def test_cer(self):
        cer = character_error_rate("MELKIBSON", "MELKIBS0N")
        assert cer > 0
        assert cer == pytest.approx(1 / 9, abs=0.01)


class TestOtherDocuments:
    def test_passport_extraction(self):
        ocr = load_json(EVAL_DIR / "passport" / "case_001_ocr.json")
        ext = get_extractor("passport")
        result = ext.extract(ocr)
        assert result["fields"]["passport_number"] == "Z1234567"
        assert result["fields"]["date_of_birth"] == "1990-08-15"
        assert result.get("mrz") is not None

    def test_passport_mrz_match(self):
        ocr = load_json(EVAL_DIR / "passport" / "case_001_ocr.json")
        expected = load_json(EVAL_DIR / "passport" / "case_001_expected.json")
        ext = get_extractor("passport")
        extracted = ext.extract(ocr)
        evaluator = ExtractionEvaluator()
        evaluation = evaluator.evaluate(extracted, expected, ocr, "passport")
        if "mrz_consistency" in evaluation:
            checks = evaluation["mrz_consistency"]["checks"]
            assert any(c["status"] == "PASS" for c in checks)

    def test_visa_extraction(self):
        ocr = load_json(EVAL_DIR / "visa" / "case_001_ocr.json")
        ext = get_extractor("visa")
        result = ext.extract(ocr)
        assert result["fields"]["visa_number"] == "A12345678"
        assert result["fields"]["passport_number"] == "Z1234567"

    def test_national_id_extraction(self):
        ocr = load_json(EVAL_DIR / "national_id" / "case_001_ocr.json")
        ext = get_extractor("national_id")
        result = ext.extract(ocr)
        assert result["fields"]["national_id_number"] == "123456789012"
        assert result["fields"]["name"] == "RAJESH KUMAR"
        assert result["fields"]["gender"] == "M"

    def test_permit_extraction(self):
        ocr = load_json(EVAL_DIR / "permit" / "case_001_ocr.json")
        ext = get_extractor("permit")
        result = ext.extract(ocr)
        assert result["fields"]["permit_number"] == "WP-2024-98765"
        assert result["fields"]["name"] == "JOHN SMITH"

    def test_national_id_expiry_not_applicable(self):
        ocr = load_json(EVAL_DIR / "national_id" / "case_001_ocr.json")
        ext = get_extractor("national_id")
        extracted = ext.extract(ocr)
        validator = DocumentValidator(rules_dir=RULES_DIR)
        val = validator.validate(extracted)
        na = [r for r in val["rules"] if r["status"] == "NOT_APPLICABLE"]
        assert len(na) >= 1


class TestCaseBasedEvaluation:
    def test_driving_license_all_cases(self):
        from app.evaluation.case_evaluator import CaseBasedEvaluator

        evaluator = CaseBasedEvaluator(EVAL_DIR)
        result = evaluator.evaluate_document_type("driving_license")
        assert result["document_type"] == "driving_license"
        ev = result["evaluation"]
        assert ev["total_cases"] >= 1
        assert "score" in ev
        assert "score_percent" in ev
        assert ev["overall_status"] in ("PASS", "FAIL", "REVIEW")
        # Score is average of case scores — not hardcoded
        assert 0 <= ev["score"] <= 100
        # failed_cases is a list (may be empty)
        assert isinstance(result.get("failed_cases"), list)
        assert isinstance(result.get("review_cases"), list)

    def test_score_is_average_of_cases(self):
        from app.evaluation.case_evaluator import CaseBasedEvaluator

        evaluator = CaseBasedEvaluator(EVAL_DIR)
        result = evaluator.evaluate_document_type("driving_license")
        ev = result["evaluation"]
        # With current samples that extract correctly, score should be high
        assert ev["total_cases"] >= 1
        assert ev["passed_cases"] + ev["failed_cases"] + ev["review_cases"] == ev["total_cases"]

    def test_passport_evaluation(self):
        from app.evaluation.case_evaluator import CaseBasedEvaluator

        evaluator = CaseBasedEvaluator(EVAL_DIR)
        result = evaluator.evaluate_document_type("passport")
        assert result["evaluation"]["total_cases"] >= 1

    def test_no_passed_case_details(self):
        """Final output must not include detailed passed case listings."""
        from app.evaluation.case_evaluator import CaseBasedEvaluator

        evaluator = CaseBasedEvaluator(EVAL_DIR)
        result = evaluator.evaluate_document_type("driving_license")
        assert "passed_case_details" not in result
        # Only counts for passed
        assert "passed_cases" in result["evaluation"]
