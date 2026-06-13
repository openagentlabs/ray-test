"""PDF text normalization utilities."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Sequence, Tuple

from fortify_workbook_tool.constants import PRIORITIES


class TextNormalizer:
    """PDF line / path normalization helpers used by the workbook parser."""

    _ISSUES_HDR = re.compile(r"\(\s*(\d+)\s*issues?\s*\)\s*$", re.IGNORECASE)
    _REF_LINE = re.compile(r",\s*line\s+\d+\s+\(")
    _FILE_LINE = re.compile(r"^File:\s*(.+)$")

    @classmethod
    def file_line_match(cls, line: str) -> Optional[re.Match[str]]:
        return cls._FILE_LINE.match(line)

    @classmethod
    def ref_line_matches(cls, line: str) -> bool:
        return bool(cls._REF_LINE.search(line))

    @staticmethod
    def norm_line(line: str) -> str:
        t = unicodedata.normalize("NFC", line)
        for ch in (
            "\ufeff",
            "\xa0",
            "\u1680",
            "\u2000",
            "\u2001",
            "\u2002",
            "\u2003",
            "\u2004",
            "\u2005",
            "\u2006",
            "\u2007",
            "\u2008",
            "\u2009",
            "\u200a",
            "\u202f",
            "\u205f",
            "\u3000",
        ):
            t = t.replace(ch, " ")
        return t.strip()

    @staticmethod
    def clean_spaces(s: str) -> str:
        return re.sub(r"[ \t\r\f\v]+", " ", s).strip()

    @classmethod
    def issues_header_match(cls, line: str) -> Optional[re.Match[str]]:
        return cls._ISSUES_HDR.search(line)

    @classmethod
    def strip_issues_header(cls, text: str) -> str:
        return cls._ISSUES_HDR.sub("", text).strip()

    @staticmethod
    def normalize_repo_path(path: str, strip_prefixes: Tuple[str, ...]) -> str:
        p = path.replace("\\", "/").strip()
        for pref in strip_prefixes:
            pref = pref.strip("/")
            if pref and p.startswith(pref):
                p = p[len(pref) :].lstrip("/")
                break
        m = re.match(r"^(?:.*/)?(?:Downloads/)?[^/]+/(deploy/.+)$", p)
        if m:
            return m.group(1)
        return p

    @staticmethod
    def split_priority(line: str) -> Tuple[str, Optional[str]]:
        s = TextNormalizer.norm_line(line)
        for p in PRIORITIES:
            if s.endswith(" " + p):
                return s[: -(len(p) + 1)].strip(), p
        return s, None

    @staticmethod
    def parse_file_location(fp: str) -> Tuple[str, str]:
        fp = fp.strip()
        mloc = re.match(r"^(.*?):(\d+)\s*$", fp)
        if mloc:
            return mloc.group(1).strip(), mloc.group(2).strip()
        return fp, ""

    @classmethod
    def join_split_issue_count_lines(cls, lines: Sequence[str]) -> List[str]:
        out: List[str] = []
        i = 0
        n = len(lines)
        while i < n:
            if i + 1 < n:
                a, b = lines[i], lines[i + 1]
                if re.search(r"\(\s*\d+\s*$", a) and re.match(
                    r"^issues?\)\s*$",
                    b.strip(),
                    flags=re.IGNORECASE,
                ):
                    out.append(cls.clean_spaces(a + b))
                    i += 2
                    continue
            out.append(lines[i])
            i += 1
        return out

