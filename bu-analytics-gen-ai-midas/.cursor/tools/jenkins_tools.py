#!/usr/bin/env python3
"""
jenkins_tools.py — MIDAS Jenkins CLI
================================================
Library : api4jenkins (gold standard; sync + async, object-oriented, full Jenkins API coverage)
Auth    : Jenkins username + API token via environment variables (preferred) or CLI flags.

ENVIRONMENT VARIABLES (preferred auth method)
  JENKINS_USER        Jenkins username
  JENKINS_API_TOKEN   Jenkins API token  (User → Configure → API Token in Jenkins UI)
  JENKINS_URL         Jenkins base URL   (override the compiled-in default)

FIRST-TIME SETUP (interactive — prompts for username + token, validates, saves permanently)
  python3 jenkins_tools.py setup

  This will:
    1. Prompt for your Jenkins username (pre-filled if JENKINS_USER is already set)
    2. Prompt for your API token (hidden input, paste and press Enter)
    3. Validate the credentials against Jenkins live
    4. Save them to ~/.zshrc (or ~/.bashrc) so every future terminal has them

  If your token has expired, any command will detect the 401 and prompt you to
  paste a fresh token — no need to manually edit ~/.zshrc.

  Create / rotate a token at:
    https://ucjenkinsdev.exlservice.com/user/<your-username>/configure
    → API Token → Add new Token → Generate

QUICK START
  # One-time setup:
  python3 jenkins_tools.py setup

  # Then run any command (credentials load automatically from ~/.zshrc):
  python3 jenkins_tools.py whoami
  python3 jenkins_tools.py status
  python3 jenkins_tools.py logs --tail 200
  python3 jenkins_tools.py logs --failed-stage          # full logs for failed stage only
  python3 jenkins_tools.py stages
  python3 jenkins_tools.py watch                        # live progress until build ends
  python3 jenkins_tools.py watch --interval 10          # poll every 10 s
  python3 jenkins_tools.py wait-for-start               # block until queued build starts
  python3 jenkins_tools.py build-info                   # detailed info on last build
  python3 jenkins_tools.py build-info --build 42        # detailed info on build 42
  python3 jenkins_tools.py approve
  python3 jenkins_tools.py trigger --param ENVIRONMENT=dev
  python3 jenkins_tools.py queue
  python3 jenkins_tools.py list-jobs
  python3 jenkins_tools.py abort
  python3 jenkins_tools.py enable
  python3 jenkins_tools.py disable
  python3 jenkins_tools.py artifacts
  python3 jenkins_tools.py nodes
  python3 jenkins_tools.py plugins
  python3 jenkins_tools.py server-info
  python3 jenkins_tools.py build-history --count 10
  python3 jenkins_tools.py test-results
  python3 jenkins_tools.py parameters

PASSING CREDENTIALS AS FLAGS (alternative; env vars take priority)
  python3 jenkins_tools.py --user YOUR_USER --api-token YOUR_TOKEN status

INSTALL DEPENDENCIES
  python3 -m pip install -r .cursor/scripts/requirements-jenkins-cli.txt

HELP FORMATS
  --help              Human-readable help (default argparse format)
  --help-ai           Machine-readable JSON schema for AI agents / tool callers
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Dependency check — deferred so --help-ai works without the library
# ---------------------------------------------------------------------------
_IMPORT_ERROR: Optional[str] = None
try:
    from api4jenkins import Jenkins
    from api4jenkins.exceptions import AuthenticationError, ItemNotFoundError, JenkinsAPIException
except ImportError as _ie:  # pragma: no cover
    _IMPORT_ERROR = str(_ie)
    Jenkins = None  # type: ignore[assignment,misc]
    AuthenticationError = Exception  # type: ignore[misc,assignment]
    ItemNotFoundError = Exception  # type: ignore[misc,assignment]
    JenkinsAPIException = Exception  # type: ignore[misc,assignment]


def _check_import() -> None:
    if _IMPORT_ERROR:
        print(
            "\n[ERROR] Required library 'api4jenkins' is not installed.\n"
            "Install it with:\n"
            "  python3 -m pip install -r .cursor/scripts/requirements-jenkins-cli.txt\n"
            "or:\n"
            "  python3 -m pip install 'api4jenkins>=2.1.0'\n",
            file=sys.stderr,
        )
        sys.exit(1)

# ---------------------------------------------------------------------------
# MIDAS defaults — override via env var JENKINS_URL / JENKINS_JOB
# ---------------------------------------------------------------------------

# Canonical Jenkins base URL for MIDAS
_DEFAULT_JENKINS_URL = "https://ucjenkinsdev.exlservice.com"

# Canonical full URL for the default MIDAS deploy pipeline job.
# This is the single source of truth; _DEFAULT_JOB_PATH is derived from it.
_DEFAULT_PIPELINE_URL = (
    "https://ucjenkinsdev.exlservice.com/job/exlerate/job/exlerate-solutions"
    "/job/MIDAS/job/bu-analytics-gen-ai-midas-deploy-eks"
)

# Slash-separated job path derived from the canonical URL above.
# api4jenkins accepts this form; it mirrors the /job/X/job/Y/... URL structure.
_DEFAULT_JOB_PATH = "/".join(
    seg
    for seg in _DEFAULT_PIPELINE_URL.replace(_DEFAULT_JENKINS_URL, "").split("/")
    if seg and seg != "job"
)

# The stage name from Jenkinsfile_Deploy_App that requires manual approval
_APPROVE_STAGE_NAME = "Approve deploy?"


# ---------------------------------------------------------------------------
# AI-agent help schema
# ---------------------------------------------------------------------------
_AI_HELP_SCHEMA: Dict[str, Any] = {
    "tool": "jenkins_tools",
    "version": "2.0.0",
    "description": (
        "Command-line interface for the MIDAS Jenkins pipeline. "
        "Provides read and write operations against the Jenkins REST API "
        "using api4jenkins. Auth uses JENKINS_USER + JENKINS_API_TOKEN env vars."
    ),
    "authentication": {
        "env_vars": {
            "JENKINS_USER": "Jenkins username (required)",
            "JENKINS_API_TOKEN": "Jenkins API token from User → Configure → API Token (required)",
            "JENKINS_URL": f"Jenkins base URL (optional, default: {_DEFAULT_JENKINS_URL})",
            "JENKINS_JOB": f"Default job path (optional, default derived from {_DEFAULT_PIPELINE_URL})",
        },
        "cli_flags": {
            "--user": "Jenkins username (overrides JENKINS_USER)",
            "--api-token": "Jenkins API token (overrides JENKINS_API_TOKEN)",
            "--url": "Jenkins base URL (overrides JENKINS_URL env var)",
        },
        "error_on_missing": True,
    },
    "global_flags": {
        "--user": "Jenkins username",
        "--api-token": "Jenkins API token",
        "--url": "Jenkins base URL",
        "--job": f"Job path (default: {_DEFAULT_JOB_PATH})",
        "--build": "Build number (default: lastBuild)",
        "--json": "Output as JSON (machine-readable)",
        "--help-ai": "Print this JSON schema and exit",
        "--OK_DELETE_MODIFY": (
            "SAFETY GATE. Must be passed for any command that MUTATES Jenkins "
            "state (queues a build, aborts a build, proceeds / aborts an "
            "approval gate, enables / disables the job, or lets `watch` "
            "auto-approve a pending input). Read-only commands do NOT need "
            "this flag. Without it, mutation commands exit with code 2 and a "
            "clear error describing the protected operation — so AI agents "
            "cannot accidentally trigger or abort a deploy."
        ),
    },
    "safety": {
        "flag": "--OK_DELETE_MODIFY",
        "required_for": [
            "trigger", "abort", "approve",
            "enable", "disable",
            "create-job", "update-job",
            "watch  (only the embedded auto-approve behaviour; read-only watch is unaffected)",
        ],
        "rule": (
            "Any subcommand that calls a mutating Jenkins API "
            "(`job.build()`, `build.stop()`, input `.proceed()` / `.abort()`, "
            "`job.enable()`, `job.disable()`) must be invoked with the "
            "`--OK_DELETE_MODIFY` global flag. If the flag is not present, "
            "the CLI exits with code 2 before any Jenkins API call is made "
            "and prints exactly which protected operation was blocked."
        ),
    },
    "commands": {
        "set-env": {
            "description": "Persist JENKINS_USER and JENKINS_API_TOKEN to ~/.zshrc / ~/.bashrc.",
            "flags": {
                "--user": "Jenkins username to persist (required)",
                "--api-token": "Jenkins API token to persist (required)",
                "--shell-rc": "Path to shell RC file (default: ~/.zshrc or ~/.bashrc)",
            },
            "side_effects": "Appends export lines to the target RC file.",
            "example": "jenkins_tools.py set-env --user alice --api-token TOKEN",
        },
        "whoami": {
            "description": "Print the authenticated Jenkins user details.",
            "flags": {},
            "example": "jenkins_tools.py whoami",
        },
        "server-info": {
            "description": "Print Jenkins server version, load stats, and executor summary.",
            "flags": {},
            "example": "jenkins_tools.py server-info",
        },
        "list-jobs": {
            "description": "List jobs/folders starting at a given path.",
            "flags": {
                "--path": "Folder path to list (default: root). Slash-separated.",
                "--depth": "Max depth to recurse (default: 1)",
            },
            "example": "jenkins_tools.py list-jobs --path exlerate/exlerate-solutions/MIDAS",
        },
        "status": {
            "description": "Show status of the default (or --job) pipeline build.",
            "flags": {
                "--build": "Specific build number (default: lastBuild)",
            },
            "example": "jenkins_tools.py status --build 42",
        },
        "build-history": {
            "description": "List recent builds for the job with result and timestamp.",
            "flags": {
                "--count": "Number of builds to list (default: 5)",
            },
            "example": "jenkins_tools.py build-history --count 10",
        },
        "logs": {
            "description": "Print console log for the selected build.",
            "flags": {
                "--tail": "Lines from end of log (default: 400; 0 = all)",
                "--follow": "Poll and stream log until build completes",
                "--interval": "Polling interval in seconds when --follow (default: 5)",
            },
            "example": "jenkins_tools.py logs --tail 200",
        },
        "stages": {
            "description": "List pipeline stages and their statuses via the Workflow API.",
            "flags": {
                "--build": "Specific build number (default: lastBuild)",
            },
            "example": "jenkins_tools.py stages",
        },
        "watch": {
            "description": (
                "Live-poll the pipeline: print stage transitions, and on "
                "finish render the final result (auto-extracting failure "
                "logs on FAILURE). Pending input gates are only "
                "auto-approved when the global `--OK_DELETE_MODIFY` flag is "
                "also passed — without it, watch detects the gate, prints a "
                "warning, and continues polling read-only."
            ),
            "conditional_mutation": (
                "Proceeds any pending input gate only when "
                "`--OK_DELETE_MODIFY` is set. Without the flag, watch is "
                "fully read-only."
            ),
            "flags": {
                "--build": "Specific build number (default: lastBuild)",
                "--interval": "Polling interval in seconds (default: 15)",
                "--log-stats": (
                    "Each poll, sample the console log and print a compact "
                    "delta: new line count, cumulative error / warning / "
                    "Terraform / Docker / Helm / kubectl / AWS event counts, "
                    "and the latest distinctive ERROR-like lines. Continues "
                    "polling until the build finishes successfully or fails."
                ),
            },
            "example": (
                "jenkins_tools.py --OK_DELETE_MODIFY watch --log-stats "
                "--interval 15   # with auto-approve"
            ),
        },
        "wait-for-start": {
            "description": (
                "Block until the most recently queued build starts, then "
                "print the build number and URL."
            ),
            "flags": {
                "--queue-url": "Queue item URL returned by trigger (optional)",
                "--timeout": "Max seconds to wait (default: 300)",
            },
            "example": "jenkins_tools.py wait-for-start --timeout 300",
        },
        "build-info": {
            "description": (
                "Detailed info on a build: trigger cause, parameters, Git "
                "SHA, stage breakdown with durations, and failure logs if "
                "the build is not SUCCESS."
            ),
            "flags": {
                "--build": "Specific build number (default: lastBuild)",
            },
            "example": "jenkins_tools.py build-info --build 42",
        },
        "parameters": {
            "description": "Show parameter definitions for the job.",
            "flags": {},
            "example": "jenkins_tools.py parameters",
        },
        "trigger": {
            "description": "Trigger a new build of the job, optionally with parameters.",
            "mutates_jenkins": True,
            "requires_flag": "--OK_DELETE_MODIFY",
            "flags": {
                "--param": "KEY=VALUE build parameter (repeatable)",
                "--wait": "Block until build completes and print result",
                "--timeout": "Seconds to wait when --wait (default: 600)",
            },
            "example": "jenkins_tools.py --OK_DELETE_MODIFY trigger --param ENVIRONMENT=dev --wait",
        },
        "abort": {
            "description": "Stop (abort) the currently running build.",
            "mutates_jenkins": True,
            "requires_flag": "--OK_DELETE_MODIFY",
            "flags": {
                "--build": "Specific build number to abort (default: lastBuild)",
            },
            "example": "jenkins_tools.py --OK_DELETE_MODIFY abort",
        },
        "approve": {
            "description": "Submit the pending manual-approval input in the pipeline.",
            "mutates_jenkins": True,
            "requires_flag": "--OK_DELETE_MODIFY",
            "flags": {
                "--build": "Build number with pending input (default: lastBuild)",
                "--input-id": "Explicit Jenkins input step id (skips auto-detect)",
                "--abort-input": "Abort the input step instead of proceeding",
            },
            "example": "jenkins_tools.py --OK_DELETE_MODIFY approve",
        },
        "queue": {
            "description": "List items currently in the Jenkins build queue.",
            "flags": {},
            "example": "jenkins_tools.py queue",
        },
        "artifacts": {
            "description": "List (and optionally download) build artifacts.",
            "flags": {
                "--build": "Build number (default: lastBuild)",
                "--download-dir": "Local directory to download artifacts into",
            },
            "example": "jenkins_tools.py artifacts --download-dir /tmp/arts",
        },
        "enable": {
            "description": "Enable the job (clears disabled state).",
            "mutates_jenkins": True,
            "requires_flag": "--OK_DELETE_MODIFY",
            "flags": {},
            "example": "jenkins_tools.py --OK_DELETE_MODIFY enable",
        },
        "disable": {
            "description": "Disable the job (prevents new builds).",
            "mutates_jenkins": True,
            "requires_flag": "--OK_DELETE_MODIFY",
            "flags": {},
            "example": "jenkins_tools.py --OK_DELETE_MODIFY disable",
        },
        "get-job-config": {
            "description": "Print the config.xml of the job at --target-job (or --job).",
            "flags": {
                "--target-job": "Slash-separated job path (overrides --job for this command).",
            },
            "example": (
                "jenkins_tools.py get-job-config "
                "--target-job exlerate/exlerate-solutions/MIDAS/midas-ai-gateway-tf-deploy-ORD1"
            ),
        },
        "create-job": {
            "description": (
                "Create a Jenkins job under --folder named --name from --template "
                "(rendered with --var KEY=VALUE substitutions for {{KEY}} placeholders). "
                "Refuses to overwrite existing jobs (use update-job for that)."
            ),
            "mutates_jenkins": True,
            "requires_flag": "--OK_DELETE_MODIFY",
            "flags": {
                "--folder":   "Folder path to create the job under.",
                "--name":     "New job's leaf name.",
                "--template": "Path to config.xml template file with {{KEY}} placeholders.",
                "--var":      "KEY=VALUE template substitution (repeatable).",
            },
            "example": (
                "jenkins_tools.py --OK_DELETE_MODIFY create-job "
                "--folder exlerate/exlerate-solutions/MIDAS "
                "--name midas-ai-gateway-tf-deploy-ORD1 "
                "--template deploy/ai_gateway/jenkins-job-templates/pipeline-job-template.xml "
                "--var REPO_URL=https://github.example/midas.git "
                "--var BRANCH=develop "
                "--var JENKINSFILE_PATH=deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD1_terraform "
                "--var DESCRIPTION='AI Gateway TF deploy (ORD1)'"
            ),
        },
        "update-job": {
            "description": (
                "Overwrite the config.xml of an existing job at --target-job from --template "
                "(with --var substitutions)."
            ),
            "mutates_jenkins": True,
            "requires_flag": "--OK_DELETE_MODIFY",
            "flags": {
                "--target-job": "Existing job's slash-separated path.",
                "--template":   "Path to config.xml template file with {{KEY}} placeholders.",
                "--var":        "KEY=VALUE template substitution (repeatable).",
            },
            "example": (
                "jenkins_tools.py --OK_DELETE_MODIFY update-job "
                "--target-job exlerate/exlerate-solutions/MIDAS/midas-ai-gateway-tf-deploy-ORD1 "
                "--template deploy/ai_gateway/jenkins-job-templates/pipeline-job-template.xml "
                "--var REPO_URL=https://github.example/midas.git --var BRANCH=develop "
                "--var JENKINSFILE_PATH=deploy/ai_gateway/jenkinsfiles/Jenkinsfile_ORD1_terraform "
                "--var DESCRIPTION='AI Gateway TF deploy (ORD1)'"
            ),
        },
        "nodes": {
            "description": "List Jenkins agents/nodes with online/offline status.",
            "flags": {},
            "example": "jenkins_tools.py nodes",
        },
        "plugins": {
            "description": "List installed Jenkins plugins with version and update status.",
            "flags": {
                "--updates-only": "Show only plugins with available updates",
            },
            "example": "jenkins_tools.py plugins --updates-only",
        },
        "test-results": {
            "description": "Show test result summary for the selected build.",
            "flags": {
                "--build": "Build number (default: lastBuild)",
            },
            "example": "jenkins_tools.py test-results",
        },
        "stats": {
            "description": (
                "Aggregate statistics for a build (and optionally the last N "
                "builds). For a single build: total duration, stage count, "
                "breakdown by stage status, slowest/fastest stage, average "
                "stage duration, queue wait vs estimate, artifact count, "
                "test summary (if any), failed stages, triggered-by, Git "
                "branch/SHA, and parameter count. With --history N > 1: adds "
                "success rate, aggregate duration (min/avg/max), and a "
                "compact pass/fail roster across the last N builds."
            ),
            "flags": {
                "--build": "Build number for single-build stats (default: lastBuild)",
                "--history": "Also aggregate across the last N builds (default: 1 = single build only)",
            },
            "returns": {
                "build": "Build number analysed",
                "status": "Final status (SUCCESS/FAILURE/ABORTED/BUILDING/...)",
                "duration_ms": "Total wall-clock duration of the build",
                "estimated_duration_ms": "Jenkins' estimated duration for the job",
                "duration_vs_estimate_pct": "Actual as percentage of estimate",
                "stage_count": "Number of pipeline stages executed",
                "stages_by_status": "Map of status -> count (SUCCESS, FAILURE, NOT_EXECUTED, ...)",
                "slowest_stage": "{name, duration_ms} of the longest stage",
                "fastest_stage": "{name, duration_ms} of the shortest stage that actually ran",
                "avg_stage_duration_ms": "Mean duration across executed stages",
                "total_stage_duration_ms": "Sum of all stage durations",
                "failed_stages": "Names of stages whose status is FAILED/FAILURE",
                "artifact_count": "Number of artifacts attached to the build",
                "test_summary": "{total, passed, failed, skipped} if a test report exists, else null",
                "triggered_by": "List of trigger descriptions (user / SCM / timer)",
                "parameter_count": "Number of build parameters",
                "git_branch": "Git branch name if resolvable from build actions",
                "git_sha": "Git commit SHA if resolvable from build actions",
                "history": (
                    "(when --history N > 1) "
                    "{analysed, success, failure, aborted, other, "
                    "success_rate_pct, duration_ms_min, duration_ms_avg, "
                    "duration_ms_max, builds: [{build, result, duration_ms}]}"
                ),
            },
            "example": "jenkins_tools.py stats --history 10 --json",
        },
    },
}


# ---------------------------------------------------------------------------
# Shell RC helpers — shared by setup and set-env
# ---------------------------------------------------------------------------

def _rc_path_for_shell(override: Optional[str] = None) -> Path:
    if override:
        return Path(override).expanduser()
    shell = os.environ.get("SHELL", "")
    return Path.home() / (".zshrc" if "zsh" in shell else ".bashrc")


def _write_creds_to_rc(user: str, token: str, rc_path: Path) -> None:
    """Write/replace the Jenkins credentials block in the shell RC file."""
    block = (
        "\n# Jenkins CLI credentials (set by jenkins_tools.py)\n"
        f'export JENKINS_USER="{user}"\n'
        f'export JENKINS_API_TOKEN="{token}"\n'
    )
    existing = rc_path.read_text() if rc_path.exists() else ""
    existing = re.sub(
        r"\n# Jenkins CLI credentials \(set by (?:jenkins_midas_deploy_cli|jenkins_tools)\.py[^\)]*\)\n"
        r'export JENKINS_USER="[^"]*"\n'
        r'export JENKINS_API_TOKEN="[^"]*"\n',
        "",
        existing,
    )
    rc_path.write_text(existing + block)
    # Also export into the current process so subsequent commands in this run work
    os.environ["JENKINS_USER"] = user
    os.environ["JENKINS_API_TOKEN"] = token


def _try_connect(url: str, user: str, token: str) -> Tuple[Any, bool]:
    """
    Attempt to create a Jenkins client and probe .version.
    Returns (client, ok). Never raises — returns (None, False) on any failure.
    """
    _check_import()
    try:
        client = Jenkins(url, auth=(user, token))
        _ = client.version
        return client, True
    except AuthenticationError:
        return None, False
    except Exception:
        return None, False


def _prompt_for_token(url: str, user: str) -> str:
    """Interactively prompt the user to paste a new API token. Returns the token string."""
    print(
        f"\n  Your token has expired or is invalid for user '{user}'.\n"
        f"\n  To generate a new token:\n"
        f"    1. Open: {url}/user/{user}/configure\n"
        f"    2. Click API Token → Add new Token → Generate\n"
        f"    3. Copy the token (it is only shown once)\n"
    )
    while True:
        token = getpass.getpass("  Paste your new Jenkins API token and press Enter: ").strip()
        if token:
            return token
        print("  [!] Token cannot be empty — please try again.")


# ---------------------------------------------------------------------------
# Credential resolution helpers
# ---------------------------------------------------------------------------

_OK_DELETE_MODIFY_BLOCKED_MSG = (
    "\n[ERROR] SAFETY GATE: refused to run a Jenkins-mutating operation "
    "({operation!r}) without the required global flag.\n\n"
    "This command would have called a MUTATING Jenkins API "
    "({effect}), so it is blocked by default to protect shared "
    "environments. Re-run with:\n\n"
    "  python3 {script} --OK_DELETE_MODIFY {rebuild}\n\n"
    "Only pass --OK_DELETE_MODIFY when you have explicit user consent to "
    "mutate Jenkins state.\n"
)


def _require_ok_delete_modify(
    ok_delete_modify: bool,
    operation: str,
    effect: str,
    argv_rebuild: Optional[List[str]] = None,
) -> None:
    """
    Exit(2) with a clear error if a Jenkins-mutating command was invoked
    without the `--OK_DELETE_MODIFY` global flag. Call this as the VERY
    FIRST step inside any gated command, before any Jenkins API call.

    Args:
        ok_delete_modify: The resolved value of the global flag.
        operation:        Short name of the gated operation (e.g. "trigger").
        effect:           One-line description of the mutation (e.g.
                          "queues a new build").
        argv_rebuild:     Tokens to reproduce the original command for the
                          user — defaults to argv[1:] minus the script name.
    """
    if ok_delete_modify:
        return
    script = Path(sys.argv[0]).name
    rebuild_tokens = argv_rebuild if argv_rebuild is not None else sys.argv[1:]
    rebuild = " ".join(rebuild_tokens).strip() or operation
    msg = _OK_DELETE_MODIFY_BLOCKED_MSG.format(
        operation=operation,
        effect=effect,
        script=script,
        rebuild=rebuild,
    )
    print(msg, file=sys.stderr)
    sys.exit(2)


def _resolve_credentials(args: argparse.Namespace) -> Tuple[str, str, str]:
    """
    Return (url, user, api_token).

    Priority: CLI flag > env var.
    If credentials are missing, direct the user to run `setup` and exit.
    Does NOT attempt a live validation here — that is done inside _connect so
    expired-token recovery can be offered interactively.
    """
    url = getattr(args, "url", None) or os.environ.get("JENKINS_URL") or _DEFAULT_JENKINS_URL
    user = getattr(args, "user", None) or os.environ.get("JENKINS_USER", "")
    token = getattr(args, "api_token", None) or os.environ.get("JENKINS_API_TOKEN", "")

    missing: List[str] = []
    if not user:
        missing.append("JENKINS_USER")
    if not token:
        missing.append("JENKINS_API_TOKEN")

    if missing:
        script = Path(sys.argv[0]).name
        print(
            f"\n[ERROR] Jenkins credentials not found ({', '.join(missing)}).\n\n"
            "Run the interactive setup command to enter and save them:\n\n"
            f"  python3 {script} setup\n\n"
            "This will prompt for your username and API token, validate them\n"
            f"against Jenkins, and save them to your shell profile permanently.\n\n"
            "Create / rotate a token at:\n"
            f"  {url}/user/<your-username>/configure  →  API Token → Add new Token\n",
            file=sys.stderr,
        )
        sys.exit(1)

    return url, user, token


def _connect(args: argparse.Namespace) -> Tuple[Any, str]:
    """
    Return (Jenkins client, job_path).

    If the stored credentials produce a 401 the user is prompted interactively
    to paste a fresh token. The new token is saved to ~/.zshrc automatically.
    Up to 3 attempts are allowed before aborting.
    """
    _check_import()
    url, user, token = _resolve_credentials(args)
    rc_path = _rc_path_for_shell(None)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        client, ok = _try_connect(url, user, token)
        if ok:
            if attempt > 1:
                # Token was refreshed — persist the new one
                _write_creds_to_rc(user, token, rc_path)
                print(f"\n[OK] New token saved to {rc_path}. Re-open terminals to pick it up.\n")
            break

        if attempt == max_attempts:
            print(
                f"\n[ERROR] Authentication failed after {max_attempts} attempts.\n"
                f"  User  : {user}\n"
                f"  URL   : {url}\n\n"
                "Run  python3 jenkins_tools.py setup  to reset credentials.\n",
                file=sys.stderr,
            )
            sys.exit(1)

        print(
            f"\n[WARNING] Authentication failed (attempt {attempt}/{max_attempts - 1}).\n"
            f"  User : {user}  |  URL : {url}"
        )
        token = _prompt_for_token(url, user)

    job_path = getattr(args, "job", None) or os.environ.get("JENKINS_JOB") or _DEFAULT_JOB_PATH
    return client, job_path


def _get_job(client: Jenkins, job_path: str) -> Any:
    try:
        job = client.get_job(job_path)
        if job is None:
            raise ItemNotFoundError(job_path)
        return job
    except (ItemNotFoundError, JenkinsAPIException):
        print(f"\n[ERROR] Job not found: {job_path!r}\n", file=sys.stderr)
        sys.exit(1)


def _console_text(build: Any) -> str:
    """
    Return the full console log as a plain string.
    api4jenkins.Build.console_text() may return str, bytes, or a generator
    depending on the version; normalise all variants here.
    """
    raw = build.console_text()
    if isinstance(raw, (str, bytes)):
        text = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
    else:
        # generator / iterator of str or bytes chunks
        chunks = []
        for chunk in raw:
            if isinstance(chunk, bytes):
                chunks.append(chunk.decode("utf-8", errors="replace"))
            else:
                chunks.append(str(chunk))
        text = "".join(chunks)
    return text


def _get_build(job: Any, build_number: Optional[int]) -> Any:
    if build_number is None:
        build = job.get_last_build()
    else:
        build = job[build_number]
    if build is None:
        label = "lastBuild" if build_number is None else str(build_number)
        print(f"\n[ERROR] Build {label!r} not found.\n", file=sys.stderr)
        sys.exit(1)
    return build


def _list_pending_input_actions(build: Any) -> List[Any]:
    """
    Return pending Pipeline input-step handles across api4jenkins versions.

    Older releases exposed WorkflowRun.get_pending_input_actions(). api4jenkins 2.x
    uses wfapi/pendingInputActions and PendingInputAction.submit() instead of .proceed().
    """
    if hasattr(build, "get_pending_input_actions"):
        try:
            return list(build.get_pending_input_actions())
        except Exception:
            pass
    try:
        desc = build.handle_req("GET", "wfapi/describe").json()
        links = desc.get("_links") or {}
        if not links.get("pendingInputActions"):
            return []
        arr = build.handle_req("GET", "wfapi/pendingInputActions").json()
        from api4jenkins.input import PendingInputAction

        out: List[Any] = []
        for action in arr:
            ad = dict(action)
            au = ad.get("abortUrl") or ""
            if "/job/" in au:
                ad["abortUrl"] = au[au.index("/job/") :]
            out.append(PendingInputAction(build.jenkins, ad))
        return out
    except Exception:
        pass
    if hasattr(build, "get_pending_input"):
        try:
            p = build.get_pending_input()
            return [p] if p is not None else []
        except Exception:
            pass
    return []


def _pending_input_proceed(action: Any) -> None:
    """Submit / proceed a pending input (provider API differs by api4jenkins version)."""
    if hasattr(action, "proceed"):
        action.proceed()
        return
    if hasattr(action, "submit"):
        action.submit()
        return
    raise RuntimeError("Cannot proceed pipeline input: no proceed/submit on action")


def _out(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, default=str))
    elif isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                print("  ".join(f"{k}={v}" for k, v in row.items()))
            else:
                print(row)
    elif isinstance(data, dict):
        for k, v in data.items():
            print(f"{k}: {v}")
    else:
        print(data)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_setup(url: str, shell_rc: Optional[str] = None) -> int:
    """
    Interactive first-time credential setup.

    Prompts for username + token, validates against Jenkins live,
    then saves to the shell RC file so every future terminal picks them up.
    If credentials already exist in the environment they are shown as defaults
    and the user can confirm or replace them.
    """
    _check_import()
    rc_path = _rc_path_for_shell(shell_rc)

    print(f"\n{'='*60}")
    print("  MIDAS Jenkins CLI — Credential Setup")
    print(f"{'='*60}")
    print(f"  Jenkins URL : {url}")
    print(f"  Saving to   : {rc_path}")
    print(f"{'='*60}\n")

    # Username
    existing_user = os.environ.get("JENKINS_USER", "").strip()
    if existing_user and existing_user not in ("your.name", ""):
        user_prompt = f"  Jenkins username [{existing_user}]: "
    else:
        user_prompt = "  Jenkins username: "

    user = input(user_prompt).strip()
    if not user:
        user = existing_user
    if not user:
        print("\n[ERROR] Username cannot be empty.", file=sys.stderr)
        return 1

    # Token
    print(f"\n  Generate a token at:\n    {url}/user/{user}/configure  →  API Token → Add new Token\n")
    existing_token = os.environ.get("JENKINS_API_TOKEN", "").strip()
    if existing_token and existing_token not in ("your-jenkins-api-token", ""):
        print("  (An existing token is saved — press Enter to keep it, or paste a new one)")
        token = getpass.getpass("  Jenkins API token: ").strip()
        if not token:
            token = existing_token
            print("  Using existing token.")
    else:
        token = getpass.getpass("  Jenkins API token: ").strip()

    if not token:
        print("\n[ERROR] API token cannot be empty.", file=sys.stderr)
        return 1

    # Validate
    print("\n  Validating credentials against Jenkins...", end=" ", flush=True)
    client, ok = _try_connect(url, user, token)
    if not ok:
        print("FAILED")
        print(
            f"\n[ERROR] Authentication failed for user '{user}'.\n"
            "  Double-check your username and that the token has not expired.\n"
            "  Run  setup  again with a freshly generated token.\n",
            file=sys.stderr,
        )
        return 1

    print("OK")

    # Persist
    _write_creds_to_rc(user, token, rc_path)

    # Show who Jenkins thinks this is
    try:
        me = client.me
        display = getattr(me, "full_name", None) or getattr(me, "id", user)
        print(f"\n  Authenticated as: {display}")
    except Exception:
        pass

    print(f"\n  Credentials saved to {rc_path}")
    print(f"  Open a new terminal (or run: source {rc_path}) to use them.\n")
    return 0


def cmd_set_env(args: argparse.Namespace) -> int:
    """Append export lines for JENKINS_USER and JENKINS_API_TOKEN to the shell RC file (non-interactive)."""
    user = args.user
    token = args.api_token
    if not user or not token:
        print("[ERROR] Both --user and --api-token are required for set-env.", file=sys.stderr)
        return 1

    rc_path = _rc_path_for_shell(getattr(args, "shell_rc", None))
    _write_creds_to_rc(user, token, rc_path)
    print(f"Credentials written to {rc_path}")
    print(f"Run: source {rc_path}  (or open a new terminal)")
    return 0


def cmd_whoami(client: Jenkins, as_json: bool) -> int:
    try:
        me = client.me
        data = {
            "id": me.id,
            "fullName": me.full_name,
            "description": getattr(me, "description", ""),
        }
        _out(data, as_json)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def cmd_server_info(client: Jenkins, as_json: bool) -> int:
    data = {
        "url": str(client.url),
        "version": client.version,
    }
    try:
        raw = client.api_json()
        data["numExecutors"] = raw.get("numExecutors")
        data["mode"] = raw.get("mode")
        data["description"] = raw.get("description") or ""
        overallLoad = raw.get("overallLoad", {})
        data["queueLength"] = overallLoad.get("queueLength", {}).get("sec10", {}).get("latest")
    except Exception:
        pass
    _out(data, as_json)
    return 0


def cmd_list_jobs(client: Jenkins, path: str, depth: int, as_json: bool) -> int:
    def _collect(folder: Any, current_path: str, remaining: int, results: list) -> None:
        try:
            for item in folder:
                item_path = f"{current_path}/{item.name}".lstrip("/")
                item_type = type(item).__name__
                results.append({"path": item_path, "type": item_type})
                if remaining > 1:
                    try:
                        _collect(item, item_path, remaining - 1, results)
                    except Exception:
                        pass
        except Exception:
            pass

    results: List[Dict[str, str]] = []
    if path:
        try:
            folder = client.get_job(path)
        except Exception:
            print(f"[ERROR] Path not found: {path!r}", file=sys.stderr)
            return 1
    else:
        folder = client

    _collect(folder, path or "", depth, results)

    if as_json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{r['type']:35s}  {r['path']}")
    return 0


def cmd_status(job: Any, build_number: Optional[int], as_json: bool) -> int:
    build = _get_build(job, build_number)
    building = build.building
    result = build.result
    status = "BUILDING" if building else (result or "UNKNOWN")

    data: Dict[str, Any] = {
        "build": build.number,
        "status": status,
        "url": str(build.url),
        "duration_ms": build.duration,
        "timestamp": build.timestamp,
        "description": getattr(build, "description", ""),
    }

    # Enrich with cause (what triggered this build)
    try:
        raw = build.api_json()
        causes = []
        for action in raw.get("actions", []):
            for cause in action.get("causes", []):
                causes.append(cause.get("shortDescription", ""))
        if causes:
            data["triggered_by"] = "; ".join(c for c in causes if c)
        # Parameters used for this build
        for action in raw.get("actions", []):
            params_list = action.get("parameters", [])
            if params_list:
                data["parameters"] = {p["name"]: p.get("value", "") for p in params_list}
                break
    except Exception:
        pass

    # Stage summary
    try:
        wf = build.get_wf_api()
        stage_list = wf.get("stages", [])
        if stage_list:
            data["stages"] = [
                {
                    "name": s.get("name", "?"),
                    "status": s.get("status") or s.get("state") or "?",
                    "duration_ms": s.get("durationMillis", 0),
                }
                for s in stage_list
            ]
    except Exception:
        pass

    if as_json:
        _out(data, True)
        return 0

    # Human-readable
    status_icon = {"SUCCESS": "✅", "FAILURE": "❌", "ABORTED": "🚫", "BUILDING": "🔄"}.get(status, "❓")
    print(f"\n{'─'*60}")
    print(f"  Build   : #{data['build']}  {status_icon} {status}")
    print(f"  URL     : {data['url']}")
    if data.get("triggered_by"):
        print(f"  Trigger : {data['triggered_by']}")
    if data.get("parameters"):
        print(f"  Params  :")
        for k, v in data["parameters"].items():
            print(f"             {k} = {v}")
    if data.get("stages"):
        print(f"  Stages  :")
        icons = {"SUCCESS": "✅", "FAILED": "❌", "FAILURE": "❌", "IN_PROGRESS": "🔄",
                 "PAUSED": "⏸", "ABORTED": "🚫", "NOT_EXECUTED": "⬜"}
        for s in data["stages"]:
            ic = icons.get(s["status"].upper(), "❓")
            dur = f"  ({s['duration_ms']//1000}s)" if s["duration_ms"] else ""
            print(f"             {ic} {s['name']}{dur}")
    print(f"{'─'*60}\n")
    return 0


def cmd_build_history(job: Any, count: int, as_json: bool) -> int:
    rows: List[Dict[str, Any]] = []
    for build in job.iter_all_builds():
        building = build.building
        result = build.result
        row: Dict[str, Any] = {
            "build": build.number,
            "status": "BUILDING" if building else (result or "UNKNOWN"),
            "timestamp": build.timestamp,
            "duration_ms": build.duration,
            "url": str(build.url),
        }
        # Enrich with trigger cause and key parameters
        try:
            raw = build.api_json()
            for action in raw.get("actions", []):
                causes = action.get("causes", [])
                if causes:
                    row["triggered_by"] = causes[0].get("shortDescription", "")
                    break
            for action in raw.get("actions", []):
                params_list = action.get("parameters", [])
                if params_list:
                    row["parameters"] = {
                        p["name"]: p.get("value", "")
                        for p in params_list
                        if p["name"] in ("ENVIRONMENT", "GIT_BRANCH", "DEPLOY_ALB_NLB")
                    }
                    break
        except Exception:
            pass
        rows.append(row)
        if len(rows) >= count:
            break

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return 0

    icons = {"SUCCESS": "✅", "FAILURE": "❌", "ABORTED": "🚫", "BUILDING": "🔄"}
    print(f"\n  {'#':>5}  {'Status':<12}  {'Triggered by':<35}  {'Duration':>8}  URL")
    print(f"  {'─'*5}  {'─'*12}  {'─'*35}  {'─'*8}  {'─'*40}")
    for r in rows:
        ic = icons.get(r["status"], "❓")
        trig = (r.get("triggered_by") or "")[:34]
        dur_s = (r["duration_ms"] or 0) // 1000
        dur_str = f"{dur_s//60}m{dur_s%60:02d}s" if dur_s >= 60 else f"{dur_s}s"
        print(f"  {r['build']:>5}  {ic} {r['status']:<10}  {trig:<35}  {dur_str:>8}  {r['url']}")
    print()
    return 0


def cmd_logs(
    job: Any,
    build_number: Optional[int],
    tail: int,
    follow: bool,
    interval: int,
    failed_stage: bool,
) -> int:
    build = _get_build(job, build_number)

    if follow:
        print(f"[INFO] Streaming log for build #{build.number} (Ctrl-C to stop) ...\n")
        try:
            for line in build.progressive_output():
                print(line, end="")
            final_result = build.result
            print(f"\n[INFO] Build #{build.number} complete: {final_result}")
            if final_result not in (None, "SUCCESS"):
                print(f"\n[HINT] Build failed. Run:  logs --failed-stage  to see only the failure logs.")
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted.")
        return 0

    if failed_stage:
        # Fetch full log and extract the section around the first FAILED stage
        text = _console_text(build)

        # Try to identify the failed stage name from workflow API
        failed_stage_name: Optional[str] = None
        try:
            wf = build.get_wf_api()
            for s in wf.get("stages", []):
                st = (s.get("status") or "").upper()
                if st in ("FAILED", "FAILURE"):
                    failed_stage_name = s.get("name")
                    break
        except Exception:
            pass

        lines = text.splitlines()
        result = build.result or "UNKNOWN"
        print(f"\n{'='*70}")
        print(f"  BUILD #{build.number}  |  RESULT: {result}")
        print(f"  URL: {build.url}")
        if failed_stage_name:
            print(f"  FAILED STAGE: {failed_stage_name}")
        print(f"{'='*70}\n")

        if failed_stage_name:
            # Find the log section for the failed stage
            start_idx = 0
            end_idx = len(lines)
            in_stage = False
            stage_start = 0
            for i, line in enumerate(lines):
                if f"[Pipeline] // stage" in line or f"Stage \"{failed_stage_name}\"" in line:
                    if not in_stage and failed_stage_name.lower() in line.lower():
                        in_stage = True
                        stage_start = max(0, i - 2)
                if in_stage and i > stage_start + 5:
                    if "[Pipeline] // stage" in line and i > stage_start + 10:
                        end_idx = i + 3
                        break
            if in_stage:
                start_idx = stage_start
            else:
                # Fall back to last N lines containing ERROR / FAILED / Exception
                error_lines = [
                    i for i, l in enumerate(lines)
                    if any(k in l for k in ("ERROR", "FAILED", "Exception", "Error:", "FATAL", "Caused by"))
                ]
                if error_lines:
                    start_idx = max(0, error_lines[0] - 20)
                    end_idx = min(len(lines), error_lines[-1] + 40)
                else:
                    start_idx = max(0, len(lines) - 200)

            excerpt = lines[start_idx:end_idx]
            print(f"  Showing lines {start_idx+1}–{min(end_idx, len(lines))} of {len(lines)} total\n")
            print("\n".join(excerpt))
        else:
            # No stage info — print last N lines with error context
            error_lines = [
                i for i, l in enumerate(lines)
                if any(k in l for k in ("ERROR", "FAILED", "Exception", "Error:", "FATAL", "Caused by"))
            ]
            if error_lines:
                start_idx = max(0, error_lines[0] - 10)
                end_idx = min(len(lines), error_lines[-1] + 30)
                print(f"  Error context: lines {start_idx+1}–{end_idx} of {len(lines)} total\n")
                print("\n".join(lines[start_idx:end_idx]))
            else:
                excerpt = lines[-200:] if len(lines) > 200 else lines
                print("\n".join(excerpt))

        print(f"\n{'='*70}")
        print(f"  Full log: {build.url}console")
        print(f"{'='*70}\n")
        return 0

    # Default: print tail lines of full console log
    text = _console_text(build)
    lines = text.splitlines()

    print(f"\n{'─'*60}")
    print(f"  Build #{build.number}  |  {build.result or 'BUILDING'}  |  {build.url}")
    print(f"  Total lines: {len(lines)}" + (f"  (showing last {tail})" if tail > 0 and len(lines) > tail else ""))
    print(f"{'─'*60}\n")

    if tail > 0 and len(lines) > tail:
        lines = lines[-tail:]
    print("\n".join(lines))
    return 0


def cmd_stages(job: Any, build_number: Optional[int], as_json: bool) -> int:
    build = _get_build(job, build_number)

    def _print_tree(stages: Any, depth: int = 0) -> List[Dict]:
        rows = []
        if not isinstance(stages, list):
            return rows
        for st in stages:
            if not isinstance(st, dict):
                continue
            name = st.get("name", "?")
            status = st.get("status") or st.get("state") or "?"
            pad = "  " * depth
            rows.append({"name": name, "status": status, "depth": depth})
            if not as_json:
                print(f"{pad}{name}\t{status}")
            nested = st.get("stages") or []
            rows.extend(_print_tree(nested, depth + 1))
        return rows

    try:
        wf = build.get_wf_api()
        stages = wf.get("stages", [])
    except Exception:
        # Fall back to raw api/json
        try:
            raw = build.api_json()
            stages = raw.get("stages", [])
        except Exception:
            stages = []

    if not stages:
        print("[INFO] No stage data available (may not be a Pipeline build).", file=sys.stderr)
        return 0

    rows = _print_tree(stages)
    if as_json:
        print(json.dumps(rows, indent=2))

    # Show pending inputs (api4jenkins 1.x vs 2.x compatible)
    try:
        pending = _list_pending_input_actions(build)
        if pending:
            hint = "\n[INFO] Pending input actions:"
            if as_json:
                hint_data = []
                for p in pending:
                    raw = getattr(p, "raw", {}) or {}
                    pid = raw.get("id", getattr(p, "id", ""))
                    msg = raw.get("message", getattr(p, "message", "") or "")
                    hint_data.append({"id": pid, "message": msg})
                print(json.dumps({"pending_inputs": hint_data}, indent=2))
            else:
                print(hint, file=sys.stderr)
                for p in pending:
                    raw = getattr(p, "raw", {}) or {}
                    pid = raw.get("id", getattr(p, "id", ""))
                    msg = raw.get("message", getattr(p, "message", "") or "")
                    print(f"  id={pid}  message={str(msg)[:120]}", file=sys.stderr)
                if any((_APPROVE_STAGE_NAME in str((getattr(p, "raw", {}) or {}).get("message", "") or getattr(p, "message", "") or "")) for p in pending):
                    print(
                        f"\n>>> Run is paused at '{_APPROVE_STAGE_NAME}' — run: approve",
                        file=sys.stderr,
                    )
    except Exception:
        pass
    return 0


def cmd_parameters(job: Any, as_json: bool) -> int:
    try:
        raw = job.api_json()
        props = raw.get("property", [])
        params: List[Dict] = []
        for prop in props:
            for pd in prop.get("parameterDefinitions", []):
                params.append({
                    "name": pd.get("name"),
                    "type": pd.get("type"),
                    "default": pd.get("defaultParameterValue", {}).get("value"),
                    "description": pd.get("description", ""),
                })
        if not params:
            print("[INFO] No parameters defined for this job.", file=sys.stderr)
            return 0
        _out(params, as_json)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def cmd_trigger(job: Any, params: List[str], wait: bool, timeout: int, as_json: bool) -> int:
    param_dict: Dict[str, str] = {}
    for p in params:
        if "=" not in p:
            print(f"[ERROR] Parameter must be KEY=VALUE, got: {p!r}", file=sys.stderr)
            return 1
        k, _, v = p.partition("=")
        param_dict[k] = v

    try:
        item = job.build(**param_dict) if param_dict else job.build()
    except Exception as exc:
        print(f"[ERROR] Trigger failed: {exc}", file=sys.stderr)
        return 1

    print(f"[INFO] Build queued. Queue item URL: {item.url}")

    if not wait:
        return 0

    print(f"[INFO] Waiting for build to start (timeout {timeout}s) ...")
    deadline = time.time() + timeout
    build = None
    while time.time() < deadline:
        build = item.get_build()
        if build:
            break
        time.sleep(3)

    if build is None:
        print("[ERROR] Timed out waiting for build to start.", file=sys.stderr)
        return 1

    print(f"[INFO] Build #{build.number} started: {build.url}")
    print("[INFO] Streaming output ...")
    try:
        for line in build.progressive_output():
            print(line, end="")
    except KeyboardInterrupt:
        print("\n[INFO] Output streaming interrupted (build may still be running).")
        return 0

    result = build.result
    data = {"build": build.number, "result": result, "url": str(build.url)}
    _out(data, as_json)
    return 0 if result == "SUCCESS" else 1


def cmd_abort(job: Any, build_number: Optional[int], as_json: bool) -> int:
    build = _get_build(job, build_number)
    if not build.building:
        msg = f"Build #{build.number} is not currently running (result={build.result})."
        if as_json:
            print(json.dumps({"error": msg}))
        else:
            print(f"[INFO] {msg}")
        return 1
    try:
        build.stop()
        data: Dict[str, Any] = {
            "build": build.number,
            "action": "aborted",
            "url": str(build.url),
        }
        if not as_json:
            print(f"\n🚫 Build #{build.number} aborted successfully.")
            print(f"   URL: {build.url}\n")
        _out(data, as_json) if as_json else None
        return 0
    except Exception as exc:
        print(f"[ERROR] Abort failed: {exc}", file=sys.stderr)
        return 1


def cmd_approve(
    job: Any,
    build_number: Optional[int],
    input_id: Optional[str],
    abort_input: bool,
    as_json: bool,
) -> int:
    build = _get_build(job, build_number)
    try:
        pending = _list_pending_input_actions(build)
    except Exception as exc:
        print(f"[ERROR] Cannot retrieve pending inputs: {exc}", file=sys.stderr)
        return 1

    if not pending:
        msg = "No pending input actions — pipeline is not waiting for approval."
        if as_json:
            print(json.dumps({"error": msg}))
        else:
            print(f"[INFO] {msg}", file=sys.stderr)
        return 1

    def _pid(p: Any) -> str:
        raw = getattr(p, "raw", {}) or {}
        return str(raw.get("id", getattr(p, "id", "")))

    def _pmsg(p: Any) -> str:
        raw = getattr(p, "raw", {}) or {}
        return str(raw.get("message", getattr(p, "message", "") or ""))

    chosen = None
    if input_id:
        for p in pending:
            if _pid(p) == input_id:
                chosen = p
                break
        if chosen is None:
            print(f"[ERROR] Input id {input_id!r} not found.", file=sys.stderr)
            return 1
    else:
        for p in pending:
            msg = _pmsg(p) + (getattr(p, "proceed_text", "") or "")
            if _APPROVE_STAGE_NAME in msg:
                chosen = p
                break
        chosen = chosen or pending[0]

    try:
        if abort_input:
            chosen.abort()
            action = "aborted"
        else:
            _pending_input_proceed(chosen)
            action = "approved"
        data = {"input_id": _pid(chosen), "action": action, "build": build.number}
        _out(data, as_json)
        return 0
    except Exception as exc:
        print(f"[ERROR] Input action failed: {exc}", file=sys.stderr)
        return 1


def cmd_queue(client: Jenkins, as_json: bool) -> int:
    rows: List[Dict[str, Any]] = []
    try:
        for item in client.queue.api_json().get("items", []):
            rows.append({
                "id": item.get("id"),
                "why": item.get("why", ""),
                "task": (item.get("task") or {}).get("name", ""),
                "url": item.get("url", ""),
            })
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    if not rows:
        print("[INFO] Build queue is empty.")
        return 0
    _out(rows, as_json)
    return 0


def cmd_artifacts(job: Any, build_number: Optional[int], download_dir: Optional[str], as_json: bool) -> int:
    build = _get_build(job, build_number)
    try:
        artifacts = list(build.iter_artifacts())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if not artifacts:
        print("[INFO] No artifacts for this build.")
        return 0

    rows = [{"name": a.name, "url": str(a.url)} for a in artifacts]
    _out(rows, as_json)

    if download_dir:
        dest = Path(download_dir)
        dest.mkdir(parents=True, exist_ok=True)
        for a in artifacts:
            target = dest / a.name
            print(f"  Downloading {a.name} → {target}")
            a.save(str(target))
        print(f"[INFO] {len(artifacts)} artifact(s) saved to {dest}")
    return 0


def cmd_enable(job: Any, as_json: bool) -> int:
    try:
        job.enable()
        data = {"action": "enabled", "job": job.name}
        _out(data, as_json)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def cmd_disable(job: Any, as_json: bool) -> int:
    try:
        job.disable()
        data = {"action": "disabled", "job": job.name}
        _out(data, as_json)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def _render_template(template_path: str, vars_kv: List[str]) -> str:
    """Read template_path and substitute every {{KEY}} with the matching value.

    vars_kv items are KEY=VALUE strings. Substitution is literal (no escaping).
    Raises ValueError if any {{KEY}} placeholder remains unsubstituted.
    """
    p = Path(template_path)
    if not p.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    body = p.read_text(encoding="utf-8")
    subs: Dict[str, str] = {}
    for kv in vars_kv:
        if "=" not in kv:
            raise ValueError(f"--var must be KEY=VALUE, got: {kv!r}")
        k, v = kv.split("=", 1)
        subs[k.strip()] = v
    for k, v in subs.items():
        body = body.replace("{{" + k + "}}", v)
    leftover = re.findall(r"\{\{([A-Z0-9_]+)\}\}", body)
    if leftover:
        raise ValueError(
            "Unsubstituted placeholders remain in rendered config: "
            + ", ".join(sorted(set(leftover)))
        )
    return body


def cmd_get_job_config(client: Any, job_path: str, as_json: bool) -> int:
    """Fetch the config.xml for an existing Jenkins job."""
    try:
        job = client.get_job(job_path)
    except Exception as exc:
        print(f"[ERROR] Job not found: {job_path!r} ({exc})", file=sys.stderr)
        return 1
    try:
        cfg = job.configure()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch config: {exc}", file=sys.stderr)
        return 1
    if as_json:
        _out({"job": job_path, "config_xml": cfg}, True)
    else:
        sys.stdout.write(cfg if isinstance(cfg, str) else cfg.decode("utf-8", errors="replace"))
    return 0


def cmd_create_job(
    client: Any,
    folder_path: str,
    job_name: str,
    config_xml: str,
    as_json: bool,
) -> int:
    """Create a Jenkins job under folder_path with the given config XML.

    folder_path: slash-separated folder path (no leading slash), e.g.
                 "exlerate/exlerate-solutions/MIDAS".
    job_name:    new job's leaf name, e.g. "midas-ai-gateway-tf-deploy-ORD1".
    config_xml:  fully-rendered Jenkins config XML body.
    """
    full_path = f"{folder_path.rstrip('/')}/{job_name}".lstrip("/")
    try:
        existing = None
        try:
            existing = client.get_job(full_path)
        except Exception:
            existing = None
        if existing is not None:
            print(
                f"[ERROR] Job already exists: {full_path!r}. "
                "Use `update-job` to overwrite its config.",
                file=sys.stderr,
            )
            return 1

        try:
            folder = client.get_job(folder_path) if folder_path else client
        except Exception as exc:
            print(f"[ERROR] Folder not found: {folder_path!r} ({exc})", file=sys.stderr)
            return 1

        try:
            folder.create(job_name, config_xml)
        except AttributeError:
            client.create_job(full_path, config_xml)

        data = {"action": "created", "job": full_path}
        _out(data, as_json)
        return 0
    except Exception as exc:
        print(f"[ERROR] Failed to create job {full_path!r}: {exc}", file=sys.stderr)
        return 1


def cmd_update_job(
    client: Any,
    job_path: str,
    config_xml: str,
    as_json: bool,
) -> int:
    """Overwrite the config of an existing Jenkins job."""
    try:
        job = client.get_job(job_path)
    except Exception as exc:
        print(f"[ERROR] Job not found: {job_path!r} ({exc})", file=sys.stderr)
        return 1
    try:
        job.configure(config_xml)
    except Exception as exc:
        print(f"[ERROR] Failed to update config for {job_path!r}: {exc}", file=sys.stderr)
        return 1
    data = {"action": "updated", "job": job_path}
    _out(data, as_json)
    return 0


def cmd_nodes(client: Jenkins, as_json: bool) -> int:
    rows: List[Dict[str, Any]] = []
    try:
        for node in client.get_nodes():
            rows.append({
                "name": node.name,
                "offline": node.offline,
                "num_executors": getattr(node, "num_executors", "?"),
                "description": getattr(node, "description", ""),
            })
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    _out(rows, as_json)
    return 0


def cmd_plugins(client: Jenkins, updates_only: bool, as_json: bool) -> int:
    rows: List[Dict[str, Any]] = []
    try:
        for plugin in client.get_plugins():
            has_update = getattr(plugin, "has_update", False)
            if updates_only and not has_update:
                continue
            rows.append({
                "short_name": plugin.short_name,
                "version": plugin.version,
                "has_update": has_update,
                "enabled": getattr(plugin, "enabled", True),
            })
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    if not rows:
        print("[INFO] No plugins found (or no updates available).")
        return 0
    _out(rows, as_json)
    return 0


def cmd_test_results(job: Any, build_number: Optional[int], as_json: bool) -> int:
    build = _get_build(job, build_number)
    try:
        report = build.get_test_report()
        if report is None:
            print("[INFO] No test report for this build.")
            return 0
        data = {
            "build": build.number,
            "total": report.total_count,
            "failed": report.fail_count,
            "skipped": report.skip_count,
            "passed": report.pass_count,
        }
        _out(data, as_json)
        return 0
    except Exception as exc:
        print(f"[ERROR] Test report unavailable: {exc}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# New commands: watch, wait-for-start, build-info
# ---------------------------------------------------------------------------

_LOG_STATS_PATTERNS = [
    # label, compiled regex (applied per-line, case-sensitive unless noted)
    ("error",    re.compile(r"\b(?:ERROR|FATAL|FAILED|Failure|Exception|Traceback|Caused by|AccessDenied|UnauthorizedOperation)\b")),
    ("warning",  re.compile(r"\b(?:WARN|WARNING|Deprecated)\b")),
    ("tf",       re.compile(r"\b(?:terraform|Terraform)\b|Plan:\s|Apply complete|Destroy complete|resource\s+\"")),
    ("docker",   re.compile(r"\bStep\s+\d+/\d+\b|docker (?:build|push|pull)|Pushed|Digest:\s+sha256:|^Successfully built\b|^Successfully tagged\b", re.MULTILINE)),
    ("helm",     re.compile(r"\bhelm\b|Release \"[^\"]+\" has been (?:upgraded|installed)|STATUS:\s+deployed|LAST DEPLOYED:")),
    ("kubectl",  re.compile(r"\bkubectl\b|pod/\S+\s+(?:created|deleted)|deployment\.apps/\S+\s+(?:created|configured|deleted)|rollout status")),
    ("aws",      re.compile(r"\b(?:aws|sts|eks|ecr|iam)\s+\w+|arn:aws:[\w:-]+")),
]

# Most recent ERROR/WARN lines to surface on each poll (quick triage).
_LOG_RECENT_ERROR_RE = re.compile(
    r"\b(?:ERROR|FATAL|FAILED|Exception|Caused by|AccessDenied|UnauthorizedOperation|Error:)\b"
)


def _parse_log_stats(text: str) -> Dict[str, Any]:
    """
    Scan the full console log `text` once and return a compact stats dict:

      {
        "total_lines": int,
        "total_bytes": int,
        "counts":   {label -> int}      # cumulative across the whole log so far
        "recent_errors": [str, ...]     # last up-to-5 distinctive ERROR-like lines
      }

    Deliberately cheap: one pass per regex over the string. Safe to run every
    poll interval in `watch --log-stats` — the log is fetched progressively
    and typically only adds a few hundred lines between polls.
    """
    lines = text.splitlines()
    counts: Dict[str, int] = {}
    for label, rx in _LOG_STATS_PATTERNS:
        # re.findall on the flat text is faster than iterating lines for most regexes,
        # but we want per-line counts so overlapping same-line hits don't double-count.
        hits = 0
        for ln in lines:
            if rx.search(ln):
                hits += 1
        counts[label] = hits

    recent_errors: List[str] = []
    for ln in reversed(lines):
        s = ln.strip()
        if not s:
            continue
        if _LOG_RECENT_ERROR_RE.search(s):
            # keep short, drop ANSI-ish prefixes
            recent_errors.append(s[:240])
            if len(recent_errors) >= 5:
                break
    recent_errors.reverse()

    return {
        "total_lines": len(lines),
        "total_bytes": len(text),
        "counts": counts,
        "recent_errors": recent_errors,
    }


def _render_log_stats_delta(
    current: Dict[str, Any],
    previous: Optional[Dict[str, Any]],
) -> str:
    """
    Build a compact single-line summary of log activity since the previous
    poll. Used inside `watch --log-stats`. Returns '' when there is nothing
    interesting to say (no new lines AND no new errors/warnings).
    """
    prev_counts = (previous or {}).get("counts", {}) if previous else {}
    prev_lines = (previous or {}).get("total_lines", 0)

    delta_lines = max(0, current["total_lines"] - prev_lines)
    bits: List[str] = [f"log=+{delta_lines} lines (total {current['total_lines']})"]

    # Per-category deltas (only show when > 0 or when cumulative > 0)
    for label in ("error", "warning", "tf", "docker", "helm", "kubectl", "aws"):
        cur = current["counts"].get(label, 0)
        prv = prev_counts.get(label, 0)
        d = cur - prv
        if d > 0:
            bits.append(f"{label}=+{d} ({cur})")
        elif cur > 0 and previous is None:
            # First poll — still show cumulative so the user has a baseline
            bits.append(f"{label}={cur}")

    # Nothing new and no baseline to print
    if delta_lines == 0 and previous is not None and all(
        current["counts"].get(l, 0) == prev_counts.get(l, 0)
        for l, _ in _LOG_STATS_PATTERNS
    ):
        return ""

    return "   📊  " + "  |  ".join(bits)


def cmd_watch(
    job: Any,
    build_number: Optional[int],
    interval: int,
    as_json: bool,
    log_stats: bool = False,
    ok_delete_modify: bool = False,
) -> int:
    """
    Poll the pipeline every `interval` seconds, print stage progress, detect
    approval gates, and report the final outcome with failure log extraction.

    SAFETY:
        Watch is READ-ONLY by default. When the caller passes
        `--OK_DELETE_MODIFY` at the top-level, watch will also proceed any
        pending pipeline input step the first time it appears (the MIDAS
        "Approve deploy?" gate). Without that flag, watch still DETECTS the
        gate and tells the user it is there — but does not proceed it.

    When `log_stats` is True, also sample the console log each poll and print
    a compact one-line delta of log activity (line count, errors, warnings,
    terraform / docker / helm / kubectl / AWS events) along with the most
    recent ERROR-like lines. This makes in-flight progress visible without
    needing a separate `logs --follow` stream.
    """
    build = _get_build(job, build_number)
    print(f"\n🔭 Watching build #{build.number}: {build.url}")
    extras: List[str] = []
    if log_stats:
        extras.append("--log-stats")
    if ok_delete_modify:
        extras.append("--OK_DELETE_MODIFY")
    extra = f"  ({', '.join(extras)})" if extras else ""
    print(f"   Polling every {interval}s{extra}  —  Ctrl-C to stop watching (build keeps running)")
    if not ok_delete_modify:
        print(
            "   ⚠️  Running in READ-ONLY mode — pending input gates will be "
            "reported but NOT auto-approved."
        )
        print(
            "     Re-run with `--OK_DELETE_MODIFY` to auto-approve detected "
            "approval gates."
        )
    print()

    _stage_icons = {
        "SUCCESS": "✅", "FAILED": "❌", "FAILURE": "❌",
        "IN_PROGRESS": "🔄", "PAUSED": "⏸", "ABORTED": "🚫",
        "NOT_EXECUTED": "⬜", "SKIPPED": "⬜",
    }
    last_stage_statuses: Dict[str, str] = {}
    auto_approved_ids: set = set()
    reported_pending_ids: set = set()
    prev_log_stats: Optional[Dict[str, Any]] = None
    last_recent_errors_key: Optional[str] = None

    def _render_stages(stages: List[Dict]) -> None:
        for s in stages:
            name = s.get("name", "?")
            status = (s.get("status") or s.get("state") or "?").upper()
            prev = last_stage_statuses.get(name)
            ic = _stage_icons.get(status, "❓")
            dur_ms = s.get("durationMillis", 0) or 0
            dur_str = f"  ({dur_ms//1000}s)" if dur_ms else ""
            if status != prev:
                print(f"   {ic} {name}{dur_str}  [{status}]")
                last_stage_statuses[name] = status

    def _auto_approve_pending(build: Any) -> None:
        """
        Detect pending input steps. When `ok_delete_modify` is True, proceed
        each the first time it appears. When False, only report that a gate
        exists (once per id) and keep polling — do NOT mutate the build.
        """
        pending = _list_pending_input_actions(build)
        for p in pending:
            raw = getattr(p, "raw", {}) or {}
            pid = str(raw.get("id", getattr(p, "id", "")))
            msg = str(raw.get("message", getattr(p, "message", "") or ""))

            if not ok_delete_modify:
                if pid in reported_pending_ids:
                    continue
                reported_pending_ids.add(pid)
                print(
                    f"\n⏸  PENDING APPROVAL DETECTED: {msg!r}  (input id: {pid})"
                )
                print(
                    "   ⚠️  SAFETY GATE: not auto-approving — "
                    "--OK_DELETE_MODIFY was not passed."
                )
                print(
                    "     To proceed this gate automatically, re-run watch with:"
                )
                print(
                    f"       python3 {Path(sys.argv[0]).name} "
                    f"--OK_DELETE_MODIFY watch --build {build.number}\n"
                )
                continue

            if pid in auto_approved_ids:
                continue
            print(f"\n✅ AUTO-APPROVING pipeline gate: {msg!r}  (input id: {pid})")
            try:
                _pending_input_proceed(p)
                auto_approved_ids.add(pid)
                print(f"   ✅ Approved — pipeline will continue.\n")
            except Exception as exc:
                print(f"   [WARN] Could not auto-approve {pid!r}: {exc}", file=sys.stderr)

    try:
        while True:
            # Refresh build object
            build = _get_build(job, build.number)
            building = build.building
            result = build.result

            # Fetch stages
            stages: List[Dict] = []
            try:
                wf = build.get_wf_api()
                stages = wf.get("stages", [])
            except Exception:
                pass

            _render_stages(stages)

            # Auto-approve any pending gates
            _auto_approve_pending(build)

            # Log-derived stats (opt-in via --log-stats)
            if log_stats:
                try:
                    text = _console_text(build)
                    cur_stats = _parse_log_stats(text)
                    line = _render_log_stats_delta(cur_stats, prev_log_stats)
                    if line:
                        print(line)
                    # Only re-print recent ERROR lines when the set actually changes,
                    # so the user isn't spammed with the same 5 lines every poll.
                    recent = cur_stats.get("recent_errors") or []
                    key = "\n".join(recent)
                    if recent and key != last_recent_errors_key:
                        print("      ↳ recent ERROR-like lines:")
                        for ln in recent[-3:]:
                            # Keep a single visible line per error for readability
                            print(f"        {ln[:200]}")
                        last_recent_errors_key = key
                    prev_log_stats = cur_stats
                except Exception as exc:
                    print(f"   [WARN] log-stats sample failed: {exc}", file=sys.stderr)

            if not building:
                # Build has finished
                final_icon = _stage_icons.get(result or "", "❓")
                print(f"\n{'='*60}")
                print(f"  Build #{build.number} FINISHED  {final_icon}  {result or 'UNKNOWN'}")
                print(f"  URL: {build.url}")
                print(f"{'='*60}\n")

                if result not in (None, "SUCCESS", "ABORTED"):
                    print("❌ Build FAILED — extracting failure logs...\n")
                    cmd_logs(job, build.number, tail=0, follow=False,
                             interval=interval, failed_stage=True)

                if as_json:
                    out_obj: Dict[str, Any] = {
                        "build": build.number,
                        "result": result,
                        "url": str(build.url),
                        "stages": [
                            {"name": s.get("name"), "status": s.get("status")}
                            for s in stages
                        ],
                    }
                    if log_stats and prev_log_stats is not None:
                        out_obj["log_stats"] = prev_log_stats
                    print(json.dumps(out_obj, indent=2))
                return 0 if result == "SUCCESS" else 1

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[INFO] Watch stopped. Build #{build.number} may still be running.")
        print(f"       {build.url}")
        return 0


def cmd_wait_for_start(
    job: Any,
    queue_url: Optional[str],
    timeout: int,
    as_json: bool,
) -> int:
    """
    Wait for the most recent queued item (or a specific queue URL) to leave the
    queue and become an active build. Returns the build number once it starts.
    """
    print(f"[INFO] Waiting for build to start (timeout {timeout}s) ...")
    deadline = time.time() + timeout
    build = None

    if queue_url:
        # Resolve queue item from URL — derive item id from URL
        try:
            import re as _re
            m = _re.search(r"/queue/item/(\d+)/", queue_url)
            if not m:
                print(f"[ERROR] Cannot parse queue item id from URL: {queue_url}", file=sys.stderr)
                return 1
        except Exception as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

    # Poll lastBuild to detect when a new build appears
    try:
        last_known = job.get_last_build()
        last_known_number = last_known.number if last_known else 0
    except Exception:
        last_known_number = 0

    while time.time() < deadline:
        try:
            candidate = job.get_last_build()
            if candidate and candidate.number > last_known_number:
                build = candidate
                break
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(5)

    print()

    if build is None:
        print(f"\n[ERROR] Timed out after {timeout}s — build never started.", file=sys.stderr)
        print(f"  Check the Jenkins queue: python3 jenkins_tools.py queue")
        return 1

    data = {
        "build": build.number,
        "status": "BUILDING" if build.building else (build.result or "UNKNOWN"),
        "url": str(build.url),
    }
    if as_json:
        print(json.dumps(data, indent=2))
    else:
        print(f"\n🚀 Build #{build.number} started!")
        print(f"   Status : {data['status']}")
        print(f"   URL    : {build.url}")
        print(f"\n   Watch it live: python3 jenkins_tools.py watch --build {build.number}\n")
    return 0


def cmd_build_info(job: Any, build_number: Optional[int], as_json: bool) -> int:
    """
    Print comprehensive information about a single build: trigger cause,
    parameters, Git revision, stage breakdown with durations, and full
    error log if the build failed.
    """
    build = _get_build(job, build_number)
    building = build.building
    result = build.result
    status = "BUILDING" if building else (result or "UNKNOWN")

    info: Dict[str, Any] = {
        "build": build.number,
        "status": status,
        "url": str(build.url),
        "duration_ms": build.duration,
        "timestamp": build.timestamp,
    }

    # Detailed raw JSON from Jenkins
    try:
        raw = build.api_json()
        # Triggered by
        for action in raw.get("actions", []):
            causes = action.get("causes", [])
            if causes:
                info["triggered_by"] = [c.get("shortDescription", "") for c in causes]
                break
        # Parameters
        for action in raw.get("actions", []):
            params = action.get("parameters", [])
            if params:
                info["parameters"] = {p["name"]: p.get("value", "") for p in params}
                break
        # Git info
        for action in raw.get("actions", []):
            branch_data = action.get("buildsByBranchName", {})
            last_built_revision = action.get("lastBuiltRevision", {})
            if last_built_revision:
                info["git_sha"] = last_built_revision.get("SHA1", "")
                branches = last_built_revision.get("branch", [])
                if branches:
                    info["git_branch"] = branches[0].get("name", "")
                break
        info["keep_log"] = raw.get("keepLog", False)
        info["node"] = raw.get("builtOn", "master")
    except Exception:
        pass

    # Stages with full detail
    try:
        wf = build.get_wf_api()
        stages = wf.get("stages", [])
        info["stages"] = []
        for s in stages:
            stage_entry: Dict[str, Any] = {
                "name": s.get("name", "?"),
                "status": s.get("status") or s.get("state") or "?",
                "duration_ms": s.get("durationMillis", 0),
                "start_time_ms": s.get("startTimeMillis", 0),
            }
            # Nested steps / errors
            error = s.get("error", {})
            if error:
                stage_entry["error_message"] = error.get("message", "")
                stage_entry["error_type"] = error.get("type", "")
            info["stages"].append(stage_entry)
    except Exception:
        pass

    if as_json:
        print(json.dumps(info, indent=2, default=str))
        return 0

    # Human-readable
    _icons = {"SUCCESS": "✅", "FAILURE": "❌", "FAILED": "❌", "ABORTED": "🚫",
              "BUILDING": "🔄", "IN_PROGRESS": "🔄", "PAUSED": "⏸",
              "NOT_EXECUTED": "⬜", "SKIPPED": "⬜"}

    print(f"\n{'='*70}")
    ic = _icons.get(status.upper(), "❓")
    print(f"  BUILD #{info['build']}  {ic}  {status}")
    print(f"  URL       : {info['url']}")
    dur_s = (info.get("duration_ms") or 0) // 1000
    dur_str = f"{dur_s//60}m{dur_s%60:02d}s" if dur_s >= 60 else f"{dur_s}s"
    print(f"  Duration  : {dur_str}")
    if info.get("triggered_by"):
        print(f"  Triggered : {'; '.join(info['triggered_by'])}")
    if info.get("node"):
        print(f"  Node      : {info['node']}")
    if info.get("git_branch"):
        print(f"  Branch    : {info['git_branch']}")
    if info.get("git_sha"):
        print(f"  SHA       : {info['git_sha'][:12]}")

    if info.get("parameters"):
        print(f"\n  Parameters:")
        for k, v in info["parameters"].items():
            print(f"    {k:<35} = {v}")

    if info.get("stages"):
        print(f"\n  Stages:")
        for s in info["stages"]:
            sic = _icons.get((s["status"] or "").upper(), "❓")
            dur_ms = s.get("duration_ms") or 0
            sdur = f"{dur_ms//1000}s" if dur_ms else "-"
            err = f"  ← {s['error_message']}" if s.get("error_message") else ""
            print(f"    {sic}  {s['name']:<40}  {sdur:>6}{err}")

    print(f"{'='*70}\n")

    # Auto-show failure logs
    if status.upper() not in ("SUCCESS", "BUILDING", "ABORTED"):
        print("❌ Build failed — fetching failure logs...\n")
        cmd_logs(job, build.number, tail=0, follow=False, interval=5, failed_stage=True)

    return 0

def cmd_stats(job: Any, build_number: Optional[int], history: int, as_json: bool) -> int:
    """
    Aggregate statistics for a build (and optionally across the last N builds).

    Always emits single-build stats for the target build. When ``history`` > 1,
    an additional ``history`` block is included that analyses the last N
    builds ending at (and including) the target build.

    Designed to be called by skills immediately after a build finishes so a
    short, human-friendly summary can be rendered alongside the watch output.
    """
    build = _get_build(job, build_number)
    result = build.result
    building = build.building
    status = "BUILDING" if building else (result or "UNKNOWN")

    # ------------------------------------------------------------------ raw
    raw: Dict[str, Any] = {}
    try:
        raw = build.api_json() or {}
    except Exception:
        raw = {}

    estimated_ms = int(raw.get("estimatedDuration") or 0)
    duration_ms = int(build.duration or raw.get("duration") or 0)
    dur_vs_est_pct = round(100.0 * duration_ms / estimated_ms, 1) if estimated_ms else None

    triggered_by: List[str] = []
    parameters: Dict[str, Any] = {}
    git_branch: str = ""
    git_sha: str = ""
    for action in raw.get("actions", []):
        causes = action.get("causes", [])
        if causes and not triggered_by:
            triggered_by = [c.get("shortDescription", "") for c in causes if c]
        params = action.get("parameters", [])
        if params and not parameters:
            parameters = {p.get("name", ""): p.get("value", "") for p in params}
        lbr = action.get("lastBuiltRevision") or {}
        if lbr and not git_sha:
            git_sha = lbr.get("SHA1", "") or ""
            branches = lbr.get("branch", []) or []
            if branches:
                git_branch = branches[0].get("name", "") or ""

    # -------------------------------------------------------------- stages
    stages_raw: List[Dict[str, Any]] = []
    try:
        wf = build.get_wf_api()
        stages_raw = list(wf.get("stages", []) or [])
    except Exception:
        stages_raw = []

    by_status: Dict[str, int] = {}
    executed: List[Dict[str, Any]] = []
    failed_stages: List[str] = []
    for s in stages_raw:
        st = (s.get("status") or s.get("state") or "UNKNOWN").upper()
        by_status[st] = by_status.get(st, 0) + 1
        dur = int(s.get("durationMillis") or 0)
        if st in ("FAILED", "FAILURE"):
            failed_stages.append(s.get("name", "?"))
        if dur > 0 and st not in ("NOT_EXECUTED", "SKIPPED"):
            executed.append({"name": s.get("name", "?"), "duration_ms": dur})

    slowest = max(executed, key=lambda x: x["duration_ms"]) if executed else None
    fastest = min(executed, key=lambda x: x["duration_ms"]) if executed else None
    total_stage_ms = sum(s["duration_ms"] for s in executed)
    avg_stage_ms = int(total_stage_ms / len(executed)) if executed else 0

    # ----------------------------------------------------------- artifacts
    try:
        artifact_count = len(list(build.get_artifacts()))
    except Exception:
        artifact_count = 0

    # ----------------------------------------------------------- test data
    test_summary: Optional[Dict[str, int]] = None
    try:
        report = build.get_test_report()
        if report is not None:
            test_summary = {
                "total": int(report.total_count),
                "passed": int(report.pass_count),
                "failed": int(report.fail_count),
                "skipped": int(report.skip_count),
            }
    except Exception:
        test_summary = None

    info: Dict[str, Any] = {
        "build": build.number,
        "status": status,
        "url": str(build.url),
        "duration_ms": duration_ms,
        "estimated_duration_ms": estimated_ms,
        "duration_vs_estimate_pct": dur_vs_est_pct,
        "stage_count": len(stages_raw),
        "stages_by_status": by_status,
        "slowest_stage": slowest,
        "fastest_stage": fastest,
        "avg_stage_duration_ms": avg_stage_ms,
        "total_stage_duration_ms": total_stage_ms,
        "failed_stages": failed_stages,
        "artifact_count": artifact_count,
        "test_summary": test_summary,
        "triggered_by": triggered_by,
        "parameter_count": len(parameters),
        "git_branch": git_branch,
        "git_sha": git_sha,
    }

    # ------------------------------------------------------------ history
    if history and history > 1:
        hist_builds: List[Dict[str, Any]] = []
        try:
            cursor = build
            for _ in range(history):
                if cursor is None:
                    break
                hist_builds.append({
                    "build": cursor.number,
                    "result": ("BUILDING" if cursor.building else (cursor.result or "UNKNOWN")),
                    "duration_ms": int(cursor.duration or 0),
                })
                try:
                    cursor = cursor.get_previous_build()
                except Exception:
                    cursor = None
        except Exception:
            pass

        durations = [b["duration_ms"] for b in hist_builds if b["duration_ms"] > 0]
        success = sum(1 for b in hist_builds if b["result"] == "SUCCESS")
        failure = sum(1 for b in hist_builds if b["result"] in ("FAILURE", "FAILED"))
        aborted = sum(1 for b in hist_builds if b["result"] == "ABORTED")
        other = len(hist_builds) - success - failure - aborted
        analysed = len(hist_builds)
        success_rate = round(100.0 * success / analysed, 1) if analysed else 0.0

        info["history"] = {
            "analysed": analysed,
            "success": success,
            "failure": failure,
            "aborted": aborted,
            "other": other,
            "success_rate_pct": success_rate,
            "duration_ms_min": min(durations) if durations else 0,
            "duration_ms_avg": int(sum(durations) / len(durations)) if durations else 0,
            "duration_ms_max": max(durations) if durations else 0,
            "builds": hist_builds,
        }

    # -------------------------------------------------------------- output
    if as_json:
        print(json.dumps(info, indent=2, default=str))
        return 0

    def _fmt_ms(ms: int) -> str:
        s = int(ms or 0) // 1000
        if s <= 0:
            return "-"
        return f"{s//60}m{s%60:02d}s" if s >= 60 else f"{s}s"

    icon = {
        "SUCCESS": "✅", "FAILURE": "❌", "FAILED": "❌",
        "ABORTED": "🚫", "BUILDING": "🔄", "UNKNOWN": "❓",
    }.get(status.upper(), "❓")

    print(f"\n{'='*70}")
    print(f"  BUILD STATS  #{info['build']}  {icon}  {status}")
    print(f"  URL            : {info['url']}")
    print(f"  Duration       : {_fmt_ms(duration_ms)}"
          + (f"   (estimated {_fmt_ms(estimated_ms)}, "
             f"{dur_vs_est_pct}% of estimate)" if estimated_ms else ""))
    print(f"  Stages         : {len(stages_raw)} total")
    if by_status:
        breakdown = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
        print(f"                   {breakdown}")
    if slowest:
        print(f"  Slowest stage  : {slowest['name']}  ({_fmt_ms(slowest['duration_ms'])})")
    if fastest:
        print(f"  Fastest stage  : {fastest['name']}  ({_fmt_ms(fastest['duration_ms'])})")
    if executed:
        print(f"  Avg stage      : {_fmt_ms(avg_stage_ms)}   "
              f"(total stage time {_fmt_ms(total_stage_ms)})")
    if failed_stages:
        print(f"  Failed stages  : {', '.join(failed_stages)}")
    print(f"  Artifacts      : {artifact_count}")
    if test_summary:
        print(f"  Tests          : {test_summary['total']} total  "
              f"(passed={test_summary['passed']}, "
              f"failed={test_summary['failed']}, "
              f"skipped={test_summary['skipped']})")
    else:
        print(f"  Tests          : (no report)")
    if triggered_by:
        print(f"  Triggered by   : {'; '.join(triggered_by)}")
    if git_branch or git_sha:
        sha_short = (git_sha or "")[:12]
        print(f"  Git            : {git_branch or '-'}  @  {sha_short or '-'}")
    print(f"  Parameters     : {len(parameters)}")

    hist = info.get("history")
    if hist:
        print(f"\n  HISTORY (last {hist['analysed']} builds)")
        print(f"    Success rate : {hist['success_rate_pct']}%  "
              f"(success={hist['success']}, failure={hist['failure']}, "
              f"aborted={hist['aborted']}, other={hist['other']})")
        print(f"    Duration     : min={_fmt_ms(hist['duration_ms_min'])}  "
              f"avg={_fmt_ms(hist['duration_ms_avg'])}  "
              f"max={_fmt_ms(hist['duration_ms_max'])}")
        print(f"    Roster       :")
        for b in hist["builds"]:
            bic = {"SUCCESS": "✅", "FAILURE": "❌", "FAILED": "❌",
                   "ABORTED": "🚫", "BUILDING": "🔄"}.get(b["result"], "❓")
            print(f"      {bic}  #{b['build']:<6}  {b['result']:<10}  "
                  f"{_fmt_ms(b['duration_ms'])}")
    print(f"{'='*70}\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jenkins_tools.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
        add_help=True,
    )

    # Global flags
    p.add_argument(
        "--user",
        default=None,
        metavar="USER",
        help=(
            "Jenkins username. Overrides JENKINS_USER env var. "
            "If neither flag nor env var is set the script exits with an error "
            "and prints the complete usage example."
        ),
    )
    p.add_argument(
        "--api-token",
        dest="api_token",
        default=None,
        metavar="TOKEN",
        help=(
            "Jenkins API token (from User → Configure → API Token). "
            "Overrides JENKINS_API_TOKEN env var."
        ),
    )
    p.add_argument(
        "--url",
        default=None,
        metavar="URL",
        help=f"Jenkins base URL. Overrides JENKINS_URL env var. (default: {_DEFAULT_JENKINS_URL})",
    )
    p.add_argument(
        "--job",
        default=None,
        metavar="JOB_PATH",
        help=(
            "Job path (slash-separated, no leading slash). "
            f"Overrides JENKINS_JOB env var. "
            f"Default: {_DEFAULT_JOB_PATH!r} "
            f"(derived from {_DEFAULT_PIPELINE_URL})"
        ),
    )
    p.add_argument(
        "--build",
        type=int,
        default=None,
        metavar="N",
        help="Build number. (default: lastBuild)",
    )
    p.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output in JSON format (for scripting / AI agent consumption).",
    )
    p.add_argument(
        "--OK_DELETE_MODIFY",
        dest="ok_delete_modify",
        action="store_true",
        help=(
            "SAFETY GATE — required for any command that MUTATES Jenkins state. "
            "Gated subcommands: trigger, abort, approve, enable, disable, and "
            "the auto-approve behaviour inside `watch`. Read-only commands "
            "(status, logs, stages, build-info, build-history, stats, "
            "watch without auto-approve, artifacts, queue, nodes, plugins, "
            "parameters, list-jobs, whoami, server-info, test-results, "
            "wait-for-start, setup, set-env) do NOT need this flag. "
            "Without --OK_DELETE_MODIFY, a gated command exits with code 2 "
            "before any Jenkins API call is made."
        ),
    )
    p.add_argument(
        "--help-ai",
        action="store_true",
        help="Print machine-readable JSON schema for AI agents and exit.",
    )

    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    # setup — interactive first-time credential wizard
    sp = sub.add_parser(
        "setup",
        help="Interactive setup: enter username + token, validate, save to shell profile.",
        description=(
            "Prompts for your Jenkins username and API token, validates them live against "
            "Jenkins, then saves them to ~/.zshrc (or ~/.bashrc) so every future terminal "
            "picks them up automatically. Re-running replaces any previously saved block.\n\n"
            "Create / rotate a token at:\n"
            f"  {_DEFAULT_JENKINS_URL}/user/<your-username>/configure  →  API Token → Add new Token"
        ),
    )
    sp.add_argument(
        "--shell-rc",
        default=None,
        metavar="PATH",
        help="Shell RC file path (default: ~/.zshrc or ~/.bashrc based on $SHELL).",
    )

    # set-env
    sp = sub.add_parser(
        "set-env",
        help="Persist JENKINS_USER and JENKINS_API_TOKEN to your shell RC file.",
        description=(
            "Appends 'export JENKINS_USER=...' and 'export JENKINS_API_TOKEN=...' to "
            "~/.zshrc (or ~/.bashrc on non-zsh shells). Re-running this command replaces "
            "any previous block it wrote."
        ),
    )
    sp.add_argument("--user", required=True, help="Jenkins username to persist.")
    sp.add_argument("--api-token", dest="api_token", required=True, help="Jenkins API token to persist.")
    sp.add_argument(
        "--shell-rc",
        default=None,
        metavar="PATH",
        help="Shell RC file path (default: ~/.zshrc or ~/.bashrc based on $SHELL).",
    )

    # whoami
    sub.add_parser("whoami", help="Print authenticated Jenkins user details.")

    # server-info
    sub.add_parser("server-info", help="Print Jenkins server version and load stats.")

    # list-jobs
    sp = sub.add_parser("list-jobs", help="List jobs/folders at a given path.")
    sp.add_argument("--path", default="", metavar="PATH", help="Folder path (default: root).")
    sp.add_argument("--depth", type=int, default=1, metavar="N", help="Max recursion depth (default: 1).")

    # status
    sub.add_parser("status", help="Show build status (default: lastBuild).")

    # build-history
    sp = sub.add_parser("build-history", help="List recent builds with result and timestamp.")
    sp.add_argument("--count", type=int, default=5, metavar="N", help="Number of builds (default: 5).")

    # logs
    sp = sub.add_parser("logs", help="Print console log for the selected build.")
    sp.add_argument(
        "--tail",
        type=int,
        default=400,
        metavar="N",
        help="Lines from end of log (default: 400; 0 = all).",
    )
    sp.add_argument(
        "--follow",
        action="store_true",
        help="Stream and follow log output until build completes.",
    )
    sp.add_argument(
        "--interval",
        type=int,
        default=5,
        metavar="SECS",
        help="Polling interval in seconds when --follow (default: 5).",
    )
    sp.add_argument(
        "--failed-stage",
        dest="failed_stage",
        action="store_true",
        help=(
            "Show only the logs for the failed stage plus surrounding error context. "
            "Ideal for quickly understanding why a build failed without scrolling the full log."
        ),
    )

    # stages
    sub.add_parser("stages", help="List pipeline stages and pending input actions.")

    # watch
    sp = sub.add_parser(
        "watch",
        help="Live-poll pipeline progress: print stage updates, detect approvals, show failure logs on finish.",
    )
    sp.add_argument(
        "--interval",
        type=int,
        default=15,
        metavar="SECS",
        help="Polling interval in seconds (default: 15).",
    )
    sp.add_argument(
        "--log-stats",
        dest="log_stats",
        action="store_true",
        help=(
            "Each poll, sample the console log and print a compact one-line "
            "delta of log activity: new line count, cumulative error / "
            "warning / Terraform / Docker / Helm / kubectl / AWS event "
            "counts, and the latest distinctive ERROR-like lines. "
            "Useful inside skills that need to show the user what is "
            "happening while the build runs, without a full --follow stream."
        ),
    )

    # wait-for-start
    sp = sub.add_parser(
        "wait-for-start",
        help="Block until the most recently queued build starts, then print the build number.",
    )
    sp.add_argument(
        "--queue-url",
        dest="queue_url",
        default=None,
        metavar="URL",
        help="Queue item URL returned by trigger (optional — defaults to detecting any new build).",
    )
    sp.add_argument(
        "--timeout",
        type=int,
        default=300,
        metavar="SECS",
        help="Max seconds to wait (default: 300).",
    )

    # build-info
    sp = sub.add_parser(
        "build-info",
        help="Detailed info on a build: trigger, parameters, Git SHA, stage breakdown, failure logs.",
    )
    # (uses global --build flag)

    # parameters
    sub.add_parser("parameters", help="Show parameter definitions for the job.")

    # trigger
    sp = sub.add_parser("trigger", help="Trigger a new build.")
    sp.add_argument(
        "--param",
        dest="params",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Build parameter (repeatable). Example: --param ENVIRONMENT=dev",
    )
    sp.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the build to complete and print result.",
    )
    sp.add_argument(
        "--timeout",
        type=int,
        default=600,
        metavar="SECS",
        help="Max seconds to wait when --wait (default: 600).",
    )

    # abort
    sub.add_parser("abort", help="Abort the currently running build.")

    # approve
    sp = sub.add_parser("approve", help="Submit (or abort) a pending pipeline input step.")
    sp.add_argument(
        "--input-id",
        dest="input_id",
        default=None,
        metavar="ID",
        help="Explicit input step id (skip auto-detect from message text).",
    )
    sp.add_argument(
        "--abort-input",
        action="store_true",
        help="Abort the input step instead of proceeding.",
    )

    # queue
    sub.add_parser("queue", help="List items currently in the Jenkins build queue.")

    # artifacts
    sp = sub.add_parser("artifacts", help="List (and optionally download) build artifacts.")
    sp.add_argument(
        "--download-dir",
        default=None,
        metavar="DIR",
        help="Local directory to save artifacts (creates if needed).",
    )

    # enable / disable
    sub.add_parser("enable", help="Enable the job (clear disabled state).")
    sub.add_parser("disable", help="Disable the job (prevent new builds).")

    # get-job-config
    sp = sub.add_parser(
        "get-job-config",
        help="Print the config.xml for the job at --target-job (or --job).",
    )
    sp.add_argument(
        "--target-job",
        dest="target_job",
        default=None,
        metavar="PATH",
        help="Slash-separated job path to fetch (overrides --job for this command).",
    )

    # create-job
    sp = sub.add_parser(
        "create-job",
        help=(
            "Create a Jenkins job under --folder from --template (rendered with --var "
            "KEY=VALUE substitutions for {{KEY}} placeholders). MUTATING — requires "
            "--OK_DELETE_MODIFY."
        ),
    )
    sp.add_argument("--folder", required=True, metavar="PATH",
                    help="Folder to create the job under (e.g. exlerate/exlerate-solutions/MIDAS).")
    sp.add_argument("--name", required=True, metavar="NAME",
                    help="New job's leaf name (e.g. midas-ai-gateway-tf-deploy-ORD1).")
    sp.add_argument("--template", required=True, metavar="PATH",
                    help="Path to the config.xml template file with {{KEY}} placeholders.")
    sp.add_argument("--var", dest="vars_kv", action="append", default=[], metavar="KEY=VALUE",
                    help="Template substitution (repeatable). Substitutes {{KEY}} with VALUE.")

    # update-job
    sp = sub.add_parser(
        "update-job",
        help=(
            "Overwrite the config.xml of an existing job at --target-job from --template "
            "(with --var substitutions). MUTATING — requires --OK_DELETE_MODIFY."
        ),
    )
    sp.add_argument("--target-job", dest="target_job", required=True, metavar="PATH",
                    help="Existing job's slash-separated path to overwrite.")
    sp.add_argument("--template", required=True, metavar="PATH",
                    help="Path to the config.xml template file with {{KEY}} placeholders.")
    sp.add_argument("--var", dest="vars_kv", action="append", default=[], metavar="KEY=VALUE",
                    help="Template substitution (repeatable). Substitutes {{KEY}} with VALUE.")

    # nodes
    sub.add_parser("nodes", help="List Jenkins agents/nodes with status.")

    # plugins
    sp = sub.add_parser("plugins", help="List installed plugins with version and update status.")
    sp.add_argument(
        "--updates-only",
        action="store_true",
        help="Show only plugins that have an available update.",
    )

    # test-results
    sub.add_parser("test-results", help="Show test result summary for the selected build.")

    # stats
    sp = sub.add_parser(
        "stats",
        help=(
            "Aggregate statistics for a build (duration, stage breakdown, "
            "slowest/fastest stage, artifacts, tests, history)."
        ),
        description=(
            "Emit a compact summary of a finished (or in-progress) build:\n"
            "  - Duration vs Jenkins' estimate\n"
            "  - Stage count and status breakdown\n"
            "  - Slowest and fastest executed stage\n"
            "  - Average / total stage time\n"
            "  - Failed stage names (if any)\n"
            "  - Artifact count\n"
            "  - Test summary (if a report exists)\n"
            "  - Trigger cause, Git branch/SHA, parameter count\n"
            "\nUse --history N (>1) to also aggregate the last N builds: "
            "success rate, min/avg/max duration, and a pass/fail roster.\n"
            "\nDesigned for skills to render after a watch ends."
        ),
    )
    sp.add_argument(
        "--history",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Also analyse the last N builds ending at the target build. "
            "N=1 (default) reports only the single target build."
        ),
    )

    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = _build_parser()

    # Intercept --help-ai before normal parsing so it does not require auth
    if "--help-ai" in sys.argv:
        print(json.dumps(_AI_HELP_SCHEMA, indent=2))
        return 0

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # setup and set-env do not need a live Jenkins connection at entry
    if args.command == "setup":
        url = getattr(args, "url", None) or os.environ.get("JENKINS_URL") or _DEFAULT_JENKINS_URL
        return cmd_setup(url, getattr(args, "shell_rc", None))

    if args.command == "set-env":
        return cmd_set_env(args)

    # ----- SAFETY GATE (runs BEFORE any Jenkins connection) -----
    # Any command that would mutate Jenkins state is refused here unless the
    # caller passed --OK_DELETE_MODIFY. Doing this check before `_connect`
    # means the script never touches Jenkins at all (not even authentication)
    # for a blocked mutation — no logs, no wasted credentials, no race.
    _GATED_DISPATCH: Dict[str, Tuple[str, str]] = {
        "trigger": ("trigger", "queues a new Jenkins build that runs the MIDAS deploy pipeline"),
        "abort":   ("abort",   "terminates the currently running Jenkins build"),
        "enable":  ("enable",  "enables the Jenkins job (clears its disabled state)"),
        "disable": ("disable", "disables the Jenkins job (blocks future builds)"),
        "create-job": ("create-job", "creates a new Jenkins job from a config.xml template"),
        "update-job": ("update-job", "overwrites the config.xml of an existing Jenkins job"),
    }
    if args.command in _GATED_DISPATCH:
        op, effect = _GATED_DISPATCH[args.command]
        _require_ok_delete_modify(
            getattr(args, "ok_delete_modify", False),
            operation=op,
            effect=effect,
        )
    if args.command == "approve":
        _abort_input = bool(getattr(args, "abort_input", False))
        _require_ok_delete_modify(
            getattr(args, "ok_delete_modify", False),
            operation=("approve --abort-input" if _abort_input else "approve"),
            effect=(
                "aborts the pending pipeline approval gate (fails the build at that stage)"
                if _abort_input
                else "proceeds the pending pipeline approval gate (lets the build continue)"
            ),
        )
    # `watch` is NOT gated here — it is read-only by default. The embedded
    # auto-approve branch inside cmd_watch honours `ok_delete_modify` itself.

    # All other commands require authentication
    client, job_path = _connect(args)
    as_json: bool = args.as_json
    build_number: Optional[int] = getattr(args, "build", None)

    if args.command == "whoami":
        return cmd_whoami(client, as_json)

    if args.command == "server-info":
        return cmd_server_info(client, as_json)

    if args.command == "list-jobs":
        return cmd_list_jobs(client, args.path, args.depth, as_json)

    if args.command == "get-job-config":
        target = getattr(args, "target_job", None) or job_path
        return cmd_get_job_config(client, target, as_json)

    if args.command == "create-job":
        try:
            xml = _render_template(args.template, args.vars_kv)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1
        return cmd_create_job(client, args.folder, args.name, xml, as_json)

    if args.command == "update-job":
        try:
            xml = _render_template(args.template, args.vars_kv)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1
        return cmd_update_job(client, args.target_job, xml, as_json)

    if args.command == "queue":
        return cmd_queue(client, as_json)

    if args.command == "nodes":
        return cmd_nodes(client, as_json)

    if args.command == "plugins":
        return cmd_plugins(client, args.updates_only, as_json)

    # Commands that operate on the default (or --job) pipeline job
    job = _get_job(client, job_path)

    if args.command == "status":
        return cmd_status(job, build_number, as_json)

    if args.command == "build-history":
        return cmd_build_history(job, args.count, as_json)

    if args.command == "logs":
        return cmd_logs(
            job, build_number,
            args.tail, args.follow, args.interval,
            getattr(args, "failed_stage", False),
        )

    if args.command == "stages":
        return cmd_stages(job, build_number, as_json)

    if args.command == "watch":
        # `watch` itself is read-only; only the embedded auto-approve branch
        # is a mutation. We pass `ok_delete_modify` into cmd_watch so it can
        # decide per-poll whether to actually call `.proceed()` on a pending
        # input. No need to block `watch` at dispatch.
        return cmd_watch(
            job, build_number, args.interval, as_json,
            log_stats=getattr(args, "log_stats", False),
            ok_delete_modify=getattr(args, "ok_delete_modify", False),
        )

    if args.command == "wait-for-start":
        return cmd_wait_for_start(job, getattr(args, "queue_url", None), args.timeout, as_json)

    if args.command == "build-info":
        return cmd_build_info(job, build_number, as_json)

    if args.command == "parameters":
        return cmd_parameters(job, as_json)

    if args.command == "trigger":
        return cmd_trigger(job, args.params, args.wait, args.timeout, as_json)

    if args.command == "abort":
        return cmd_abort(job, build_number, as_json)

    if args.command == "approve":
        return cmd_approve(job, build_number, args.input_id, args.abort_input, as_json)

    if args.command == "artifacts":
        return cmd_artifacts(job, build_number, args.download_dir, as_json)

    if args.command == "enable":
        return cmd_enable(job, as_json)

    if args.command == "disable":
        return cmd_disable(job, as_json)

    if args.command == "test-results":
        return cmd_test_results(job, build_number, as_json)

    if args.command == "stats":
        return cmd_stats(job, build_number, args.history, as_json)

    parser.error(f"Unknown command: {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
