#!/usr/bin/env python3
"""Validate and deploy repo IaC per ``.cursor/rules/infras/tools.mdc``.

Runs the validation pipeline (stages 01–04) for Terraform and Helm, then optionally
applies changes to the project AWS account from ``.cursor/rules/constants/constants.mdc``.

Usage::

    python infra/scripts/iac_deploy.py <run-id>
    python infra/scripts/iac_deploy.py <run-id> --terraform-only
    python infra/scripts/iac_deploy.py <run-id> --helm-only
    python infra/scripts/iac_deploy.py <run-id> --deploy
    python infra/scripts/iac_deploy.py <run-id> --deploy-terraform
    python infra/scripts/iac_deploy.py <run-id> --deploy-helm

Reports:   ``.cursor/scratch/<run-id>/<run-id>-<tool>.rep``
Console:   ``.cursor/scratch/<run-id>/<run-id>-console-<tool>.log``

Requires: ``rich`` (``pip install rich``). External CLIs per ``infras/tools.mdc``.
AWS profile, region, and account are loaded from ``constants/constants.mdc`` and
verified with ``aws sts get-caller-identity`` before plan, apply, or Helm deploy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

try:
    from rich.console import Console
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print(
        "error: rich is required. Install with: pip install rich",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCRATCH_ROOT: Final[Path] = REPO_ROOT / ".cursor/scratch"
TF_ROOT: Final[Path] = REPO_ROOT / "infra/aws/aws_tf"
DEPLOYED_AWS: Final[Path] = REPO_ROOT / "infra/aws/deployed/aws"
POLICY_DIR: Final[Path] = REPO_ROOT / "policy"
CONSTANTS_PATH: Final[Path] = REPO_ROOT / ".cursor/rules/constants/constants.mdc"

_RUN_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_CONSTANT_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d+\.\s+\*\*`([A-Z_][A-Z0-9_]*)`\*\* — `([^`]+)`",
)


@dataclass(frozen=True)
class ProjectConstants:
    """AWS and project identity from constants.mdc."""

    aws_account_id: str
    aws_cli_profile: str
    aws_default_region: str
    prj_slug: str

    @property
    def eks_cluster_name(self) -> str:
        return self.prj_slug


@dataclass(frozen=True)
class ToolStep:
    """One external CLI invocation."""

    tool_id: str
    label: str
    argv: tuple[str, ...]
    cwd: Path | None = None
    optional: bool = False


@dataclass
class StepOutcome:
    """Result of a single tool step."""

    step: ToolStep
    ok: bool
    skipped: bool = False
    exit_code: int | None = None
    report_path: Path | None = None
    console_path: Path | None = None
    detail: str = ""


@dataclass
class Session:
    """Output directory and artifact naming for one run."""

    run_id: str
    output_dir: Path

    def report_path(self, tool_id: str) -> Path:
        return self.output_dir / f"{self.run_id}-{tool_id}.rep"

    def console_path(self, tool_id: str) -> Path:
        return self.output_dir / f"{self.run_id}-console-{tool_id}.log"


# ---------------------------------------------------------------------------
# Repo paths and constants
# ---------------------------------------------------------------------------


def find_repo_root() -> Path:
    """Return repository root (directory containing ``infra/aws/aws_tf``)."""
    if (REPO_ROOT / "infra/aws/aws_tf").is_dir():
        return REPO_ROOT
    current = Path(__file__).resolve().parent
    for directory in (current, *current.parents):
        if (directory / "infra/aws/aws_tf").is_dir():
            return directory
    msg = "Could not locate repository root (missing infra/aws/aws_tf)."
    raise RuntimeError(msg)


def load_project_constants() -> ProjectConstants:
    """Parse required AWS/project constants from constants.mdc."""
    if not CONSTANTS_PATH.is_file():
        msg = f"Missing project constants file: {CONSTANTS_PATH}"
        raise RuntimeError(msg)

    values: dict[str, str] = {}
    for line in CONSTANTS_PATH.read_text(encoding="utf-8").splitlines():
        match = _CONSTANT_LINE_RE.match(line.strip())
        if match:
            values[match.group(1)] = match.group(2)

    required = ("AWS_ACCOUNT_ID", "AWS_CLI_PROFILE", "AWS_DEFAULT_REGION", "PRJ_SLUG")
    missing = [name for name in required if name not in values]
    if missing:
        msg = f"Missing constants in {CONSTANTS_PATH}: {', '.join(missing)}"
        raise RuntimeError(msg)

    return ProjectConstants(
        aws_account_id=values["AWS_ACCOUNT_ID"],
        aws_cli_profile=values["AWS_CLI_PROFILE"],
        aws_default_region=values["AWS_DEFAULT_REGION"],
        prj_slug=values["PRJ_SLUG"],
    )


def build_process_env(constants: ProjectConstants) -> dict[str, str]:
    """Subprocess environment with project AWS profile and region."""
    env = os.environ.copy()
    env["AWS_PROFILE"] = constants.aws_cli_profile
    env["AWS_DEFAULT_REGION"] = constants.aws_default_region
    env["AWS_REGION"] = constants.aws_default_region
    return env


def discover_deployed_region_root(constants: ProjectConstants) -> Path | None:
    """``infra/aws/deployed/aws/<account>/<region>`` for this project."""
    expected = DEPLOYED_AWS / constants.aws_account_id / constants.aws_default_region
    if expected.is_dir():
        return expected
    if not DEPLOYED_AWS.is_dir():
        return None
    for account_dir in sorted(DEPLOYED_AWS.iterdir()):
        if not account_dir.is_dir():
            continue
        for region_dir in sorted(account_dir.iterdir()):
            if region_dir.is_dir():
                return region_dir
    return None


def discover_helm_charts(region_root: Path) -> list[tuple[str, Path]]:
    """Return ``(chart_slug, chart_dir)`` for every ``Chart.yaml`` under *region_root*."""
    charts: list[tuple[str, Path]] = []
    for chart_yaml in sorted(region_root.rglob("Chart.yaml")):
        chart_dir = chart_yaml.parent
        rel = chart_dir.relative_to(region_root)
        slug = rel.as_posix().replace("/", "-")
        charts.append((slug, chart_dir))
    return charts


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def _console() -> Console:
    return Console(stderr=True, highlight=False)


def run_with_spinner(
    console: Console,
    *,
    label: str,
    command: str,
    fn: Callable[[], StepOutcome],
) -> StepOutcome:
    """Execute *fn* under a blue spinner; tool output is not streamed."""
    spinner = Spinner(
        "dots",
        text=Text.assemble((label, "blue"), ("  ", ""), (command, "dim")),
        style="blue",
    )
    with Live(spinner, console=console, refresh_per_second=12, transient=False):
        return fn()


def print_error(console: Console, message: str) -> None:
    console.print(Text(message, style="red"))


def print_summary_table(console: Console, outcomes: Sequence[StepOutcome]) -> None:
    table = Table(title="IaC validate & deploy summary", show_header=True, header_style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Tool")
    table.add_column("Report")
    table.add_column("Console log")

    for outcome in outcomes:
        if outcome.skipped:
            status = Text("—", style="dim")
        elif outcome.ok:
            status = Text("✓", style="green")
        else:
            status = Text("✗", style="red")

        report_cell = outcome.report_path.name if outcome.report_path else "—"
        console_cell = outcome.console_path.name if outcome.console_path else "—"
        table.add_row(status, outcome.step.label, report_cell, console_cell)

    console.print()
    console.print(table)


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _command_label(argv: Sequence[str]) -> str:
    return " ".join(argv)


def _write_artifact(path: Path, *, header: str, stdout: str, stderr: str, exit_code: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            header,
            f"exit_code: {exit_code}",
            "",
            "=== stdout ===",
            stdout.rstrip(),
            "",
            "=== stderr ===",
            stderr.rstrip(),
            "",
        ],
    )
    path.write_text(body, encoding="utf-8")


def _write_report(path: Path, *, summary: str, stdout: str, stderr: str, exit_code: int) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = f"# IaC validate & deploy report\n# generated: {stamp}\n# summary: {summary}\n"
    _write_artifact(path, header=header, stdout=stdout, stderr=stderr, exit_code=exit_code)


def _extract_stdout_from_report(report_path: Path) -> str:
    text = report_path.read_text(encoding="utf-8")
    marker = "=== stdout ==="
    if marker not in text:
        return text
    _, _, remainder = text.partition(marker)
    stdout, _, _ = remainder.partition("=== stderr ===")
    return stdout.strip()


def require_binary(name: str) -> str | None:
    return shutil.which(name)


def execute_step(
    session: Session,
    step: ToolStep,
    *,
    env: dict[str, str],
) -> StepOutcome:
    """Run one tool; capture output to scratch files."""
    binary = step.argv[0]
    if require_binary(binary) is None:
        if step.optional:
            return StepOutcome(
                step=step,
                ok=True,
                skipped=True,
                detail=f"optional tool not on PATH: {binary}",
            )
        return StepOutcome(
            step=step,
            ok=False,
            detail=f"required tool not on PATH: {binary}",
        )

    cwd = step.cwd or REPO_ROOT
    report_path = session.report_path(step.tool_id)
    console_path = session.console_path(step.tool_id)

    try:
        completed = subprocess.run(
            list(step.argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as exc:
        return StepOutcome(step=step, ok=False, detail=str(exc))

    ok = completed.returncode == 0
    summary = "PASS" if ok else f"FAIL (exit {completed.returncode})"
    _write_report(
        report_path,
        summary=summary,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
    )
    _write_artifact(
        console_path,
        header=f"# console capture — {_command_label(step.argv)}",
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
    )

    detail = ""
    if not ok:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        detail = detail[-1] if detail else f"exit {completed.returncode}"

    return StepOutcome(
        step=step,
        ok=ok,
        exit_code=completed.returncode,
        report_path=report_path,
        console_path=console_path,
        detail=detail,
    )


def verify_aws_account(outcome: StepOutcome, constants: ProjectConstants) -> StepOutcome:
    """Ensure pre-flight identity matches AWS_ACCOUNT_ID from constants.mdc."""
    if outcome.skipped or not outcome.ok or outcome.report_path is None:
        return outcome

    raw = _extract_stdout_from_report(outcome.report_path)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return StepOutcome(
            step=outcome.step,
            ok=False,
            report_path=outcome.report_path,
            console_path=outcome.console_path,
            detail="Could not parse aws sts get-caller-identity JSON output.",
        )

    account = str(payload.get("Account", ""))
    if account != constants.aws_account_id:
        return StepOutcome(
            step=outcome.step,
            ok=False,
            report_path=outcome.report_path,
            console_path=outcome.console_path,
            detail=(
                f"Wrong AWS account: got {account}, expected {constants.aws_account_id} "
                f"(profile {constants.aws_cli_profile})."
            ),
        )
    return outcome


def run_steps(
    console: Console,
    session: Session,
    steps: Sequence[ToolStep],
    outcomes: list[StepOutcome],
    *,
    env: dict[str, str],
    post_step: Callable[[StepOutcome], StepOutcome] | None = None,
) -> bool:
    """Run steps in order; stop on first failure. Returns False if a step failed."""
    for step in steps:
        command = _command_label(step.argv)

        def _run() -> StepOutcome:
            outcome = execute_step(session, step, env=env)
            if post_step is not None:
                return post_step(outcome)
            return outcome

        outcome = run_with_spinner(console, label=step.label, command=command, fn=_run)
        outcomes.append(outcome)

        if outcome.skipped:
            console.print(
                Text(f"Skipped (optional): {step.label} — {outcome.detail}", style="dim"),
            )
            continue

        if outcome.ok:
            console.print(Text(f"OK: {step.label}", style="green"))
            continue

        print_error(console, f"Failed: {step.label}")
        if outcome.detail:
            print_error(console, outcome.detail)
        return False

    return True


# ---------------------------------------------------------------------------
# Pipeline builders (infras/tools.mdc)
# ---------------------------------------------------------------------------


def aws_preflight_step(constants: ProjectConstants) -> ToolStep:
    return ToolStep(
        "aws-preflight",
        "AWS account pre-flight",
        (
            "aws",
            "sts",
            "get-caller-identity",
            "--profile",
            constants.aws_cli_profile,
            "--region",
            constants.aws_default_region,
            "--output",
            "json",
        ),
    )


def eks_kubeconfig_step(constants: ProjectConstants) -> ToolStep:
    return ToolStep(
        "aws-kubeconfig",
        "EKS kubeconfig",
        (
            "aws",
            "eks",
            "update-kubeconfig",
            "--name",
            constants.eks_cluster_name,
            "--profile",
            constants.aws_cli_profile,
            "--region",
            constants.aws_default_region,
        ),
    )


def terraform_validation_steps(*, include_plan: bool = True) -> list[ToolStep]:
    """Stages 01, 02, 03, 04 for Terraform."""
    steps: list[ToolStep] = [
        ToolStep(
            "terraform-fmt",
            "Terraform format check",
            ("terraform", "fmt", "-recursive", "-check"),
            cwd=TF_ROOT,
        ),
        ToolStep(
            "tflint-init",
            "TFLint plugin init",
            ("tflint", "--init"),
            cwd=TF_ROOT,
        ),
        ToolStep(
            "tflint",
            "TFLint static analysis",
            ("tflint", "-f", "compact"),
            cwd=TF_ROOT,
        ),
        ToolStep(
            "trivy-terraform",
            "Trivy config scan (Terraform)",
            ("trivy", "config", "--format", "table", str(TF_ROOT)),
        ),
        ToolStep(
            "checkov-terraform",
            "Checkov scan (Terraform)",
            ("checkov", "-d", str(TF_ROOT), "--compact"),
        ),
        ToolStep(
            "terraform-init",
            "Terraform init",
            ("terraform", "init", "-input=false"),
            cwd=TF_ROOT,
        ),
        ToolStep(
            "terraform-validate",
            "Terraform validate",
            ("terraform", "validate"),
            cwd=TF_ROOT,
        ),
    ]
    if include_plan:
        steps.extend(
            [
                ToolStep(
                    "terraform-plan",
                    "Terraform plan",
                    (
                        "terraform",
                        "plan",
                        "-input=false",
                        "-out=tfplan.binary",
                    ),
                    cwd=TF_ROOT,
                ),
                ToolStep(
                    "terraform-plan-json",
                    "Terraform plan JSON export",
                    (
                        "bash",
                        "-lc",
                        "terraform show -json tfplan.binary > tfplan.json",
                    ),
                    cwd=TF_ROOT,
                ),
            ],
        )
        if POLICY_DIR.is_dir() and require_binary("conftest"):
            steps.append(
                ToolStep(
                    "conftest-terraform",
                    "Conftest policy (Terraform plan)",
                    (
                        "conftest",
                        "test",
                        "tfplan.json",
                        "-p",
                        str(POLICY_DIR),
                    ),
                    cwd=TF_ROOT,
                    optional=True,
                ),
            )
    return steps


def helm_validation_steps(charts: Sequence[tuple[str, Path]]) -> list[ToolStep]:
    """Stages 01–03 per chart; stage 04 template + optional Conftest."""
    steps: list[ToolStep] = []
    for slug, chart_dir in charts:
        release = slug.replace("-", "")[:32] or "release"
        steps.extend(
            [
                ToolStep(
                    f"helm-lint-{slug}",
                    f"Helm lint ({slug})",
                    ("helm", "lint", str(chart_dir)),
                ),
                ToolStep(
                    f"kubelinter-{slug}",
                    f"KubeLinter ({slug})",
                    ("kubelinter", "lint", f"{chart_dir}/"),
                ),
                ToolStep(
                    f"trivy-helm-{slug}",
                    f"Trivy config scan ({slug})",
                    ("trivy", "config", "--format", "table", str(chart_dir)),
                ),
                ToolStep(
                    f"checkov-helm-{slug}",
                    f"Checkov scan ({slug})",
                    ("checkov", "-d", str(chart_dir), "--compact"),
                ),
                ToolStep(
                    f"helm-template-{slug}",
                    f"Helm template render ({slug})",
                    (
                        "helm",
                        "template",
                        release,
                        str(chart_dir),
                    ),
                ),
            ],
        )
        if POLICY_DIR.is_dir() and require_binary("conftest"):
            steps.append(
                ToolStep(
                    f"conftest-helm-{slug}",
                    f"Conftest policy ({slug})",
                    (
                        "bash",
                        "-lc",
                        f"helm template {release} {chart_dir} | conftest test - -p {POLICY_DIR}",
                    ),
                    optional=True,
                ),
            )
    return steps


def terraform_deploy_steps(*, use_saved_plan: bool) -> list[ToolStep]:
    """Apply Terraform to the project AWS account after validation."""
    plan_file = TF_ROOT / "tfplan.binary"
    if use_saved_plan and plan_file.is_file():
        return [
            ToolStep(
                "terraform-apply",
                "Terraform apply (saved plan)",
                ("terraform", "apply", "-input=false", "tfplan.binary"),
                cwd=TF_ROOT,
            ),
        ]
    return [
        ToolStep(
            "terraform-apply",
            "Terraform apply",
            ("terraform", "apply", "-input=false", "-auto-approve"),
            cwd=TF_ROOT,
        ),
    ]


def helm_deploy_steps(
    charts: Sequence[tuple[str, Path]],
    *,
    namespace: str,
) -> list[ToolStep]:
    """Upgrade/install each chart into the project EKS cluster."""
    steps: list[ToolStep] = []
    for slug, chart_dir in charts:
        release = slug.replace("-", "")[:32] or "release"
        steps.append(
            ToolStep(
                f"helm-upgrade-{slug}",
                f"Helm upgrade --install ({slug})",
                (
                    "helm",
                    "upgrade",
                    "--install",
                    release,
                    str(chart_dir),
                    "--namespace",
                    namespace,
                    "--create-namespace",
                ),
            ),
        )
    return steps


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_aws_preflight(
    console: Console,
    session: Session,
    outcomes: list[StepOutcome],
    constants: ProjectConstants,
    env: dict[str, str],
) -> bool:
    def _verify(outcome: StepOutcome) -> StepOutcome:
        return verify_aws_account(outcome, constants)

    return run_steps(
        console,
        session,
        [aws_preflight_step(constants)],
        outcomes,
        env=env,
        post_step=_verify,
    )


def validate_terraform(
    console: Console,
    session: Session,
    outcomes: list[StepOutcome],
    *,
    include_plan: bool,
    env: dict[str, str],
) -> bool:
    return run_steps(
        console,
        session,
        terraform_validation_steps(include_plan=include_plan),
        outcomes,
        env=env,
    )


def validate_helm(
    console: Console,
    session: Session,
    outcomes: list[StepOutcome],
    charts: Sequence[tuple[str, Path]],
    *,
    env: dict[str, str],
) -> bool:
    if not charts:
        console.print(Text("No Helm charts found — skipping Helm validation.", style="yellow"))
        return True
    return run_steps(console, session, helm_validation_steps(charts), outcomes, env=env)


def deploy_terraform(
    console: Console,
    session: Session,
    outcomes: list[StepOutcome],
    *,
    env: dict[str, str],
    use_saved_plan: bool,
) -> bool:
    return run_steps(
        console,
        session,
        terraform_deploy_steps(use_saved_plan=use_saved_plan),
        outcomes,
        env=env,
    )


def deploy_helm(
    console: Console,
    session: Session,
    outcomes: list[StepOutcome],
    charts: Sequence[tuple[str, Path]],
    *,
    env: dict[str, str],
    constants: ProjectConstants,
    namespace: str,
) -> bool:
    if not charts:
        console.print(Text("No Helm charts found — skipping Helm deploy.", style="yellow"))
        return True
    if not run_steps(
        console,
        session,
        [eks_kubeconfig_step(constants)],
        outcomes,
        env=env,
    ):
        return False
    return run_steps(
        console,
        session,
        helm_deploy_steps(charts, namespace=namespace),
        outcomes,
        env=env,
    )


def prepare_session(run_id: str) -> Session:
    if not _RUN_ID_RE.fullmatch(run_id):
        msg = (
            "run-id must be 1–64 chars: letters, digits, dot, underscore, hyphen; "
            "must start with alphanumeric."
        )
        raise ValueError(msg)
    output_dir = SCRATCH_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return Session(run_id=run_id, output_dir=output_dir)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and optionally deploy Terraform and Helm to the project "
            "AWS account per infras/tools.mdc."
        ),
    )
    parser.add_argument(
        "run_id",
        help="Scratch folder name under .cursor/scratch/ (also used in artifact filenames).",
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--terraform-only",
        action="store_true",
        help="Run Terraform pipeline only.",
    )
    scope.add_argument(
        "--helm-only",
        action="store_true",
        help="Run Helm pipeline only.",
    )
    parser.add_argument(
        "--skip-plan",
        action="store_true",
        help="Skip terraform plan / plan-json / conftest-terraform steps.",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="After successful validation, deploy Terraform and Helm (mutating).",
    )
    parser.add_argument(
        "--deploy-terraform",
        action="store_true",
        help="After successful validation, run terraform apply (mutating).",
    )
    parser.add_argument(
        "--deploy-helm",
        action="store_true",
        help="After successful validation, run helm upgrade --install per chart (mutating).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    console = _console()

    try:
        session = prepare_session(args.run_id)
    except ValueError as exc:
        print_error(console, str(exc))
        return 2

    try:
        find_repo_root()
        constants = load_project_constants()
    except RuntimeError as exc:
        print_error(console, str(exc))
        return 2

    env = build_process_env(constants)
    region_root = discover_deployed_region_root(constants)
    charts = discover_helm_charts(region_root) if region_root else []

    deploy_terraform_flag = args.deploy or args.deploy_terraform
    deploy_helm_flag = args.deploy or args.deploy_helm

    run_terraform = not args.helm_only
    run_helm = not args.terraform_only
    include_plan = not args.skip_plan
    needs_aws = (
        (run_terraform and include_plan)
        or deploy_terraform_flag
        or deploy_helm_flag
    )

    helm_namespace = os.environ.get("IAC_DEPLOY_HELM_NAMESPACE", constants.prj_slug)

    console.print(
        Text.assemble(
            ("IaC validate & deploy: ", "bold"),
            (session.run_id, "cyan"),
            (" → ", ""),
            (str(session.output_dir), "dim"),
        ),
    )
    console.print(
        Text.assemble(
            ("AWS account ", "dim"),
            (constants.aws_account_id, "cyan"),
            (" · profile ", "dim"),
            (constants.aws_cli_profile, "cyan"),
            (" · region ", "dim"),
            (constants.aws_default_region, "cyan"),
        ),
    )

    outcomes: list[StepOutcome] = []
    all_ok = True

    if needs_aws:
        console.print(Text("\n— AWS pre-flight —", style="bold blue"))
        if not run_aws_preflight(console, session, outcomes, constants, env):
            all_ok = False

    if all_ok and run_terraform:
        console.print(Text("\n— Terraform validation —", style="bold blue"))
        if not validate_terraform(
            console,
            session,
            outcomes,
            include_plan=include_plan,
            env=env,
        ):
            all_ok = False

    if all_ok and run_helm:
        console.print(Text("\n— Helm validation —", style="bold blue"))
        if not validate_helm(console, session, outcomes, charts, env=env):
            all_ok = False

    if all_ok and deploy_terraform_flag:
        console.print(Text("\n— Terraform deploy —", style="bold blue"))
        if not deploy_terraform(
            console,
            session,
            outcomes,
            env=env,
            use_saved_plan=include_plan and run_terraform,
        ):
            all_ok = False

    if all_ok and deploy_helm_flag:
        console.print(Text("\n— Helm deploy —", style="bold blue"))
        if not deploy_helm(
            console,
            session,
            outcomes,
            charts,
            env=env,
            constants=constants,
            namespace=helm_namespace,
        ):
            all_ok = False

    print_summary_table(console, outcomes)

    if all_ok:
        console.print(Text("\nAll steps completed successfully.", style="green"))
        return 0

    console.print(Text("\nPipeline stopped due to failure.", style="red"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
