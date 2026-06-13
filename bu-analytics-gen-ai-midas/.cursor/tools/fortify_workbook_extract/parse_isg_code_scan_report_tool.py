#!/usr/bin/env python3
"""
CLI entry for parsing ISG/Fortify Developer Workbook PDF scan reports.

This is the **canonical** executable for this tool (``*_tool`` naming). Prefer invoking this file.

No imports at module load: the ``_ParseIsgEntry`` class pulls in ``sys``/``pathlib``,
adds this script's directory to ``sys.path``, then runs :func:`fortify_workbook_tool.runtime.launch_cli`
which installs missing dependencies (via pip) before importing the rest of the stack.
"""


class _ParseIsgEntry:
    """Lazy bootstrap — third-party packages resolve inside :func:`launch_cli`."""

    @staticmethod
    def main() -> None:
        import sys
        from pathlib import Path

        tools_dir = Path(__file__).resolve().parent
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))

        from fortify_workbook_tool.runtime import launch_cli

        raise SystemExit(launch_cli())


if __name__ == "__main__":
    _ParseIsgEntry.main()
