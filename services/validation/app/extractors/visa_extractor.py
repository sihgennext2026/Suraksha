"""
Visa field extractor.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.extractors.base_extractor import BaseExtractor


class VisaExtractor(BaseExtractor):
    document_type = "visa"

    def _extract_fields(
        self,
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "name": None,
            "visa_number": None,
            "passport_number": None,
            "nationality": None,
            "visa_type": None,
            "date_of_issue": None,
            "date_of_expiry": None,
        }
        meta: Dict[str, Any] = {}

        # Visa number
        vnum, conf, src = self._extract_number(
            lines,
            [r"visa\s*(no|number|#)", r"control\s*number"],
            pattern=r"\b([A-Z0-9]{6,15})\b",
        )
        fields["visa_number"] = vnum
        if vnum:
            meta["visa_number"] = {"source_text": src, "ocr_confidence": conf}

        # Passport number
        pnum, conf, src = self._extract_number(
            lines,
            [r"passport\s*(no|number|#)"],
            pattern=r"\b([A-Z]{1,2}\d{6,9}|[A-Z0-9]{8,12})\b",
        )
        fields["passport_number"] = pnum
        if pnum:
            meta["passport_number"] = {"source_text": src, "ocr_confidence": conf}

        # Name
        name, conf, src = self._get_text_after_label(
            lines,
            [r"^name\s*:?", r"surname", r"given\s*name"],
            max_lookahead=2,
            skip_patterns=[r"visa", r"passport", r"nationality", r"date"],
        )
        if name:
            fields["name"] = self.normalize_name(name)
            meta["name"] = {"source_text": src, "ocr_confidence": conf}

        # Nationality
        nat, conf, src = self._get_text_after_label(
            lines, [r"nationality", r"citizen"], max_lookahead=2
        )
        if nat:
            fields["nationality"] = nat.strip()
            meta["nationality"] = {"source_text": src, "ocr_confidence": conf}

        # Visa type
        vtype, conf, src = None, None, None
        for ln in lines:
            text = str(ln.get("text") or "")
            m = re.search(r"(?:visa\s*type|type\s*of\s*visa|class)\s*[/:]?\s*(?:class)?\s*([A-Z0-9][A-Z0-9/\-]{1,10})", text, re.IGNORECASE)
            if m:
                vtype = m.group(1).strip()
                conf = ln.get("confidence")
                src = text
                break
        if not vtype:
            vtype, conf, src = self._get_text_after_label(
                lines,
                [r"visa\s*type", r"type\s*of\s*visa"],
                max_lookahead=2,
            )
        if vtype:
            # Clean leading / or Class
            vtype = re.sub(r"^[/\s]*(class)?[/\s]*", "", vtype, flags=re.IGNORECASE).strip()
            fields["visa_type"] = vtype
            meta["visa_type"] = {"source_text": src, "ocr_confidence": conf}

        # Dates
        doi, conf, src = self._extract_date_field(
            lines, [r"date\s*of\s*issue", r"issue\s*date", r"issued"]
        )
        fields["date_of_issue"] = doi
        if doi:
            meta["date_of_issue"] = {"source_text": src, "ocr_confidence": conf}

        doe, conf, src = self._extract_date_field(
            lines, [r"date\s*of\s*expir", r"expiry", r"valid\s*until", r"valid\s*to"]
        )
        fields["date_of_expiry"] = doe
        if doe:
            meta["date_of_expiry"] = {"source_text": src, "ocr_confidence": conf}

        return fields, meta

    def _extract_number(
        self,
        lines: List[Dict[str, Any]],
        label_patterns: List[str],
        pattern: str,
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        idx = -1
        for lp in label_patterns:
            idx = self._find_line_index(lines, lp)
            if idx >= 0:
                break
        # Prefer lines AFTER the label
        search = lines[idx + 1 : idx + 4] if idx >= 0 else lines
        rx = re.compile(pattern, re.IGNORECASE)
        skip = re.compile(r"^(visa|passport|number|no|#|name|nationality|date|type|class)$", re.IGNORECASE)
        for ln in search:
            text = str(ln.get("text") or "").strip()
            if not text or skip.match(text):
                continue
            m = rx.search(text)
            if m:
                val = m.group(1).upper()
                if val in ("NUMBER", "PASSPORT", "VISA", "NAME"):
                    continue
                return val, ln.get("confidence"), text
        # Fallback: scan all lines
        for ln in lines:
            text = str(ln.get("text") or "").strip()
            if skip.match(text):
                continue
            m = rx.search(text)
            if m:
                val = m.group(1).upper()
                if val in ("NUMBER", "PASSPORT", "VISA", "NAME"):
                    continue
                if len(val) >= 6:
                    return val, ln.get("confidence"), text
        return None, None, None

    def _extract_date_field(
        self,
        lines: List[Dict[str, Any]],
        label_patterns: List[str],
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        val, conf, src = self._extract_inline_value(
            lines,
            label_patterns,
            value_pattern=r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}",
        )
        if val:
            return self.normalize_date(val), conf, src
        val, conf, src = self._get_text_after_label(
            lines, label_patterns, max_lookahead=2
        )
        if val:
            return self.normalize_date(val), conf, src
        return None, None, None
