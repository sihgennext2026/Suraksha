"""
Base extractor for raw OCR JSON.
All document-specific extractors inherit from this class.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class BaseExtractor(ABC):
    """Abstract base class for document field extractors."""

    document_type: str = "unknown"

    # Common date patterns found in OCR
    DATE_PATTERNS = [
        # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
        re.compile(
            r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})",
            re.IGNORECASE,
        ),
        # YYYY-MM-DD
        re.compile(
            r"(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})",
            re.IGNORECASE,
        ),
        # DD Mon YYYY / DD Month YYYY
        re.compile(
            r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})",
            re.IGNORECASE,
        ),
    ]

    MONTH_MAP = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    def extract(self, ocr: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry: convert raw OCR JSON into structured document JSON.
        """
        lines = self._get_lines(ocr)
        full_text = ocr.get("full_text") or " ".join(
            ln.get("text", "") for ln in lines
        )
        fields, field_meta = self._extract_fields(lines, full_text, ocr)

        result: Dict[str, Any] = {
            "document_type": self.document_type,
            "fields": fields,
        }
        if field_meta:
            result["field_meta"] = field_meta

        # Subclasses may attach extra data (e.g. MRZ)
        extra = self._post_process(result, lines, full_text, ocr)
        if extra:
            result.update(extra)
        return result

    @abstractmethod
    def _extract_fields(
        self,
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Document-specific extraction.
        Returns (fields_dict, field_meta_dict).
        field_meta maps field_name -> {source_text, ocr_confidence, ...}
        """
        ...

    def _post_process(
        self,
        result: Dict[str, Any],
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Optional post-processing hook (e.g. MRZ for passport)."""
        return None

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _get_lines(self, ocr: Dict[str, Any]) -> List[Dict[str, Any]]:
        lines = ocr.get("lines") or []
        return [ln for ln in lines if isinstance(ln, dict)]

    def _line_texts(self, lines: List[Dict[str, Any]]) -> List[str]:
        return [str(ln.get("text") or "").strip() for ln in lines]

    def _find_line_index(
        self,
        lines: List[Dict[str, Any]],
        pattern: str,
        flags: int = re.IGNORECASE,
    ) -> int:
        """Return index of first line whose text matches pattern, else -1."""
        rx = re.compile(pattern, flags)
        for i, ln in enumerate(lines):
            text = str(ln.get("text") or "")
            if rx.search(text):
                return i
        return -1

    def _get_text_after_label(
        self,
        lines: List[Dict[str, Any]],
        label_patterns: List[str],
        max_lookahead: int = 3,
        skip_patterns: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Find a label line, then return the first non-empty subsequent line
        that does not match skip_patterns.
        Returns (value, confidence, source_text).
        """
        skip_rx = [re.compile(p, re.IGNORECASE) for p in (skip_patterns or [])]
        for label_pat in label_patterns:
            idx = self._find_line_index(lines, label_pat)
            if idx < 0:
                continue
            label_text = str(lines[idx].get("text") or "")
            # Value may be on the same line after the label
            same_line = re.split(
                re.compile(label_pat, re.IGNORECASE), label_text, maxsplit=1
            )
            if len(same_line) > 1 and same_line[1].strip():
                val = same_line[1].strip().lstrip(":").strip()
                if val and len(val) > 1 and not any(rx.search(val) for rx in skip_rx):
                    conf = lines[idx].get("confidence")
                    return val, conf, label_text

            # Look ahead
            for j in range(1, max_lookahead + 1):
                if idx + j >= len(lines):
                    break
                candidate = str(lines[idx + j].get("text") or "").strip()
                if not candidate:
                    continue
                if any(rx.search(candidate) for rx in skip_rx):
                    continue
                conf = lines[idx + j].get("confidence")
                return candidate, conf, candidate
        return None, None, None

    def _extract_inline_value(
        self,
        lines: List[Dict[str, Any]],
        label_patterns: List[str],
        value_pattern: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        """
        Extract value that appears on the same line as the label,
        e.g. 'DateofBirth:10-03-2006' or 'Blood Group: B+'.
        """
        for label_pat in label_patterns:
            rx = re.compile(
                rf"({label_pat})\s*[:\-]?\s*(.+)",
                re.IGNORECASE,
            )
            for ln in lines:
                text = str(ln.get("text") or "")
                m = rx.search(text)
                if m:
                    val = m.group(2).strip().lstrip(":").strip()
                    if value_pattern:
                        vm = re.search(value_pattern, val, re.IGNORECASE)
                        if vm:
                            val = vm.group(0)
                        else:
                            continue
                    if val and len(val) > 1:
                        return val, ln.get("confidence"), text
        return None, None, None

    def normalize_date(self, raw: Optional[str]) -> Optional[str]:
        """
        Normalize various date formats to YYYY-MM-DD.
        Returns None if parsing fails or date is invalid.
        """
        if not raw or not isinstance(raw, str):
            return None
        raw = raw.strip()
        if not raw:
            return None

        # Try DD-MM-YYYY / DD/MM/YYYY / DD.MM.YYYY
        m = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", raw)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return self._validate_date(y, mo, d)

        # Try YYYY-MM-DD
        m = re.match(r"^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$", raw)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return self._validate_date(y, mo, d)

        # Try DD Mon YYYY
        m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})$", raw, re.IGNORECASE)
        if m:
            d = int(m.group(1))
            mo_name = m.group(2).lower()
            y = int(m.group(3))
            mo = self.MONTH_MAP.get(mo_name)
            if mo:
                return self._validate_date(y, mo, d)

        # Embedded date in longer string
        for pat in self.DATE_PATTERNS:
            m = pat.search(raw)
            if m:
                groups = m.groups()
                if len(groups) == 3:
                    if groups[0].isdigit() and len(groups[0]) == 4:
                        y, mo, d = int(groups[0]), int(groups[1]), int(groups[2])
                    elif groups[1].isalpha():
                        d = int(groups[0])
                        mo = self.MONTH_MAP.get(groups[1].lower())
                        y = int(groups[2])
                        if not mo:
                            continue
                    else:
                        d, mo, y = int(groups[0]), int(groups[1]), int(groups[2])
                    result = self._validate_date(y, mo, d)
                    if result:
                        return result
        return None

    def _validate_date(self, year: int, month: int, day: int) -> Optional[str]:
        """Return YYYY-MM-DD if valid calendar date, else None."""
        try:
            if year < 1900 or year > 2100:
                return None
            dt = datetime(year, month, day)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    def normalize_name(self, raw: Optional[str]) -> Optional[str]:
        """Clean name: strip, collapse whitespace, keep original case."""
        if not raw or not isinstance(raw, str):
            return None
        cleaned = re.sub(r"\s+", " ", raw.strip())
        if not cleaned:
            return None
        # Reject pure label-like strings
        if cleaned.lower() in {
            "name", "name:", "holder's signature", "holders signature",
            "signature", "son/daughter", "father", "mother",
        }:
            return None
        return cleaned

    def normalize_number(self, raw: Optional[str]) -> Optional[str]:
        """Strip whitespace from document numbers."""
        if not raw or not isinstance(raw, str):
            return None
        cleaned = re.sub(r"\s+", "", raw.strip())
        return cleaned if cleaned else None
