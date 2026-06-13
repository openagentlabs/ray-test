"""Entry shim: provision dependencies, then run CLI."""

from __future__ import annotations


def main() -> None:
    """Console script entry (``uv run``, ``pip install`` scripts)."""
    raise SystemExit(launch_cli())


def launch_cli() -> int:
    """Install missing deps if needed, then execute :class:`FortifyWorkbenchToolCli`."""
    from fortify_workbook_tool.bootstrap import DependencyProvisioner
    from fortify_workbook_tool.cli import FortifyWorkbenchToolCli
    from fortify_workbook_tool.feedback import ColoredFeedback

    fb = ColoredFeedback()
    DependencyProvisioner().ensure(fb)
    return FortifyWorkbenchToolCli(fb).run()
