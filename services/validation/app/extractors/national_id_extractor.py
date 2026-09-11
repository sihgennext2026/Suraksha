"""
National ID field extractor.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.extractors.base_extractor import BaseExtractor


class NationalIdExtractor(BaseExtractor):
    document_type = "national_id"

    def _extract_fields(
        self,
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "name": None,
            "national_id_number": None,
            "date_of_birth": None,
            "gender": None,
            "address": None,
        }
        meta: Dict[str, Any] = {}

        # ID number
        nid, conf, src = self._extract_id_number(lines)
        fields["national_id_number"] = nid
        if nid:
            meta["national_id_number"] = {"source_text": src, "ocr_confidence": conf}

        # Name
        name, conf, src = self._get_text_after_label(
            lines,
            [r"^name\s*:?", r"full\s*name", r"holder"],
            max_lookahead=2,
            skip_patterns=[r"id\s*no", r"date", r"gender", r"address", r"sex"],
        )
        if name:
            fields["name"] = self.normalize_name(name)
            meta["name"] = {"source_text": src, "ocr_confidence": conf}

        # DOB
        dob, conf, src = self._extract_inline_value(
            lines,
            [r"date\s*of\s*birth", r"dob", r"birth"],
            value_pattern=r"\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}",
        )
        if dob:
            fields["date_of_birth"] = self.normalize_date(dob)
            meta["date_of_birth"] = {"source_text": src, "ocr_confidence": conf}
        else:
            val, conf, src = self._get_text_after_label(
                lines, [r"date\s*of\s*birth", r"dob"], max_lookahead=2
            )
            if val:
                fields["date_of_birth"] = self.normalize_date(val)
                meta["date_of_birth"] = {"source_text": src, "ocr_confidence": conf}

        # Gender
        gender, conf, src = self._extract_gender(lines)
        fields["gender"] = gender
        if gender:
            meta["gender"] = {"source_text": src, "ocr_confidence": conf}

        # Address
        addr = self._extract_address(lines)
        if addr:
            fields["address"] = addr

        return fields, meta

    def _extract_id_number(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        label_idx = self._find_line_index(
            lines, r"id\s*(no|number|#)|national\s*id|aadhaar|uid|identity"
        )
        # Prefer lines AFTER the label
        if label_idx >= 0:
            search = lines[label_idx + 1 : label_idx + 4]
        else:
            search = lines
        patterns = [
            re.compile(r"\b(\d{12})\b"),  # Aadhaar-like
            re.compile(r"\b(\d{10,16})\b"),
            re.compile(r"\b([A-Z]{2,5}\d{4,12})\b", re.IGNORECASE),
            re.compile(r"\b([A-Z0-9]{8,16})\b", re.IGNORECASE),
        ]
        for ln in search:
            text = str(ln.get("text") or "").strip()
            if re.search(r"name|birth|gender|address|sex|aadhaar|number", text, re.IGNORECASE):
                # Still allow pure digit lines
                if not re.match(r"^\d{10,16}$", text):
                    continue
            for pat in patterns:
                m = pat.search(text)
                if m:
                    return m.group(1).upper(), ln.get("confidence"), text
        # Full scan fallback
        for ln in lines:
            text = str(ln.get("text") or "").strip()
            m = re.search(r"\b(\d{12})\b", text)
            if m:
                return m.group(1), ln.get("confidence"), text
        return None, None, None

    def _extract_gender(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        val, conf, src = self._extract_inline_value(
            lines, [r"gender", r"sex"], value_pattern=r"\b(M|F|Male|Female|Other)\b"
        )
        if val:
            v = val.strip().upper()
            if v in ("M", "MALE"):
                return "M", conf, src
            if v in ("F", "FEMALE"):
                return "F", conf, src
            return v, conf, src
        val, conf, src = self._get_text_after_label(
            lines, [r"gender", r"sex"], max_lookahead=1
        )
        if val:
            v = val.strip().upper()
            if v.startswith("M"):
                return "M", conf, src
            if v.startswith("F"):
                return "F", conf, src
            return v, conf, src
        return None, None, None

    def _extract_address(self, lines: List[Dict[str, Any]]) -> Optional[str]:
        idx = self._find_line_index(lines, r"^address\s*:?|residential")
        if idx < 0:
            return None
        parts = []
        for j in range(1, 5):
            if idx + j >= len(lines):
                break
            text = str(lines[idx + j].get("text") or "").strip()
            if not text:
                continue
            if re.search(r"signature|issue|valid|class", text, re.IGNORECASE):
                break
            parts.append(text)
        return " ".join(parts) if parts else None
