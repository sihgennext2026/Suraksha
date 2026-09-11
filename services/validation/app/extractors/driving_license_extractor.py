"""
Driving License field extractor.
Works on raw OCR JSON (lines[].text, full_text).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.extractors.base_extractor import BaseExtractor


class DrivingLicenseExtractor(BaseExtractor):
    document_type = "driving_license"

    # Labels that should never be taken as name / license number values
    NAME_SKIP = [
        r"^name\s*:?\s*$",
        r"holder'?s?\s*signature",
        r"^signature",
        r"son/daughter",
        r"^address",
        r"date\s*of\s*birth",
        r"blood\s*group",
        r"organ",
        r"issue\s*date",
        r"validity",
        r"^pdl$",
        r"^tn$",
        r"^\-?\d+$",
    ]

    LICENSE_SKIP = [
        r"^tn$",
        r"^pdl$",
        r"^\-?\d+$",
        r"issue\s*date",
        r"validity",
        r"name",
        r"address",
        r"blood",
        r"organ",
        r"son/daughter",
        r"holder",
        r"signature",
        r"date\s*of\s*birth",
        r"indian\s*union",
        r"government",
        r"driving\s*licen",
    ]

    def _extract_fields(
        self,
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "name": None,
            "license_number": None,
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,
        }
        meta: Dict[str, Any] = {}

        # --- License number ---
        lic, conf, src = self._extract_license_number(lines, full_text)
        fields["license_number"] = lic
        if lic is not None:
            meta["license_number"] = {
                "source_text": src,
                "ocr_confidence": conf,
            }

        # --- Name ---
        name, conf, src = self._extract_name(lines)
        fields["name"] = name
        if name is not None:
            meta["name"] = {"source_text": src, "ocr_confidence": conf}

        # --- Date of Birth ---
        dob, conf, src = self._extract_dob(lines)
        fields["date_of_birth"] = dob
        if dob is not None:
            meta["date_of_birth"] = {"source_text": src, "ocr_confidence": conf}

        # --- Issue date ---
        doi, conf, src = self._extract_issue_date(lines)
        fields["date_of_issue"] = doi
        if doi is not None:
            meta["date_of_issue"] = {"source_text": src, "ocr_confidence": conf}

        # --- Expiry date ---
        doe, conf, src = self._extract_expiry_date(lines)
        fields["date_of_expiry"] = doe
        if doe is not None:
            meta["date_of_expiry"] = {"source_text": src, "ocr_confidence": conf}

        # Optional fields (not required for evaluation schema)
        bg, conf, src = self._extract_inline_value(
            lines, [r"blood\s*group"], value_pattern=r"[ABO][+\-]|AB[+\-]"
        )
        if bg:
            fields["blood_group"] = bg.strip()
            meta["blood_group"] = {"source_text": src, "ocr_confidence": conf}

        od, conf, src = self._extract_inline_value(
            lines, [r"organ\s*[dq]?onor"]
        )
        if od:
            # Normalize Y/N
            od_clean = od.strip().upper()
            if od_clean in ("Y", "YES", "N", "NO"):
                fields["organ_donor"] = "Y" if od_clean.startswith("Y") else "N"
                meta["organ_donor"] = {"source_text": src, "ocr_confidence": conf}

        parent, conf, src = self._get_text_after_label(
            lines,
            [r"son/daughter", r"father'?s?\s*name", r"parent"],
            max_lookahead=2,
            skip_patterns=[r"^address", r"date", r"blood", r"organ"],
        )
        if parent:
            fields["parent_name"] = self.normalize_name(parent)
            meta["parent_name"] = {"source_text": src, "ocr_confidence": conf}

        addr = self._extract_address(lines)
        if addr:
            fields["address"] = addr
            meta["address"] = {"source_text": addr, "ocr_confidence": None}

        return fields, meta

    def _extract_license_number(
        self, lines: List[Dict[str, Any]], full_text: str
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Extract license number. Prefer patterns like TNxxxxxxxxxxx or
        alphanumeric strings that look like Indian DL numbers.
        Avoid short codes like 'TN', 'PDL', numeric noise like '-9090'.
        """
        # Pattern for Indian DL: state code (2 letters) + digits/letters
        lic_rx = re.compile(
            r"\b([A-Z]{2}[0-9]{2,4}[0-9A-Z]{6,12})\b",
            re.IGNORECASE,
        )
        skip_rx = [re.compile(p, re.IGNORECASE) for p in self.LICENSE_SKIP]

        # First pass: scan lines for strong pattern
        for ln in lines:
            text = str(ln.get("text") or "").strip()
            if not text:
                continue
            if any(rx.search(text) for rx in skip_rx):
                continue
            m = lic_rx.search(text)
            if m:
                val = m.group(1).upper()
                return val, ln.get("confidence"), text

        # Second pass: any long alphanumeric that isn't a label
        alnum_rx = re.compile(r"\b([A-Z0-9]{10,20})\b", re.IGNORECASE)
        for ln in lines:
            text = str(ln.get("text") or "").strip()
            if not text or any(rx.search(text) for rx in skip_rx):
                continue
            m = alnum_rx.search(text)
            if m:
                val = m.group(1).upper()
                # Reject pure dates
                if re.match(r"^\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}$", val):
                    continue
                return val, ln.get("confidence"), text

        return None, None, None

    def _extract_name(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Extract name following 'Name:' label.
        Skip 'Holder's Signature' and other non-name lines.
        """
        skip = self.NAME_SKIP
        # Prefer value after Name: label
        val, conf, src = self._get_text_after_label(
            lines,
            [r"^name\s*:?", r"\bname\s*:"],
            max_lookahead=3,
            skip_patterns=skip,
        )
        if val:
            cleaned = self.normalize_name(val)
            # Reject document-number-like values as names
            if cleaned and len(cleaned) > 1 and re.search(r"[A-Za-z]{2,}", cleaned) and not re.match(r"^[A-Z]{2}\d", cleaned, re.IGNORECASE) and not re.match(r"^\d+$", cleaned):
                return cleaned, conf, src

        # Inline: Name: VALUE
        val, conf, src = self._extract_inline_value(lines, [r"\bname"])
        if val:
            cleaned = self.normalize_name(val)
            if cleaned and len(cleaned) > 1 and re.search(r"[A-Za-z]{2,}", cleaned) and not any(
                re.search(p, cleaned, re.IGNORECASE) for p in skip
            ):
                if not re.match(r"^[A-Z]{2}\d", cleaned, re.IGNORECASE) and not re.match(r"^\d+$", cleaned):
                    return cleaned, conf, src

        return None, None, None

    def _extract_dob(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """Extract date of birth from 'DateofBirth:...' or nearby."""
        # Inline pattern common in Indian DL OCR
        val, conf, src = self._extract_inline_value(
            lines,
            [r"date\s*of\s*birth", r"dob", r"dateofbirth"],
            value_pattern=r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}",
        )
        if val:
            norm = self.normalize_date(val)
            return norm, conf, src

        # Look for label then next date-like line
        idx = self._find_line_index(lines, r"date\s*of\s*birth|dob|dateofbirth")
        if idx >= 0:
            for j in range(0, 3):
                if idx + j >= len(lines):
                    break
                text = str(lines[idx + j].get("text") or "")
                norm = self.normalize_date(text)
                if norm:
                    # Prefer DOB that looks like a birth date (year < 2015-ish)
                    year = int(norm[:4])
                    if year < 2015:
                        return norm, lines[idx + j].get("confidence"), text
        return None, None, None

    def _extract_issue_date(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Issue Date label is followed by date values.
        In the sample OCR the order is:
          Issue Date | Validity (NT) | Validity (TR) | 16-06-2025 | 09-09-2046
        So the first date after the issue/validity labels is issue date.
        """
        # Collect indices of label lines
        issue_idx = self._find_line_index(lines, r"issue\s*date")
        validity_idx = self._find_line_index(lines, r"validity")

        start = min(
            i for i in [issue_idx, validity_idx] if i >= 0
        ) if (issue_idx >= 0 or validity_idx >= 0) else -1

        if start < 0:
            # Fallback: search full text for "Issue Date" near a date
            return None, None, None

        dates_found: List[Tuple[str, float, str]] = []
        for j in range(start, min(start + 8, len(lines))):
            text = str(lines[j].get("text") or "").strip()
            if not text:
                continue
            # Skip pure labels
            if re.search(r"issue\s*date|validity|name|holder", text, re.IGNORECASE):
                continue
            norm = self.normalize_date(text)
            if norm:
                conf = lines[j].get("confidence") or 0.0
                dates_found.append((norm, conf, text))

        if dates_found:
            # First date after labels is issue date
            return dates_found[0][0], dates_found[0][1], dates_found[0][2]
        return None, None, None

    def _extract_expiry_date(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Expiry comes from Validity (NT) / Validity (TR).
        Prefer the later date when multiple dates appear after validity labels.
        """
        validity_idx = self._find_line_index(lines, r"validity")
        issue_idx = self._find_line_index(lines, r"issue\s*date")
        start = min(
            i for i in [issue_idx, validity_idx] if i >= 0
        ) if (issue_idx >= 0 or validity_idx >= 0) else -1

        if start < 0:
            return None, None, None

        dates_found: List[Tuple[str, float, str]] = []
        for j in range(start, min(start + 8, len(lines))):
            text = str(lines[j].get("text") or "").strip()
            if not text:
                continue
            if re.search(r"issue\s*date|validity|name|holder", text, re.IGNORECASE):
                continue
            norm = self.normalize_date(text)
            if norm:
                conf = lines[j].get("confidence") or 0.0
                dates_found.append((norm, conf, text))

        if len(dates_found) >= 2:
            # Second date is typically the (longer) validity/expiry
            return dates_found[1][0], dates_found[1][1], dates_found[1][2]
        if len(dates_found) == 1:
            # Only one date — could be expiry if year is far future
            year = int(dates_found[0][0][:4])
            if year > 2030:
                return dates_found[0][0], dates_found[0][1], dates_found[0][2]
        return None, None, None

    def _extract_address(
        self, lines: List[Dict[str, Any]]
    ) -> Optional[str]:
        idx = self._find_line_index(lines, r"^address\s*:?")
        if idx < 0:
            return None
        parts = []
        for j in range(1, 4):
            if idx + j >= len(lines):
                break
            text = str(lines[idx + j].get("text") or "").strip()
            if not text:
                continue
            if re.search(r"^pdl$|^class|signature", text, re.IGNORECASE):
                break
            parts.append(text)
        return " ".join(parts) if parts else None
