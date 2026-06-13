#!/usr/bin/env python3
"""
Fail if any aws_security_group resource in deploy/ecs-app uses a non-ASCII description.

EC2 CreateSecurityGroup rejects GroupDescription outside ASCII (e.g. Unicode em/en dashes).
We also validate other description = assignments in the same resource body (inline rules)
so CI catches the same class of mistake before plan/apply.

Usage:
  python3 deploy/scripts/ci/terraform-check-ecs-app-aws-sg-descriptions-ascii.py [REPO_ROOT]

Default REPO_ROOT is the parent of deploy/ (two levels up from this file).
Exit 0 if OK; 1 if violations; 2 on usage/environment errors.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RESOURCE_START = re.compile(
    r'^\s*resource\s+"aws_security_group"\s+"([^"]+)"\s*\{\s*$',
    re.MULTILINE,
)
# Double-quoted description (single line; handles \" inside string)
DESC_DOUBLE = re.compile(r'^\s*description\s*=\s*"((?:[^"\\]|\\.)*)"\s*$')
# Heredoc opener: description = <<-EOT or description = <<EOT
DESC_HEREDOC_OPEN = re.compile(r'^\s*description\s*=\s*<<-?(\w+)\s*$')


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _extract_quoted_string(line: str) -> str | None:
    m = DESC_DOUBLE.match(line)
    return m.group(1) if m else None


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _find_resource_end(text: str, open_brace_index: int) -> int:
    """Return index after closing `}` for resource block starting at open_brace_index (the `{`)."""
    depth = 0
    i = open_brace_index
    n = len(text)
    in_string = False
    escape = False
    string_quote: str | None = None

    while i < n:
        ch = text[i]

        if in_string:
            if string_quote == '"':
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                    string_quote = None
            else:  # heredoc - skip until we implement; should not appear inside our scan
                pass
            i += 1
            continue

        if ch == '"':
            in_string = True
            string_quote = '"'
            i += 1
            continue

        if ch == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(i + 2, n)
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1

    return -1


def _violations_in_body(body: str, file_path: Path, resource_name: str) -> list[str]:
    out: list[str] = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        q = _extract_quoted_string(line)
        if q is not None and not _is_ascii(q):
            bad = next((c for c in q if ord(c) > 127), "?")
            out.append(
                f"{file_path}:{resource_name}: non-ASCII in description (e.g. U+{ord(bad):04X}): "
                f"{line.strip()[:120]}"
            )
        hm = DESC_HEREDOC_OPEN.match(line)
        if hm:
            delim = hm.group(1)
            i += 1
            parts: list[str] = []
            while i < len(lines):
                if lines[i].strip() == delim:
                    content = "\n".join(parts)
                    if not _is_ascii(content):
                        out.append(
                            f"{file_path}:{resource_name}: non-ASCII in <<-{delim} description block"
                        )
                    break
                parts.append(lines[i])
                i += 1
        i += 1
    return out


def _scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    violations: list[str] = []
    for m in RESOURCE_START.finditer(text):
        resource_label = m.group(1)
        open_brace = text.find("{", m.start())
        if open_brace == -1:
            continue
        end = _find_resource_end(text, open_brace)
        if end == -1:
            violations.append(f"{path}:{resource_label}: unclosed resource block")
            continue
        body = text[open_brace + 1 : end - 1]
        violations.extend(_violations_in_body(body, path, resource_label))
    return violations


def main() -> int:
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else _default_repo_root()
    ecs_app = repo / "deploy" / "ecs-app"
    if not ecs_app.is_dir():
        print(f"ERROR: expected {ecs_app} (ecs-app root)", file=sys.stderr)
        return 2

    all_v: list[str] = []
    for tf in sorted(ecs_app.rglob("*.tf")):
        if ".terraform" in tf.parts:
            continue
        all_v.extend(_scan_file(tf))

    if all_v:
        print("Non-ASCII in aws_security_group description(s) (EC2 requires ASCII):", file=sys.stderr)
        for v in all_v:
            print(f"  {v}", file=sys.stderr)
        return 1

    print("OK: all aws_security_group descriptions under deploy/ecs-app are ASCII.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
