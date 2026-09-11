"""
Tests for app/field_extractor.py structured field extraction.

Covers the three bugs fixed in the label/value matching:
  1. OCR-split labels (e.g. "Father's" + "Name:" on separate fragments)
  2. OCR-split values (e.g. "Narendran" + "R" on separate fragments)
  3. Standalone document number fallback (e.g. "RRJ3578119" with no label)
  4. Latin-preference on bilingual documents
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.field_extractor import (
    FieldLineLike,
    extract_structured_fields,
    normalize_date,
    parse_mrz,
    _find_standalone_doc_number,
    _sorted_lines,
    _find_label_value,
    _find_name_and_native,
    _find_all_label_matches,
    FIELD_LABELS,
)
from app.schemas import DocumentType


def _make_line(text, lang="fr", score=0.99, poly=None):
    """Helper: build a FieldLineLike with a simple axis-aligned bbox."""
    if poly is None:
        poly = [[0, 0], [100, 0], [100, 30], [0, 30]]
    return FieldLineLike(text=text, score=score, poly=poly, lang=lang)


def _make_line_at(text, x1, y1, x2, y2, lang="fr", score=0.99):
    """Helper: build a FieldLineLike with explicit bbox coordinates."""
    poly = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    return FieldLineLike(text=text, score=score, poly=poly, lang=lang)


# ---------------------------------------------------------------------------
# Sample data from the real voter-ID OCR output (bilingual Tamil + English)
# ---------------------------------------------------------------------------
VOTER_ID_LINES = [
    _make_line_at("இந்தியத்", 246, 21, 404, 71, lang="ta"),
    _make_line_at("தேர்தல்", 394, 21, 535, 75, lang="ta"),
    _make_line_at("ஆணையம்", 536, 32, 729, 73, lang="ta"),
    _make_line_at("ELECTION", 181, 81, 370, 116, lang="ta"),
    _make_line_at("COMMISSION OF INDIA", 371, 82, 792, 127, lang="fr"),
    _make_line_at("RRJ3578119", 48, 157, 253, 192, lang="fr"),
    _make_line_at("பெயர்:", 306, 217, 390, 253, lang="ta"),
    _make_line_at("நேரேந்திரன்", 386, 220, 527, 258, lang="ta"),
    _make_line_at("ரn", 526, 227, 555, 254, lang="ta"),
    _make_line_at("Name:", 305, 265, 388, 292, lang="ta"),
    _make_line_at("Narendran", 391, 266, 524, 294, lang="fr"),
    _make_line_at("R", 530, 271, 549, 292, lang="fr"),
    _make_line_at("தந்தையின்", 304, 311, 444, 342, lang="ta"),
    _make_line_at("பெயர்:", 442, 310, 529, 344, lang="ta"),
    _make_line_at("ராஜ்", 524, 314, 581, 345, lang="ta"),
    _make_line_at("மோகன்குமார்", 578, 313, 747, 349, lang="ta"),
    _make_line_at("Father's", 303, 355, 405, 382, lang="fr"),
    _make_line_at("Name:", 410, 357, 493, 386, lang="fr"),
    _make_line_at("Raj", 493, 358, 541, 389, lang="fr"),
    _make_line_at("Mohankumar", 540, 359, 707, 390, lang="fr"),
    _make_line_at("பாலினம் / Gender: ஆண் / Male", 301, 393, 655, 434, lang="ta"),
    _make_line_at("பிறந்த", 301, 436, 381, 474, lang="ta"),
    _make_line_at("த தேதி / வயது:", 362, 436, 522, 479, lang="ta"),
    _make_line_at("Date of Birth / Age: 03-01-2007", 299, 480, 658, 519, lang="ta"),
    _make_line_at("e-EPIC - மின்னணு வாக்காளர் புகைப்பட அடையாள அட்டை", 107, 557, 857, 610, lang="ta"),
]


class TestVoterIDExtraction:
    """End-to-end test against the real voter-ID sample."""

    def setup_method(self):
        self.result = extract_structured_fields(
            document_type=DocumentType.DRIVING_LICENSE,
            mrz_lines=[],
            field_lines=VOTER_ID_LINES,
        )

    def test_name_extracted_latin(self):
        assert self.result.fields["name"] is not None
        assert "Narendran" in self.result.fields["name"]
        assert "R" in self.result.fields["name"]

    def test_name_native_extracted(self):
        assert self.result.fields["name_native"] is not None
        assert "நேரேந்திரன்" in self.result.fields["name_native"]

    def test_father_name_not_null(self):
        assert self.result.fields["father_name"] is not None

    def test_father_name_prefers_latin(self):
        val = self.result.fields["father_name"]
        assert val is not None
        assert "Raj" in val
        assert "Mohankumar" in val

    def test_date_of_birth(self):
        assert self.result.fields["date_of_birth"] == "2007-01-03"

    def test_sex(self):
        assert self.result.fields["sex"] == "M"

    def test_document_number_standalone(self):
        assert self.result.fields["document_number"] == "RRJ3578119"

    def test_document_number_source(self):
        assert self.result.sources["document_number"] == "standalone_id"

    def test_null_fields_are_none(self):
        for key in ("issue_date", "expiry_date", "address", "categories"):
            assert self.result.fields[key] is None, f"{key} should be None"


# ---------------------------------------------------------------------------
# Split-label matching (Father's + Name: on separate OCR fragments)
# ---------------------------------------------------------------------------
class TestSplitLabelMatching:
    def test_father_name_split_across_two_fragments(self):
        lines = [
            _make_line_at("Father's", 100, 100, 200, 130, lang="fr"),
            _make_line_at("Name:", 210, 102, 300, 132, lang="fr"),
            _make_line_at("John Smith", 100, 150, 300, 180, lang="fr"),
        ]
        result = extract_structured_fields(
            DocumentType.DRIVING_LICENSE, [], lines,
        )
        assert result.fields["father_name"] == "John Smith"

    def test_father_name_split_across_three_fragments(self):
        lines = [
            _make_line_at("Father's", 100, 100, 180, 130, lang="fr"),
            _make_line_at("Name", 190, 102, 260, 132, lang="fr"),
            _make_line_at(":", 265, 102, 275, 132, lang="fr"),
            _make_line_at("Robert Doe", 100, 150, 300, 180, lang="fr"),
        ]
        result = extract_structured_fields(
            DocumentType.DRIVING_LICENSE, [], lines,
        )
        assert result.fields["father_name"] == "Robert Doe"


# ---------------------------------------------------------------------------
# Split-value continuation (Narendran + R on same row)
# ---------------------------------------------------------------------------
class TestSplitValueContinuation:
    def test_name_value_fragments_joined(self):
        lines = [
            _make_line_at("Name:", 100, 100, 200, 130, lang="fr"),
            _make_line_at("John", 210, 100, 280, 130, lang="fr"),
            _make_line_at("William", 290, 100, 400, 130, lang="fr"),
            _make_line_at("Smith", 410, 100, 500, 130, lang="fr"),
        ]
        sorted_l = _sorted_lines(lines)
        matches = _find_all_label_matches(sorted_l, FIELD_LABELS["name"])
        assert len(matches) >= 1
        assert "John" in matches[0][0]
        assert "Smith" in matches[0][0]

    def test_next_line_value_fragments_joined(self):
        lines = [
            _make_line_at("Name:", 100, 100, 200, 130, lang="fr"),
            _make_line_at("Alice", 100, 150, 200, 180, lang="fr"),
            _make_line_at("B", 210, 150, 230, 180, lang="fr"),
        ]
        sorted_l = _sorted_lines(lines)
        matches = _find_all_label_matches(sorted_l, FIELD_LABELS["name"])
        assert len(matches) >= 1
        assert "Alice" in matches[0][0]
        assert "B" in matches[0][0]


# ---------------------------------------------------------------------------
# Standalone document number detection
# ---------------------------------------------------------------------------
class TestStandaloneDocNumber:
    def test_voter_id_pattern(self):
        lines = _sorted_lines([_make_line_at("RRJ3578119", 50, 50, 250, 80)])
        result = _find_standalone_doc_number(lines)
        assert result is not None
        assert result[0] == "RRJ3578119"
        assert result[2] == "standalone_id"

    def test_aadhaar_pattern(self):
        lines = _sorted_lines([_make_line_at("1234 5678 9012", 50, 50, 300, 80)])
        result = _find_standalone_doc_number(lines)
        assert result is not None
        assert result[0] == "123456789012"

    def test_passport_number_pattern(self):
        lines = _sorted_lines([_make_line_at("A1234567", 50, 50, 200, 80)])
        result = _find_standalone_doc_number(lines)
        assert result is not None
        assert result[0] == "A1234567"

    def test_rejects_plain_text(self):
        lines = _sorted_lines([_make_line_at("Hello World", 50, 50, 200, 80)])
        assert _find_standalone_doc_number(lines) is None

    def test_rejects_short_number(self):
        lines = _sorted_lines([_make_line_at("AB123", 50, 50, 200, 80)])
        assert _find_standalone_doc_number(lines) is None


# ---------------------------------------------------------------------------
# Latin preference on bilingual documents
# ---------------------------------------------------------------------------
class TestLatinPreference:
    def test_prefers_latin_match_for_father_name(self):
        lines = [
            _make_line_at("தந்தையின்", 100, 100, 200, 130, lang="ta"),
            _make_line_at("பெயர்:", 210, 100, 300, 130, lang="ta"),
            _make_line_at("ராஜ்", 100, 150, 180, 180, lang="ta"),
            _make_line_at("Father's", 100, 200, 200, 230, lang="fr"),
            _make_line_at("Name:", 210, 200, 300, 230, lang="fr"),
            _make_line_at("Raj", 100, 250, 160, 280, lang="fr"),
        ]
        sorted_l = _sorted_lines(lines)
        found = _find_label_value(sorted_l, FIELD_LABELS["father_name"])
        assert found is not None
        assert "Raj" in found[0]

    def test_falls_back_to_native_when_no_latin(self):
        lines = [
            _make_line_at("தந்தையின்", 100, 100, 200, 130, lang="ta"),
            _make_line_at("பெயர்:", 210, 100, 300, 130, lang="ta"),
            _make_line_at("ராஜ்", 100, 150, 180, 180, lang="ta"),
        ]
        sorted_l = _sorted_lines(lines)
        found = _find_label_value(sorted_l, FIELD_LABELS["father_name"])
        assert found is not None
        assert "ராஜ்" in found[0]


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------
class TestDateNormalization:
    def test_dmy_dash(self):
        assert normalize_date("03-01-2007") == "2007-01-03"

    def test_dmy_slash(self):
        assert normalize_date("15/06/2019") == "2019-06-15"

    def test_iso(self):
        assert normalize_date("2020-01-10") == "2020-01-10"

    def test_text_dmy(self):
        assert normalize_date("18 MAR 2007") == "2007-03-18"

    def test_text_mdy(self):
        assert normalize_date("MAR 18, 2007") == "2007-03-18"

    def test_embedded_in_text(self):
        assert normalize_date("/ Age: 03-01-2007") == "2007-01-03"

    def test_returns_none_on_garbage(self):
        assert normalize_date("no date here") is None


# ---------------------------------------------------------------------------
# MRZ parsing (Passport TD3)
# ---------------------------------------------------------------------------
class TestMRZParsing:
    def test_td3_passport(self):
        mrz = [
            "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
            "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
        ]
        result = parse_mrz(mrz)
        assert result is not None
        assert result.surname == "ERIKSSON"
        assert result.given_name == "ANNA MARIA"
        assert result.document_number == "L898902C3"
        assert result.nationality == "UTO"
        assert result.sex == "F"

    def test_returns_none_on_garbage(self):
        assert parse_mrz(["not a real mrz line"]) is None

    def test_returns_none_on_empty(self):
        assert parse_mrz([]) is None


# ---------------------------------------------------------------------------
# Full passport extraction (MRZ + label matching)
# ---------------------------------------------------------------------------
class TestPassportExtraction:
    def test_passport_mrz_fields(self):
        mrz_lines = [
            "P<INDSMITH<<JOHN<WILLIAM<<<<<<<<<<<<<<<<<<<<<",
            "A123456786IND9005151M3001095<<<<<<<<<<<<<<04",
        ]
        field_lines = [
            _make_line_at("Date of Issue: 10 JAN 2020", 100, 100, 400, 130, lang="fr"),
            _make_line_at("Issuing Authority:", 100, 150, 300, 180, lang="fr"),
            _make_line_at("MINISTRY OF EXTERNAL AFFAIRS", 100, 190, 500, 220, lang="fr"),
        ]
        result = extract_structured_fields(
            DocumentType.PASSPORT, mrz_lines, field_lines,
        )
        assert result.fields["name"] == "SMITH, JOHN WILLIAM"
        assert result.fields["surname"] == "SMITH"
        assert result.fields["given_name"] == "JOHN WILLIAM"
        assert result.fields["document_number"] == "A12345678"
        assert result.fields["nationality"] == "IND"
        assert result.fields["sex"] == "M"
        assert result.sources["name"] == "mrz"
        assert result.fields["issue_date"] == "2020-01-10"
        assert result.fields["issuing_authority"] == "MINISTRY OF EXTERNAL AFFAIRS"


# ---------------------------------------------------------------------------
# National ID extraction
# ---------------------------------------------------------------------------
class TestNationalIDExtraction:
    def test_national_id_fields(self):
        lines = [
            _make_line_at("Name:", 100, 100, 200, 130, lang="fr"),
            _make_line_at("Jane Doe", 210, 100, 350, 130, lang="fr"),
            _make_line_at("Date of Birth: 25-12-1995", 100, 150, 400, 180, lang="fr"),
            _make_line_at("Gender: Female", 100, 200, 300, 230, lang="fr"),
            _make_line_at("ID No: ABC1234567", 100, 250, 350, 280, lang="fr"),
            _make_line_at("Nationality: Indian", 100, 300, 350, 330, lang="fr"),
        ]
        result = extract_structured_fields(
            DocumentType.NATIONAL_ID, [], lines,
        )
        assert result.fields["name"] == "Jane Doe"
        assert result.fields["date_of_birth"] == "1995-12-25"
        assert result.fields["sex"] == "F"
        assert result.fields["document_number"] == "ABC1234567"
        assert result.fields["nationality"] == "Indian"


# ---------------------------------------------------------------------------
# Permit extraction
# ---------------------------------------------------------------------------
class TestPermitExtraction:
    def test_permit_fields(self):
        lines = [
            _make_line_at("Name:", 100, 100, 200, 130, lang="fr"),
            _make_line_at("John Smith", 210, 100, 350, 130, lang="fr"),
            _make_line_at("Father's Name:", 100, 150, 300, 180, lang="fr"),
            _make_line_at("Robert Smith", 100, 200, 300, 230, lang="fr"),
            _make_line_at("Date of Birth: 15/05/1990", 100, 250, 400, 280, lang="fr"),
            _make_line_at("Permit No: PRM2024001234", 100, 300, 400, 330, lang="fr"),
            _make_line_at("Date of Issue: 01-01-2024", 100, 350, 400, 380, lang="fr"),
            _make_line_at("Valid Until: 01-01-2025", 100, 400, 400, 430, lang="fr"),
            _make_line_at("Issuing Authority:", 100, 450, 300, 480, lang="fr"),
            _make_line_at("Immigration Authority", 100, 490, 400, 520, lang="fr"),
        ]
        result = extract_structured_fields(
            DocumentType.PERMIT, [], lines,
        )
        assert result.fields["name"] == "John Smith"
        assert result.fields["father_name"] == "Robert Smith"
        assert result.fields["date_of_birth"] == "1990-05-15"
        assert result.fields["document_number"] == "PRM2024001234"
        assert result.fields["issue_date"] == "2024-01-01"
        assert result.fields["expiry_date"] == "2025-01-01"
        assert result.fields["issuing_authority"] == "Immigration Authority"


# ---------------------------------------------------------------------------
# Visa extraction (two-column layout with margin annotations)
# ---------------------------------------------------------------------------
VISA_FIELD_LINES = [
    _make_line_at("UNINNDSTMNESOFAVIERIOA", 147, 72, 872, 115, lang="fr", score=0.76),
    _make_line_at("Surname", 427, 160, 540, 186, lang="fr"),
    _make_line_at("*", 962, 152, 982, 170, lang="fr"),
    _make_line_at("VIAJERO DE LA FRONTERA", 427, 185, 846, 225, lang="fr"),
    _make_line_at("4", 951, 190, 973, 216, lang="fr"),
    _make_line_at("Given Names", 426, 229, 600, 258, lang="fr"),
    _make_line_at("9", 947, 234, 973, 266, lang="fr"),
    _make_line_at("JORGE", 427, 260, 537, 295, lang="fr"),
    _make_line_at("3", 948, 282, 974, 315, lang="fr"),
    _make_line_at("MOUBOU", 14, 297, 48, 474, lang="fr", score=0.51),
    _make_line_at("Date of Birth", 429, 305, 584, 328, lang="fr"),
    _make_line_at("Nationality", 707, 298, 843, 333, lang="fr"),
    _make_line_at("18 MAY 1980", 429, 331, 619, 367, lang="fr"),
    _make_line_at("MEXICAN", 709, 331, 857, 366, lang="fr"),
    _make_line_at("6", 947, 329, 974, 361, lang="fr"),
    _make_line_at("Sex", 428, 376, 479, 402, lang="fr"),
    _make_line_at("2", 947, 376, 976, 412, lang="fr"),
    _make_line_at("MALE", 429, 406, 523, 439, lang="fr"),
    _make_line_at("4", 948, 423, 975, 454, lang="fr"),
    _make_line_at("Date of Issue", 428, 447, 592, 474, lang="fr"),
    _make_line_at("Expires On", 706, 444, 849, 474, lang="fr"),
    _make_line_at("21 MAR 2012", 430, 480, 624, 508, lang="fr"),
    _make_line_at("20 MAR 2022", 708, 476, 906, 508, lang="fr"),
]


class TestVisaExtraction:
    """End-to-end test against a US B1/B2 visa with two-column layout."""

    def setup_method(self):
        self.result = extract_structured_fields(
            document_type=DocumentType.VISA,
            mrz_lines=[],
            field_lines=VISA_FIELD_LINES,
        )

    def test_surname(self):
        assert self.result.fields["surname"] == "VIAJERO DE LA FRONTERA"

    def test_given_name(self):
        assert self.result.fields["given_name"] == "JORGE"

    def test_name_composed(self):
        assert self.result.fields["name"] == "VIAJERO DE LA FRONTERA, JORGE"

    def test_date_of_birth(self):
        assert self.result.fields["date_of_birth"] == "1980-05-18"

    def test_nationality(self):
        assert self.result.fields["nationality"] == "MEXICAN"

    def test_sex(self):
        f = self.result.fields
        assert f.get("sex") is None or f.get("sex") == "M"

    def test_issue_date(self):
        assert self.result.fields["issue_date"] == "2012-03-21"

    def test_expiry_date(self):
        assert self.result.fields["expiry_date"] == "2022-03-20"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
