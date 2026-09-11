"""
Passport field extractor with MRZ support.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.extractors.base_extractor import BaseExtractor


class PassportExtractor(BaseExtractor):
    document_type = "passport"

    NAME_SKIP = [
        r"^name\s*:?\s*$",
        r"surname",
        r"given\s*name",
        r"nationality",
        r"passport",
        r"date\s*of",
        r"place\s*of",
        r"sex",
        r"gender",
        r"^mrz",
        r"^p<",
    ]

    def _extract_fields(
        self,
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        fields: Dict[str, Any] = {
            "name": None,
            "passport_number": None,
            "nationality": None,
            "date_of_birth": None,
            "date_of_issue": None,
            "date_of_expiry": None,
        }
        meta: Dict[str, Any] = {}

        # Passport number
        pnum, conf, src = self._extract_passport_number(lines, full_text)
        fields["passport_number"] = pnum
        if pnum:
            meta["passport_number"] = {"source_text": src, "ocr_confidence": conf}

        # Name
        name, conf, src = self._extract_name(lines)
        fields["name"] = name
        if name:
            meta["name"] = {"source_text": src, "ocr_confidence": conf}

        # Nationality
        nat, conf, src = self._extract_nationality(lines)
        fields["nationality"] = nat
        if nat:
            meta["nationality"] = {"source_text": src, "ocr_confidence": conf}

        # DOB
        dob, conf, src = self._extract_date_field(
            lines, [r"date\s*of\s*birth", r"dob", r"birth"]
        )
        fields["date_of_birth"] = dob
        if dob:
            meta["date_of_birth"] = {"source_text": src, "ocr_confidence": conf}

        # Issue
        doi, conf, src = self._extract_date_field(
            lines, [r"date\s*of\s*issue", r"issue\s*date", r"issued"]
        )
        fields["date_of_issue"] = doi
        if doi:
            meta["date_of_issue"] = {"source_text": src, "ocr_confidence": conf}

        # Expiry
        doe, conf, src = self._extract_date_field(
            lines, [r"date\s*of\s*expir", r"expiry", r"valid\s*until", r"date\s*of\s*expiry"]
        )
        fields["date_of_expiry"] = doe
        if doe:
            meta["date_of_expiry"] = {"source_text": src, "ocr_confidence": conf}

        return fields, meta

    def _post_process(
        self,
        result: Dict[str, Any],
        lines: List[Dict[str, Any]],
        full_text: str,
        ocr: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        mrz = self._extract_mrz(lines, full_text)
        if mrz:
            return {"mrz": mrz}
        return None

    def _extract_passport_number(
        self, lines: List[Dict[str, Any]], full_text: str
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        # Common passport number patterns (alphanumeric 6-12)
        patterns = [
            re.compile(r"\b([A-Z]{1,2}\d{6,9})\b", re.IGNORECASE),
            re.compile(r"\b([A-Z0-9]{8,12})\b", re.IGNORECASE),
        ]
        label_idx = self._find_line_index(
            lines, r"passport\s*(no|number|#)|document\s*no"
        )
        candidates: List[Tuple[str, float, str]] = []

        search_lines = lines
        if label_idx >= 0:
            search_lines = lines[label_idx : label_idx + 4]

        for ln in search_lines:
            text = str(ln.get("text") or "").strip()
            if not text:
                continue
            if re.search(r"name|nationality|birth|expir|issue|sex", text, re.IGNORECASE):
                continue
            for pat in patterns:
                m = pat.search(text)
                if m:
                    val = m.group(1).upper()
                    # Avoid pure dates
                    if re.match(r"^\d{6,8}$", val) and len(val) <= 8:
                        # Could be YYMMDD — skip if looks like date
                        continue
                    candidates.append((val, ln.get("confidence") or 0.0, text))
                    break

        if candidates:
            # Prefer letter+digit style
            for c in candidates:
                if re.match(r"^[A-Z]+\d+$", c[0], re.IGNORECASE):
                    return c[0], c[1], c[2]
            return candidates[0][0], candidates[0][1], candidates[0][2]
        return None, None, None

    def _extract_name(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        # Surname + given names — value is typically on the NEXT line after label
        surname, s_conf, s_src = None, None, None
        given, g_conf, g_src = None, None, None

        for i, ln in enumerate(lines):
            text = str(ln.get("text") or "")
            if re.search(r"surname|last\s*name|family\s*name|nom\b", text, re.IGNORECASE):
                # next non-empty line
                for j in range(i + 1, min(i + 3, len(lines))):
                    cand = str(lines[j].get("text") or "").strip()
                    if not cand:
                        continue
                    if re.search(r"given|first|forename|prenom|nationality|passport|date|sex", cand, re.IGNORECASE):
                        break
                    if re.match(r"^[A-Za-z][A-Za-z\s\-]{1,40}$", cand):
                        surname = cand
                        s_conf = lines[j].get("confidence")
                        s_src = cand
                        break
            if re.search(r"given\s*name|first\s*name|forename|prenom", text, re.IGNORECASE):
                for j in range(i + 1, min(i + 3, len(lines))):
                    cand = str(lines[j].get("text") or "").strip()
                    if not cand:
                        continue
                    if re.search(r"surname|nationality|passport|date|sex|place", cand, re.IGNORECASE):
                        break
                    if re.match(r"^[A-Za-z][A-Za-z\s\-]{1,40}$", cand):
                        given = cand
                        g_conf = lines[j].get("confidence")
                        g_src = cand
                        break

        if surname or given:
            parts = [p for p in [given, surname] if p]
            name = self.normalize_name(" ".join(parts))
            conf = g_conf or s_conf
            src = g_src or s_src
            return name, conf, src

        # Generic Name: label
        val, conf, src = self._get_text_after_label(
            lines,
            [r"^name\s*:?", r"\bname\s*:"],
            max_lookahead=2,
            skip_patterns=self.NAME_SKIP,
        )
        if val:
            return self.normalize_name(val), conf, src
        return None, None, None

    def _extract_nationality(
        self, lines: List[Dict[str, Any]]
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        for i, ln in enumerate(lines):
            text = str(ln.get("text") or "")
            if re.search(r"nationality|nationalite|citizen", text, re.IGNORECASE):
                # inline value after label
                # Prefer next-line value over inline fragment
                for j in range(i + 1, min(i + 3, len(lines))):
                    cand = str(lines[j].get("text") or "").strip()
                    if not cand:
                        continue
                    if re.search(r"date|sex|place|passport|birth|sexe", cand, re.IGNORECASE):
                        break
                    cleaned = re.sub(r"[^A-Za-z\s]", "", cand).strip()
                    # Reject label remnants
                    if cleaned.upper() in ("TE", "LITE", "NATIONALITE", "NATIONALITY", "CODE", "DU", "PAYS"):
                        continue
                    if cleaned and len(cleaned) >= 3:
                        return cleaned, lines[j].get("confidence"), cand
                m = re.search(r"(?:nationality|nationalite|citizen)[^A-Za-z]*([A-Za-z]{3,})", text, re.IGNORECASE)
                if m and m.group(1).upper() not in ("NATIONALITE", "NATIONALITY", "CODE", "DU"):
                    return m.group(1).strip(), ln.get("confidence"), text
        return None, None, None

    def _extract_date_field(
        self,
        lines: List[Dict[str, Any]],
        label_patterns: List[str],
    ) -> Tuple[Optional[str], Optional[float], Optional[str]]:
        for lp in label_patterns:
            for i, ln in enumerate(lines):
                text = str(ln.get("text") or "")
                if not re.search(lp, text, re.IGNORECASE):
                    continue
                # Inline date on same line
                norm = self.normalize_date(text)
                if norm:
                    return norm, ln.get("confidence"), text
                m = re.search(r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})", text)
                if m:
                    norm = self.normalize_date(m.group(1))
                    if norm:
                        return norm, ln.get("confidence"), text
                # Next lines
                for j in range(i + 1, min(i + 3, len(lines))):
                    cand = str(lines[j].get("text") or "").strip()
                    if not cand:
                        continue
                    norm = self.normalize_date(cand)
                    if norm:
                        return norm, lines[j].get("confidence"), cand
                    m = re.search(r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})", cand)
                    if m:
                        norm = self.normalize_date(m.group(1))
                        if norm:
                            return norm, lines[j].get("confidence"), cand
        return None, None, None

    def _extract_mrz(
        self, lines: List[Dict[str, Any]], full_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extract TD3 MRZ lines (two lines of 44 characters starting with P<).
        """
        mrz_lines = []
        for ln in lines:
            text = str(ln.get("text") or "").strip().replace(" ", "")
            # MRZ-like: mostly uppercase, digits, < 
            if re.match(r"^P<[A-Z0-9<]{20,}$", text, re.IGNORECASE):
                mrz_lines.append(text.upper())
            elif re.match(r"^[A-Z0-9<]{30,44}$", text, re.IGNORECASE) and "<" in text:
                mrz_lines.append(text.upper())

        # Also search full_text
        if not mrz_lines:
            for m in re.finditer(r"(P<[A-Z0-9<]{40,44})", full_text.replace(" ", ""), re.IGNORECASE):
                mrz_lines.append(m.group(1).upper())
            for m in re.finditer(r"([A-Z0-9<]{44})", full_text.replace(" ", ""), re.IGNORECASE):
                candidate = m.group(1).upper()
                if "<" in candidate and candidate not in mrz_lines:
                    mrz_lines.append(candidate)

        if not mrz_lines:
            return None

        result: Dict[str, Any] = {"raw_lines": mrz_lines[:2]}

        # Parse TD3 line 1: P<CCCSurname<<Given<Names
        line1 = mrz_lines[0] if mrz_lines else ""
        if line1.startswith("P<") and len(line1) >= 5:
            result["document_code"] = line1[0]
            result["issuing_country"] = line1[2:5].replace("<", "")
            name_part = line1[5:]
            if "<<" in name_part:
                parts = name_part.split("<<", 1)
                surname = parts[0].replace("<", " ").strip()
                given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
                result["surname"] = surname
                result["given_names"] = given
                result["name"] = f"{given} {surname}".strip()
            else:
                result["name"] = name_part.replace("<", " ").strip()

        # Parse TD3 line 2 if present
        if len(mrz_lines) >= 2:
            line2 = mrz_lines[1]
            if len(line2) >= 27:
                result["passport_number"] = line2[0:9].replace("<", "")
                result["nationality"] = line2[10:13].replace("<", "")
                # YYMMDD DOB
                dob_raw = line2[13:19]
                result["date_of_birth_raw"] = dob_raw
                result["date_of_birth"] = self._mrz_date_to_iso(dob_raw)
                result["sex"] = line2[20:21]
                exp_raw = line2[21:27]
                result["date_of_expiry_raw"] = exp_raw
                result["date_of_expiry"] = self._mrz_date_to_iso(exp_raw, expiry=True)

        return result

    def _mrz_date_to_iso(self, yymmdd: str, expiry: bool = False) -> Optional[str]:
        if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
            return None
        yy = int(yymmdd[0:2])
        mm = int(yymmdd[2:4])
        dd = int(yymmdd[4:6])
        # Century heuristic
        if expiry:
            year = 2000 + yy if yy < 70 else 1900 + yy
        else:
            year = 1900 + yy if yy > 50 else 2000 + yy
        return self._validate_date(year, mm, dd)
