#!/usr/bin/env python3
"""Interactive local configuration generator for MIDAS frontend/backend."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ParamSpec:
    """Spec for one environment variable prompt."""

    key: str
    default_local: str
    description: str


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "runb-local" / "output"


FILE_SPECS: Dict[str, List[ParamSpec]] = {
    "frontend/.env": [
        ParamSpec("VITE_BASE_URL", "http://localhost:8000", "Backend API base URL"),
        ParamSpec("VITE_COGNITO_DOMAIN", "https://<your-cognito-domain>", "Cognito Hosted UI domain"),
        ParamSpec("VITE_COGNITO_CLIENT_ID", "<your-cognito-app-client-id>", "Cognito SPA client id"),
        ParamSpec("VITE_COGNITO_REDIRECT_URI", "http://localhost:5173/auth/callback", "Frontend callback URL"),
        ParamSpec("VITE_COGNITO_LOGOUT_REDIRECT_URI", "http://localhost:5173/", "Frontend logout redirect URL"),
        ParamSpec("VITE_COGNITO_SCOPES", "openid email profile", "OAuth scopes"),
        ParamSpec("VITE_DEV_BYPASS_AUTH", "false", "Use dev bypass login page"),
    ],
    "backend/.env": [
        ParamSpec("APP_ENV", "development", "Runtime environment"),
        ParamSpec("SESSION_REQUIRE_REDIS", "false", "Require Redis-backed sessions"),
        ParamSpec("SESSION_REDIS_URL", "redis://localhost:6379/0", "Redis session store URL"),
        ParamSpec("REDIS_URL", "redis://localhost:6379/0", "Fallback Redis URL"),
        ParamSpec("COGNITO_DOMAIN", "https://<pool>.auth.<region>.amazoncognito.com", "Cognito Hosted UI domain"),
        ParamSpec("COGNITO_REGION", "us-east-1", "Cognito region"),
        ParamSpec("COGNITO_USER_POOL_ID", "us-east-1_XXXXXXXXX", "Cognito user pool id"),
        ParamSpec("COGNITO_CLIENT_ID", "<app-client-id>", "Cognito app client id"),
        ParamSpec("COGNITO_CLIENT_SECRET", "", "Optional for confidential app client"),
        ParamSpec("COGNITO_REDIRECT_URIS", "http://localhost:5173/auth/callback", "Allowed callback URL(s)"),
        ParamSpec("COGNITO_LOGOUT_REDIRECT_URI", "http://localhost:5173/", "Post-logout redirect URL"),
        ParamSpec("COGNITO_SCOPES", "openid email profile", "OAuth scopes"),
        ParamSpec("COGNITO_IDP_NAME", "MicrosoftEntraID", "Optional fixed IdP"),
        ParamSpec("COGNITO_COOKIE_SECURE", "false", "Must be false for HTTP localhost"),
        ParamSpec("COGNITO_LOGIN_COOKIE_SECRET", "", "Optional in local; required in production"),
        ParamSpec("COGNITO_LOGIN_COOKIE_TTL", "600", "cg_login cookie TTL in seconds"),
        ParamSpec("COGNITO_REFRESH_COOKIE_TTL_DAYS", "5", "Refresh cookie TTL in days"),
        ParamSpec("CORS_ALLOW_ORIGINS", "http://localhost:5173", "Allowed frontend origins"),
    ],
}


@dataclass(frozen=True)
class ValidationCheck:
    """One local-readiness validation rule."""

    key: str
    expected: str
    reason: str


VALIDATION_RULES: Dict[str, List[ValidationCheck]] = {
    "frontend/.env": [
        ValidationCheck("VITE_BASE_URL", "http://localhost:8000", "Frontend points to local backend"),
        ValidationCheck("VITE_COGNITO_REDIRECT_URI", "http://localhost:5173/auth/callback", "Local callback URL"),
        ValidationCheck("VITE_COGNITO_LOGOUT_REDIRECT_URI", "http://localhost:5173/", "Local logout redirect URL"),
    ],
    "backend/.env": [
        ValidationCheck("APP_ENV", "development", "Local-friendly runtime mode"),
        ValidationCheck("COGNITO_REDIRECT_URIS", "http://localhost:5173/auth/callback", "Backend callback allowlist"),
        ValidationCheck("COGNITO_LOGOUT_REDIRECT_URI", "http://localhost:5173/", "Backend logout URL"),
        ValidationCheck("COGNITO_COOKIE_SECURE", "false", "HTTP localhost requires non-secure cookie"),
        ValidationCheck("CORS_ALLOW_ORIGINS", "http://localhost:5173", "Allow local frontend origin"),
    ],
}


def parse_env_file(path: Path) -> Dict[str, str]:
    """Parse simple KEY=VALUE lines from an env-style file."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_current_values() -> Dict[str, Dict[str, str]]:
    """Load current env values from likely source files."""
    sources = {
        "frontend/.env": [
            ROOT / "frontend" / ".env",
            ROOT / "frontend" / ".env.example",
        ],
        "backend/.env": [
            ROOT / "backend" / ".env",
            ROOT / "backend" / ".env.backup",
        ],
    }
    merged: Dict[str, Dict[str, str]] = {}
    for target, paths in sources.items():
        target_values: Dict[str, str] = {}
        # Lower priority first, higher priority later (existing .env overrides example/backup)
        for path in reversed(paths):
            target_values.update(parse_env_file(path))
        merged[target] = target_values
    return merged


