#!/usr/bin/env python3
"""Thin entry shim — prefer ``uv run jp-tool`` or the console script."""

from jp_tool.cli import main

if __name__ == "__main__":
    main()
