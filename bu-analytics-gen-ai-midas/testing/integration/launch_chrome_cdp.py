#!/usr/bin/env python3
"""
Launch Chrome/Edge with remote debugging enabled so pytest can connect to it.

Usage:
    python testing/integration/launch_chrome_cdp.py

Then in a second terminal:
    cd testing && python -m pytest integration/ -q -s

The script finds your installed Chrome or Edge, launches it on port 9222,
and opens the MIDAS app. Log in once with your SSO — pytest will read the
token from your open tab automatically.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

_PORT: int = 9222
_URL: str = "https://exldecision-ai-dev.exlservice.com"

_CHROME_CANDIDATES: list[str] = [
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    # Linux
    "google-chrome",
    "google-chrome-stable",
    "chromium-browser",
    "chromium",
    "microsoft-edge",
    # Windows (common paths via shutil)
    "chrome",
]


def _find_browser() -> str:
    for candidate in _CHROME_CANDIDATES:
        if candidate.startswith("/"):
            if shutil.which(candidate) or __import__("os").path.isfile(candidate):
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return ""


def main() -> None:
    browser = _find_browser()
    if not browser:
        print("ERROR: Could not find Chrome or Edge. Install Chrome and try again.", file=sys.stderr)
        sys.exit(1)

    args = [
        browser,
        f"--remote-debugging-port={_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
        _URL,
    ]

    print(f"Launching: {browser}")
    print(f"Remote debugging port: {_PORT}")
    print(f"Opening: {_URL}")
    print()
    print("1. Log in with your corporate SSO in the browser that opens.")
    print("2. Wait for the MIDAS dashboard to load.")
    print("3. Then run in a second terminal:")
    print("     cd testing && python -m pytest integration/ -q -s")
    print()
    print("Press Ctrl+C to quit Chrome when tests are done.")

    subprocess.run(args)


if __name__ == "__main__":
    main()