def prompt_value(spec: ParamSpec, current_value: Optional[str]) -> str:
    """Prompt user for one value.

    Prompt controls:
    - Enter: use local default
    - '=': keep current value (if present)
    - any other text: use custom value
    """
    print(f"\n- {spec.key}")
    print(f"  Description : {spec.description}")
    print(f"  Local default: {spec.default_local!r}")
    if current_value is not None:
        print(f"  Current value: {current_value!r}")
        raw = input("  Enter=default, '='=current, or type custom: ").strip()
    else:
        print("  Current value: <not set>")
        raw = input("  Enter=default, or type custom: ").strip()

    if raw == "":
        return spec.default_local
    if raw == "=" and current_value is not None:
        return current_value
    return raw


def write_env_file(path: Path, specs: List[ParamSpec], values: Dict[str, str]) -> None:
    """Write env file in the same key order as specs."""
    lines = [f"# Generated by runb-local/generate_local_config.py for {path.name}"]
    for spec in specs:
        lines.append(f"{spec.key}={values.get(spec.key, '')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_markdown(path: Path, selected: Dict[str, Dict[str, str]]) -> None:
    """Write markdown summary of selected values grouped by target file."""
    lines: List[str] = [
        "# Local Config Review",
        "",
        "Generated by `runb-local/generate_local_config.py`.",
        "",
        "## Selected Values",
        "",
    ]
    for target_file, values in selected.items():
        lines.append(f"### `{target_file}`")
        lines.append("")
        for key, value in values.items():
            lines.append(f"- `{key}` = `{value}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def evaluate_rule(actual_values: Dict[str, str], rule: ValidationCheck) -> Tuple[bool, str]:
    """Evaluate one rule and return pass/fail with a message."""
    actual = actual_values.get(rule.key, "<missing>")
    passed = actual == rule.expected
    if passed:
        return True, f"`{rule.key}` is `{actual}`"
    return False, f"`{rule.key}` is `{actual}` (expected `{rule.expected}`)"


def run_validation(target: str, values: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Run local readiness checks for one target env file."""
    lines: List[str] = []
    ok = True
    for rule in VALIDATION_RULES.get(target, []):
        passed, detail = evaluate_rule(values, rule)
        icon = "PASS" if passed else "FAIL"
        lines.append(f"- [{icon}] {detail} - {rule.reason}")
        ok = ok and passed

    if target == "backend/.env":
        session_require_redis = values.get("SESSION_REQUIRE_REDIS", "").lower()
        session_redis_url = values.get("SESSION_REDIS_URL", "")
        redis_url = values.get("REDIS_URL", "")
        if session_require_redis == "false":
            lines.append("- [PASS] Redis is optional (SESSION_REQUIRE_REDIS=false)")
        elif session_require_redis == "true":
            if session_redis_url.startswith("redis://localhost") or redis_url.startswith("redis://localhost"):
                lines.append("- [PASS] Redis required and local Redis URL is configured")
            else:
                lines.append("- [FAIL] Redis required but local Redis URL not found")
                ok = False
        else:
            lines.append("- [FAIL] SESSION_REQUIRE_REDIS must be either true or false")
            ok = False

    return ok, lines


def run_step_2_validation(
    generated_frontend: Path,
    generated_backend: Path,
) -> None:
    """Step 2: Validate generated and current env files for local readiness."""
    print("\n" + "=" * 72)
    print("STEP 2 - LOCAL READINESS VALIDATION")
    print("=" * 72)

    generated_values = {
        "frontend/.env": parse_env_file(generated_frontend),
        "backend/.env": parse_env_file(generated_backend),
    }
    current_values = {
        "frontend/.env": parse_env_file(ROOT / "frontend" / ".env"),
        "backend/.env": parse_env_file(ROOT / "backend" / ".env"),
    }

    overall_ok = True

    print("\nGenerated output files:")
    for target in ("frontend/.env", "backend/.env"):
        passed, lines = run_validation(target, generated_values[target])
        print(f"\n{target} (generated) -> {'PASS' if passed else 'FAIL'}")
        for line in lines:
            print(line)
        overall_ok = overall_ok and passed

    print("\nCurrent project files:")
    for target in ("frontend/.env", "backend/.env"):
        if not current_values[target]:
            print(f"\n{target} (current) -> SKIP (file missing or empty)")
            overall_ok = False
            continue
        passed, lines = run_validation(target, current_values[target])
        print(f"\n{target} (current) -> {'PASS' if passed else 'FAIL'}")
        for line in lines:
            print(line)
        overall_ok = overall_ok and passed

    print("\nValidation summary:")
    print(f"- Overall status: {'PASS' if overall_ok else 'FAIL'}")
    print("- Tip: copy generated files into frontend/.env and backend/.env, then rerun this script.")


def main() -> None:
    """Run interactive local config collection and emit output files."""
    print("MIDAS local configuration generator")
    print("Press Enter to accept the local default for each parameter.")
    print("If shown, type '=' to keep the current repo value.")

    current_values = load_current_values()
    selected_by_file: Dict[str, Dict[str, str]] = {}

    for target_file, specs in FILE_SPECS.items():
        print("\n" + "=" * 72)
        print(f"Target file: {target_file}")
        print("=" * 72)
        selected_values: Dict[str, str] = {}
        existing = current_values.get(target_file, {})
        for spec in specs:
            selected_values[spec.key] = prompt_value(spec, existing.get(spec.key))
        selected_by_file[target_file] = selected_values

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frontend_out = OUTPUT_DIR / "frontend.env"
    backend_out = OUTPUT_DIR / "backend.env"
    review_out = OUTPUT_DIR / "config-review.md"

    write_env_file(frontend_out, FILE_SPECS["frontend/.env"], selected_by_file["frontend/.env"])
    write_env_file(backend_out, FILE_SPECS["backend/.env"], selected_by_file["backend/.env"])
    write_review_markdown(review_out, selected_by_file)

    print("\nDone. Generated:")
    print(f"- {frontend_out}")
    print(f"- {backend_out}")
    print(f"- {review_out}")
    print("\nNext steps:")
    print("1) Review generated values in runb-local/output")
    print("2) Copy to live files if correct:")
    print("   cp runb-local/output/frontend.env frontend/.env")
    print("   cp runb-local/output/backend.env backend/.env")
    run_step_2_validation(frontend_out, backend_out)


if __name__ == "__main__":
    main()

