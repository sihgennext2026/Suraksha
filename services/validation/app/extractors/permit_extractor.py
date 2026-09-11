"""
Permit field extractor.
Fields are driven by the permit rule configuration; common fields extracted here.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.extractors.base_extractor import BaseExtractor


class PermitExtractor(BaseExtractor):
    document_type = "permit"

    def _extract_fields(
        self,
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "name": None,
            "permit_number": None,
            "permit_type": None,
            "date_of_issue": None,
            "date_of_expiry": None,
            "nationality": None,
        }
        meta: Dict[str, Any] = {}

        # Permit number
        pnum, conf, src = self._extract_number(
            lines,
            [r"permit\s*(no|number|#)", r"reference", r"serial"],
            pattern=r"\b([A-Z0-9\-/]{6,20})\b",
        )
        fields["permit_number"] = pnum
        if pnum:
            meta["permit_number"] = {"source_text": src, "ocr_confidence": conf}

        # Name
        name, conf, src = self._get_text_after_label(
            lines,
            [r"^name\s*:?", r"holder", r"permittee"],
            max_lookahead=2,
            skip_patterns=[r"permit", r"date", r"type", r"nationality"],
        )
        if name:
            fields["name"] = self.normalize_name(name)
            meta["name"] = {"source_text": src, "ocr_confidence": conf}

        # Permit type
        ptype, conf, src = self._get_text_after_label(
            lines,
            [r"permit\s*type", r"type\s*of\s*permit", r"category", r"class"],
            max_lookahead=2,
        )
        if ptype:
            fields["permit_type"] = ptype.strip()
            meta["permit_type"] = {"source_text": src, "ocr_confidence": conf}

        # Nationality
        nat, conf, src = self._get_text_after_label(
            lines, [r"nationality", r"citizen"], max_lookahead=2
        )
        if nat:
            fields["nationality"] = nat.strip()
            meta["nationality"] = {"source_text": src, "ocr_confidence": conf}

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
        search = lines[idx + 1 : idx + 4] if idx >= 0 else lines
        rx = re.compile(pattern, re.IGNORECASE)
        skip = re.compile(r"^(permit|number|no|#|type|name|reference|serial)$", re.IGNORECASE)
        for ln in search:
            text = str(ln.get("text") or "").strip()
            if not text or skip.match(text):
                continue
            m = rx.search(text)
            if m:
                val = self.normalize_number(m.group(1))
                if val and val.upper() not in ("PERMIT", "NUMBER", "TYPE"):
                    return val, ln.get("confidence"), text
        for ln in lines:
            text = str(ln.get("text") or "").strip()
            m = re.search(r"\b([A-Z]{1,3}[\-/]?\d{4}[\-/]?\d{3,})\b", text, re.IGNORECASE)
            if m:
                return self.normalize_number(m.group(1)), ln.get("confidence"), text
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
