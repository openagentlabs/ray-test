#!/usr/bin/env python3
"""Replace sidebar nav (Start Here / Current / Future / Final) while preserving page-local tail links."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent

TAIL_MARKERS = (
    '<div class="nav-section">Future State Contents',
    '<div class="nav-section">Jump to Zone',
    '<div class="nav-section">Jump to Column',
    '<div class="nav-section">System Layer (jump)',
    '<div class="nav-section">System Layer</div>',  # layered exact
    '<div class="nav-section">On this page',
)


def extract_tail(after_logo: str) -> str:
    """Return sidebar tail (in-page anchors) after the global nav link blocks."""
    for mk in TAIL_MARKERS:
        i = after_logo.find(mk)
        if i != -1:
            return after_logo[i:].rstrip()
    return ""


# rel_path -> (p_start, p_future, p_final, overview_a, current_a, fut_act, fin_act[, overview_href_override])
NAV_MAP: dict[str, tuple] = {
    "start-here/index.html": ("../", "../future/", "../final/", True, False, None, None, "index.html"),
    "current/index.html": ("../", "../future/", "../final/", False, True, None, None),
    "final/index.html": ("../", "../future/", "", False, False, None, "index"),
    "final/architecture.html": ("../", "../future/", "", False, False, None, "architecture"),
    "final/classic/index.html": ("../../", "../../future/", "../../final/", False, False, None, "classic"),
    "final/layered/index.html": ("../../", "../../future/", "../../final/", False, False, None, "layered"),
    "final/microservice/index.html": ("../../", "../../future/", "../../final/", False, False, None, "microservice"),
    "final/developer/index.html": ("../../", "../../future/", "../../final/", False, False, None, "developer"),
    "final/requirements/index.html": ("../../", "../../future/", "../../final/", False, False, None, "requirements"),
    "future/index.html": ("../", "", "../final/", False, False, "index", None),
    "future/architecture.html": ("../", "", "../final/", False, False, "architecture", None),
    "future/classic/index.html": ("../../", "../", "../../final/", False, False, "classic", None),
    "future/layered/index.html": ("../../", "../", "../../final/", False, False, "layered", None),
    "future/microservice/index.html": ("../../", "../", "../../final/", False, False, "microservice", None),
    "future/developer/index.html": ("../../", "../", "../../final/", False, False, "developer", None),
    "future/requirements/index.html": ("../../", "../", "../../final/", False, False, "requirements", None),
    "future/decisions/index.html": ("../../", "../", "../../final/", False, False, "decisions", None),
}


def build_nav_v2(
    p_start: str,
    p_future: str,
    p_final: str,
    overview_active: bool,
    current_active: bool,
    future_active: Optional[str],
    final_active: Optional[str],
    overview_href: Optional[str] = None,
) -> str:
    """Build shared sidebar HTML. Optional overview_href overrides default Start Here link."""
    o_a = " active" if overview_active else ""
    c_a = " active" if current_active else ""
    oh = overview_href if overview_href is not None else f"{p_start}start-here/index.html"
    items = [
        ("index.html", "📋 System Layer Diagram", "index"),
        ("architecture.html", "🗺️ SVG Component Diagram", "architecture"),
        ("classic/index.html", "🏛️ Classic Architecture Diagram", "classic"),
        ("layered/index.html", "📐 Layered Architecture Diagram", "layered"),
        ("microservice/index.html", "🧩 Microservice Software Diagram", "microservice"),
        ("developer/index.html", "🧑‍💻 Developer Architecture Diagram", "developer"),
        ("requirements/index.html", "📜 Requirements", "requirements"),
        ("decisions/index.html", "⚖️ Architectural decisions", "decisions"),
    ]
    lines = [
        '      <div class="nav-section">Start Here</div>',
        f'      <a class="nav-item{o_a}" href="{oh}">👋 Overview</a>',
        "",
        '      <div class="nav-section">Current state</div>',
        f'      <a class="nav-item{c_a}" href="{p_start}current/index.html">🏛️ Current Architecture (Simplified)</a>',
        "",
        '      <div class="nav-section">Future state</div>',
    ]
    for href, label, key in items:
        act = " active" if future_active == key else ""
        lines.append(f'      <a class="nav-item{act}" href="{p_future}{href}">{label}</a>')
    lines.append('      <div class="nav-section">Final state</div>')
    for href, label, key in items:
        act = " active" if final_active == key else ""
        lines.append(f'      <a class="nav-item{act}" href="{p_final}{href}">{label}</a>')
    return "\n".join(lines)


def patch_file(rel: str) -> None:
    """Rewrite nav in one HTML file according to NAV_MAP."""
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    m = re.search(
        r"<nav class=\"sidebar\">\s*(<div class=\"sidebar-logo\">.*?</div>)\s*(.*?)\s*</nav>",
        text,
        re.DOTALL,
    )
    if not m:
        raise SystemExit(f"No nav match: {rel}")
    logo = m.group(1)
    after = m.group(2)
    tail = extract_tail(after)

    tup = NAV_MAP[rel]
    overview_override: Optional[str] = None
    if len(tup) == 8:
        (
            p_start,
            p_future,
            p_final,
            oa,
            ca,
            fut,
            fin,
            overview_override,
        ) = tup
    else:
        p_start, p_future, p_final, oa, ca, fut, fin = tup

    body = build_nav_v2(
        p_start,
        p_future,
        p_final,
        oa,
        ca,
        fut,
        fin,
        overview_href=overview_override,
    )
    new_inner = body + ("\n" + tail if tail else "") + "\n"

    new_nav = f'<nav class="sidebar">\n  {logo}\n{new_inner}</nav>'
    text2 = text[: m.start()] + new_nav + text[m.end() :]
    path.write_text(text2, encoding="utf-8")
    print("OK", rel)


def main() -> None:
    for rel in NAV_MAP:
        patch_file(rel)


if __name__ == "__main__":
    main()
