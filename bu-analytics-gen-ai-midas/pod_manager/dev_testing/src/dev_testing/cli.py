"""Typer CLI for dev_testing modules."""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import Callable

import typer
from returns.result import Failure, Result, Success

from dev_testing.config import DeployTarget, EndpointProfile
from dev_testing.modules import (
    cleanup,
    grpc_lease,
    grpc_pool,
    health,
    http_login,
    http_routing,
    integration,
    postgres,
)
from dev_testing.results_ext import Reporter

app = typer.Typer(help="Unified local and AWS tests for pod_manager.")


class TestModule(StrEnum):
    HEALTH = "health"
    GRPC_POOL = "grpc_pool"
    GRPC_LEASE = "grpc_lease"
    HTTP_LOGIN = "http_login"
    HTTP_ROUTING = "http_routing"
    POSTGRES = "postgres"
    INTEGRATION = "integration"
    ALL = "all"


_MODULE_RUNNERS: dict[TestModule, Callable] = {
    TestModule.HEALTH: health.run,
    TestModule.GRPC_POOL: grpc_pool.run,
    TestModule.GRPC_LEASE: grpc_lease.run,
    TestModule.HTTP_LOGIN: http_login.run,
    TestModule.HTTP_ROUTING: http_routing.run,
    TestModule.POSTGRES: postgres.run,
    TestModule.INTEGRATION: integration.run,
}

_ALL_ORDER = [
    TestModule.HEALTH,
    TestModule.POSTGRES,
    TestModule.GRPC_POOL,
    TestModule.HTTP_LOGIN,
    TestModule.HTTP_ROUTING,
    TestModule.GRPC_LEASE,
    TestModule.INTEGRATION,
]

_PREFLIGHT = cleanup.run


def _report() -> tuple[Reporter, dict[str, int]]:
    state = {"passed": 0, "failed": 0}

    def _inner(ok: bool, message: str) -> None:
        if ok:
            state["passed"] += 1
            typer.echo(f"  OK: {message}")
        else:
            state["failed"] += 1
            typer.echo(f"  FAIL: {message}", err=True)

    return _inner, state


async def _run_module(
    module: TestModule,
    profile: EndpointProfile,
) -> Result[None, str]:
    runner = _MODULE_RUNNERS[module]
    reporter, _state = _report()
    typer.echo(f"==> {module.value} (target={profile.deploy_target.value})")
    return await runner(profile, reporter)


async def _run_all(profile: EndpointProfile) -> int:
    exit_code = 0
    reporter, _state = _report()
    typer.echo(f"==> cleanup (target={profile.deploy_target.value})")
    preflight = await _PREFLIGHT(profile, reporter)
    if isinstance(preflight, Failure):
        typer.echo(preflight.failure(), err=True)
        exit_code = 1
    typer.echo("")
    for module in _ALL_ORDER:
        result = await _run_module(module, profile)
        if isinstance(result, Failure):
            typer.echo(result.failure(), err=True)
            exit_code = 1
        typer.echo("")
    return exit_code


@app.command()
def main(
    module: TestModule = typer.Argument(..., help="Test module to run (or all)."),
    target: DeployTarget = typer.Option(
        DeployTarget.LOCAL,
        "--target",
        "-t",
        help="Deploy target profile.",
    ),
    test_sub: str = typer.Option(None, "--sub", help="Test subject for lease/routing."),
) -> None:
    """Run a dev_testing module against local or AWS endpoints."""
    profile = EndpointProfile.from_environment(target=target)
    if test_sub:
        profile = profile.model_copy(update={"test_sub": test_sub})
    elif module == TestModule.ALL:
        profile = profile.model_copy(
            update={"test_sub": f"dev-test-{int(time.time())}@example.com"},
        )
    try:
        profile.validate_ready()
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if module == TestModule.ALL:
        code = asyncio.run(_run_all(profile))
        raise typer.Exit(code=code)

    result = asyncio.run(_run_module(module, profile))
    if isinstance(result, Failure):
        typer.echo(result.failure(), err=True)
        raise typer.Exit(code=1)
    typer.echo("Module passed.")


if __name__ == "__main__":
    app()
