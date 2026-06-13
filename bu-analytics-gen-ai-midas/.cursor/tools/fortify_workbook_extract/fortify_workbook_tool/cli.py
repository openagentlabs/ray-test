"""Command-line entry: tool card, JSON jobs, legacy flags, colored feedback."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence, Union

from fortify_workbook_tool.aggregation import PriorityAggregator
from fortify_workbook_tool.constants import DEFAULT_STRIP_PREFIXES
from fortify_workbook_tool.domain import FormatterOptions
from fortify_workbook_tool.extraction_service import WorkbookExtractionService
from fortify_workbook_tool.feedback import ColoredFeedback
from fortify_workbook_tool.input_models import SimpleFileJobConfig, StructuredJobConfig
from fortify_workbook_tool.input_processor import ToolJsonInputProcessor
from fortify_workbook_tool.output_formatters import get_formatter
from fortify_workbook_tool.tool_card import TOOL_CARD_MARKDOWN, tool_descriptor_json
from fortify_workbook_tool.validators import ScanReportValidationError


class FortifyWorkbenchToolCli:
    """Coordinates validation → extraction → formatters with concise colored feedback."""

    def __init__(self, feedback: Optional[ColoredFeedback] = None) -> None:
        self._preset_feedback = feedback
        self._aggregator = PriorityAggregator()
        self._json_input = ToolJsonInputProcessor()

    def run(self, argv: Optional[Sequence[str]] = None) -> int:
        args_list = list(argv if argv is not None else sys.argv[1:])

        if not args_list:
            sys.stdout.write(TOOL_CARD_MARKDOWN)
            return 0

        parser = self._build_arg_parser()
        args = parser.parse_args(args_list)
        if getattr(args, "app_config", None) is not None:
            from fortify_workbook_tool.app_config import set_app_config_path

            set_app_config_path(args.app_config)
        if getattr(args, "format", None) is None and getattr(args, "pdf", None) is not None:
            from fortify_workbook_tool.app_config import get_app_config

            ac = get_app_config()
            df = ac.output.default_format
            args.format = df if df in ("csv", "json", "yaml") else "csv"

        if getattr(args, "print_csv_fields", False):
            from fortify_workbook_tool.report import issue_csv_field_names

            for name in issue_csv_field_names():
                sys.stdout.write(f"{name}\n")
            return 0

        fb = self._preset_feedback or ColoredFeedback()
        fb.configure(no_color=args.no_color)

        if args.tool_card_json:
            sys.stdout.write(json.dumps(tool_descriptor_json(), indent=2, ensure_ascii=False) + "\n")
            return 0

        extract_svc = WorkbookExtractionService(feedback=fb)

        if args.json_config is not None:
            return self._run_json_job(extract_svc, fb, args.json_config, args)

        if args.pdf is None:
            parser.error("Provide --pdf/--output/--format (legacy), or --json-config PATH (use '-' for stdin).")

        return self._run_legacy_pdf_args(extract_svc, fb, args)

    def _run_json_job(
        self,
        extract_svc: WorkbookExtractionService,
        fb: ColoredFeedback,
        config_ref: str,
        args: argparse.Namespace,
    ) -> int:
        fb.step("Reading JSON job configuration…")
        try:
            if config_ref.strip() == "-":
                raw = sys.stdin.read()
                cfg = self._json_input.parse_string(raw)
            else:
                cfg = self._json_input.parse_path(Path(config_ref))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            fb.error(f"Invalid JSON config: {exc}")
            return 1
        fb.ok("Job configuration OK.")

        try:
            extraction = extract_svc.extract(cfg.pdf_path)
        except ScanReportValidationError:
            fb.warn("Stopped: input file did not pass validation.")
            return 1
        except (FileNotFoundError, ValueError, OSError) as exc:
            fb.error(str(exc))
            return 1

        self._emit_warnings(fb, extraction.all_warnings())

        opts = self._formatter_options_from_job(cfg)
        fmt_kind = cfg.output_format if isinstance(cfg, SimpleFileJobConfig) else cfg.output.format
        formatter = get_formatter(fmt_kind)

        fb.step(f"Writing {fmt_kind.upper()} output…")
        try:
            if isinstance(cfg, SimpleFileJobConfig):
                formatter.write(extraction, cfg.output_path, opts)
                out_desc = str(cfg.output_path)
            else:
                out_path = cfg.output.path
                if out_path is not None:
                    formatter.write(extraction, out_path, opts)
                    out_desc = str(out_path)
                else:
                    sys.stdout.write(formatter.format_text(extraction, opts))
                    out_desc = "(stdout)"
        except (OSError, ValueError) as exc:
            fb.error(f"Output failed: {exc}")
            return 1

        fb.ok(f"Output written → {out_desc}")
        self._print_summary_block(fb, extraction, out_desc)
        fr = getattr(args, "final_report", None)
        if fr is not None:
            self._write_final_report(fb, extraction, out_desc, fmt_kind, Path(fr))
        if cfg.fail_on_warnings and extraction.all_warnings():
            fb.warn("Exit 2 (--fail-on-warnings): warnings occurred.")
            return 2
        return 0

    def _run_legacy_pdf_args(
        self,
        extract_svc: WorkbookExtractionService,
        fb: ColoredFeedback,
        args: argparse.Namespace,
    ) -> int:
        out_path = args.output
        if out_path is None:
            fb.error("Legacy mode requires --output PATH (or --csv alias).")
            return 1

        fmt_kind = args.format
        try:
            extraction = extract_svc.extract(args.pdf)
        except ScanReportValidationError:
            fb.warn("Stopped: input file did not pass validation.")
            return 1
        except (FileNotFoundError, ValueError, OSError) as exc:
            fb.error(str(exc))
            return 1

        self._emit_warnings(fb, extraction.all_warnings())

        opts = FormatterOptions(
            normalize_paths=not args.no_normalize_paths,
            strip_prefixes=self._effective_strip_prefixes(),
            include_priority_summary=True,
            schema_version=self._formatter_schema_version(),
        )
        formatter = get_formatter(fmt_kind)

        fb.step(f"Writing {fmt_kind.upper()}…")
        try:
            formatter.write(extraction, out_path, opts)
        except (OSError, ValueError) as exc:
            fb.error(f"Cannot write output: {exc}")
            return 1

        fb.ok(f"Output written → {out_path}")
        self._print_summary_block(fb, extraction, str(out_path))
        fr = getattr(args, "final_report", None)
        if fr is not None:
            self._write_final_report(fb, extraction, str(out_path), fmt_kind, Path(fr))

        if args.fail_on_warnings and extraction.all_warnings():
            fb.warn("Exit 2 (--fail-on-warnings): warnings occurred.")
            return 2
        return 0

    @staticmethod
    def _emit_warnings(fb: ColoredFeedback, warnings: Sequence[str]) -> None:
        if not warnings:
            fb.dim("(No loader/parser warnings.)")
            return
        fb.warn(f"{len(warnings)} warning(s):")
        for w in warnings:
            fb.dim(f"  • {w}")

    def _print_summary_block(self, fb: ColoredFeedback, extraction: object, out_desc: str) -> None:
        from fortify_workbook_tool.domain import WorkbookExtraction

        assert isinstance(extraction, WorkbookExtraction)
        summary = self._aggregator.summarize(extraction.issues)
        fb.info("Done.")
        fb.dim(
            f"  Issues: {summary.total} total · "
            f"C:{summary.critical} H:{summary.high} M:{summary.medium} L:{summary.low}"
            + (f" · other:{summary.other}" if summary.other else "")
        )
        fb.dim(f"  Rows written: {len(extraction.issues)} → {out_desc}")

    def _write_final_report(
        self,
        fb: ColoredFeedback,
        extraction: object,
        output_display: str,
        output_format: str,
        report_path: Path,
    ) -> None:
        from fortify_workbook_tool.domain import WorkbookExtraction
        from fortify_workbook_tool.report import build_final_report_from_extraction

        assert isinstance(extraction, WorkbookExtraction)
        fb.step("Writing final report…")
        report = build_final_report_from_extraction(
            extraction,
            output_display,
            output_format,
            self._formatter_schema_version(),
        )
        report.write(report_path)
        fb.ok(f"Final report written → {report_path}")

    @staticmethod
    def _effective_strip_prefixes() -> tuple[str, ...]:
        from fortify_workbook_tool.app_config import get_app_config

        prefixes = get_app_config().extraction.strip_prefixes
        return prefixes if prefixes else DEFAULT_STRIP_PREFIXES

    @staticmethod
    def _formatter_schema_version() -> str:
        from fortify_workbook_tool.app_config import get_app_config

        return get_app_config().formatter.schema_version

    @classmethod
    def _formatter_options_from_job(
        cls,
        cfg: Union[StructuredJobConfig, SimpleFileJobConfig],
    ) -> FormatterOptions:
        if isinstance(cfg, SimpleFileJobConfig):
            return FormatterOptions(
                normalize_paths=cfg.normalize_paths,
                strip_prefixes=cls._effective_strip_prefixes(),
                include_priority_summary=True,
                issue_field_subset=None,
                schema_version=cls._formatter_schema_version(),
            )
        out = cfg.output
        subset: Optional[tuple[str, ...]] = None
        if out.issue_field_subset is not None:
            subset = tuple(out.issue_field_subset)
        return FormatterOptions(
            normalize_paths=cfg.normalize_paths,
            strip_prefixes=cls._effective_strip_prefixes(),
            include_priority_summary=out.include_priority_summary,
            issue_field_subset=subset,
            schema_version=cls._formatter_schema_version(),
        )

    @staticmethod
    def _app_config_parent_parser() -> argparse.ArgumentParser:
        pre = argparse.ArgumentParser(add_help=False)
        pre.add_argument(
            "--app-config",
            type=Path,
            metavar="PATH",
            dest="app_config",
            help=(
                "Load application defaults from this TOML file "
                "(overrides env FORTIFY_WORKBOOK_APP_CONFIG). Same keys as app_config.toml beside the tool."
            ),
        )
        return pre

    @classmethod
    def _build_arg_parser(cls) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(
            description="Fortify Developer Workbook PDF → structured issues (CSV / JSON / YAML).",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="Run with no arguments to print the tool card.",
            parents=[cls._app_config_parent_parser()],
        )
        p.add_argument(
            "--tool-card-json",
            action="store_true",
            help="Emit machine-readable tool descriptor + JSON Schema for job configs (stdout).",
        )
        p.add_argument(
            "--json-config",
            metavar="PATH",
            help="JSON job file; use '-' to read from stdin (structured or simple_file job).",
        )
        p.add_argument("--pdf", type=Path, help="Input Developer Workbook PDF (legacy mode).")
        p.add_argument(
            "--output",
            "--csv",
            dest="output",
            type=Path,
            help="Output file path (legacy mode; required with --pdf).",
        )
        p.add_argument(
            "--format",
            choices=["csv", "json", "yaml"],
            default=None,
            help="Output format for legacy mode (default: output.default_format from app_config.toml).",
        )
        p.add_argument(
            "--no-normalize-paths",
            action="store_true",
            help="Do not normalize Downloads/... path prefixes (legacy mode).",
        )
        p.add_argument(
            "--fail-on-warnings",
            action="store_true",
            help="Exit with code 2 when loader/parser produced warnings.",
        )
        p.add_argument(
            "--no-color",
            action="store_true",
            help="Disable ANSI colors (also respects NO_COLOR env).",
        )
        p.add_argument(
            "--final-report",
            type=Path,
            metavar="PATH",
            dest="final_report",
            help="After a successful run, write a Markdown final report (counts, paths, CSV column list).",
        )
        p.add_argument(
            "--print-csv-fields",
            action="store_true",
            dest="print_csv_fields",
            help="Print FortifyIssue CSV column names (one per line) to stdout and exit.",
        )
        return p


def main() -> None:
    """Invoke CLI without bootstrap (dependencies must already be installed)."""
    raise SystemExit(FortifyWorkbenchToolCli().run())


if __name__ == "__main__":
    main()
