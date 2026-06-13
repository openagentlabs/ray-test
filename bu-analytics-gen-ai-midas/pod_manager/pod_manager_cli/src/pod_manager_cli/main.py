"""Typer CLI — gRPC-only operator console for router.svc."""

from __future__ import annotations

import asyncio
import json
import re
import sys

import grpc
import httpx
import typer
from pod_manager_client import PodManagerClient, PodManagerClientError

from pod_manager_cli.deploy_config import DeployTarget, EndpointProfile, load_profile_file

app = typer.Typer(help="pod_manager routing control plane operator CLI (gRPC :8804).")
config_app = typer.Typer(help="Runtime and service configuration via gRPC.")
app.add_typer(config_app, name="config")


def _profile() -> EndpointProfile:
    return EndpointProfile.from_environment()


def _host() -> str:
    return _profile().pod_manager_host


def _port() -> int:
    return _profile().pod_manager_port


def _envoy_url() -> str:
    return _profile().envoy_url


def _run(coro):  # noqa: ANN001, ANN201
    return asyncio.run(coro)


_NODE_NAME_RE = re.compile(
    r"BACKEND_POOL_NODE_NAME</strong>:\s*([^<]+)",
)


def _parse_routed_node(body: str) -> str | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        for key in ("backend_pool_node", "pod_id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    match = _NODE_NAME_RE.search(body)
    return match.group(1).strip() if match else None


def _exit_from_client_error(exc: PodManagerClientError) -> None:
    typer.echo(f"error: {exc}", err=True)
    if exc.code == grpc.StatusCode.UNAVAILABLE:
        raise typer.Exit(code=2) from exc
    raise typer.Exit(code=1) from exc


@app.command("pool")
def pool_status(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    """List pod pool status (GetPoolStatus)."""

    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            status = await client.get_pool_status()
            typer.echo(f"free={status.free_count} claimed={status.claimed_count}")
            for pod in status.pods:
                pool = getattr(pod, "pool", "") or "-"
                line = (
                    f"{pod.pod_id}\t{pool}\t{pod.state}\t"
                    f"{pod.assigned_sub or '-'}\t{pod.pod_dns}"
                )
                typer.echo(line)
            if verbose:
                typer.echo(f"(pods={len(status.pods)})")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@app.command("claim")
def claim(sub: str = typer.Option(..., "--sub", help="Cognito subject or test sub")) -> None:
    """Acquire or resume a backend lease (idempotent AcquireLease)."""

    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            result = await client.acquire_lease(sub)
            action = "resumed existing lease" if result.already_leased else "acquired new lease"
            typer.echo(action)
            typer.echo(f"pod_id={result.pod_id}")
            typer.echo(f"pod_dns={result.pod_dns}")
            typer.echo(f"assignment_epoch={result.assignment_epoch}")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@app.command("lease")
def lease_status(sub: str = typer.Option(..., "--sub", help="Cognito subject or test sub")) -> None:
    """Show current backend lease for a subject (read-only GetLease)."""

    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            try:
                result = await client.get_lease(sub)
            except PodManagerClientError as exc:
                if exc.code == grpc.StatusCode.NOT_FOUND:
                    typer.echo("no lease")
                    return
                raise
            typer.echo(f"pod_id={result.pod_id}")
            typer.echo(f"pod_dns={result.pod_dns}")
            typer.echo(f"assignment_epoch={result.assignment_epoch}")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@app.command("release")
def release(sub: str = typer.Option(..., "--sub")) -> None:
    """Release assignment for a subject."""

    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            await client.release_lease(sub)
            typer.echo("released")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@app.command("heartbeat")
def heartbeat(
    sub: str = typer.Option(..., "--sub"),
    epoch: int = typer.Option(..., "--epoch"),
) -> None:
    """Refresh session idle timer (Heartbeat RPC)."""

    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            new_epoch = await client.heartbeat(sub, epoch)
            typer.echo(f"assignment_epoch={new_epoch}")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@app.command("route")
def route(
    sub: str = typer.Option(..., "--sub"),
    envoy_url: str = typer.Option(None, "--envoy-url", help="Override ENVOY_URL"),
) -> None:
    """HTTP smoke test through Envoy (optional; uses x-test-sub)."""

    url = (envoy_url or _envoy_url()).rstrip("/") + "/"
    headers = {"x-test-sub": sub}
    try:
        resp = httpx.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        typer.echo(f"HTTP error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    node = _parse_routed_node(resp.text)
    if node:
        typer.echo(f"routed_node={node}")
    else:
        typer.echo(resp.text[:500])


@app.command("e2e")
def e2e(
    sub: str = typer.Option("alice@example.com", "--sub"),
    repeats: int = typer.Option(3, "--repeats"),
    envoy_url: str = typer.Option(None, "--envoy-url"),
) -> None:
    """claim → route N times → release; assert sticky backend identity."""

    base = (envoy_url or _envoy_url()).rstrip("/")
    route_url = f"{base}/api/v1/me"
    seen: set[str] = set()

    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            claimed = await client.acquire_lease(sub)
            typer.echo(f"claimed pod_id={claimed.pod_id}")
            for _ in range(repeats):
                resp = httpx.get(route_url, headers={"x-test-sub": sub}, timeout=10.0)
                resp.raise_for_status()
                node = _parse_routed_node(resp.text)
                if not node:
                    typer.echo("could not parse routed node from /api/v1/me", err=True)
                    raise typer.Exit(code=1)
                seen.add(node)
            await client.release_lease(sub)

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)
    except httpx.HTTPError as exc:
        typer.echo(f"HTTP error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if len(seen) != 1:
        typer.echo(f"not sticky: saw pods {seen}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"sticky OK: {seen.pop()}")


@config_app.command("profile")
def config_profile(
    target: str = typer.Option(
        None,
        "--target",
        "-t",
        help="Deploy target profile to show (local or aws); defaults to POD_MANAGER_DEPLOY_TARGET",
    ),
    export_shell: bool = typer.Option(
        False,
        "--export",
        help="Print export statements suitable for eval/source",
    ),
) -> None:
    """Show active deploy target and endpoint profile (local vs aws)."""
    deploy_target = DeployTarget(target) if target else _profile().deploy_target
    file_values = load_profile_file(deploy_target)
    merged = EndpointProfile.from_environment()
    if target:
        merged = EndpointProfile(
            deploy_target=deploy_target,
            envoy_url=file_values.get("ENVOY_URL", merged.envoy_url),
            pod_manager_host=file_values.get("POD_MANAGER_HOST", merged.pod_manager_host),
            pod_manager_port=int(
                file_values.get("POD_MANAGER_PORT", str(merged.pod_manager_port)),
            ),
            database_url=file_values.get("DATABASE_URL"),
        )

    lines = {
        "POD_MANAGER_DEPLOY_TARGET": merged.deploy_target.value,
        "ENVOY_URL": merged.envoy_url,
        "POD_MANAGER_HOST": merged.pod_manager_host,
        "POD_MANAGER_PORT": str(merged.pod_manager_port),
        "DATABASE_URL": merged.database_url or "",
    }
    if export_shell:
        for key, value in lines.items():
            if value:
                typer.echo(f'export {key}="{value}"')
        return

    typer.echo(f"deploy_target={merged.deploy_target.value}")
    for key, value in lines.items():
        if key != "POD_MANAGER_DEPLOY_TARGET":
            typer.echo(f"{key}={value or '-'}")


@config_app.command("env")
def config_env() -> None:
    """Show runtime environment as the manager process sees it (redacted)."""

    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            entries = await client.get_runtime_environment()
            for key in sorted(entries):
                typer.echo(f"{key}={entries[key]}")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@config_app.command("list")
def config_list() -> None:
    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            for entry in await client.list_service_config():
                typer.echo(f"{entry.config_key}\t{entry.value}\t{entry.updated_at}")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@config_app.command("get")
def config_get(key: str = typer.Argument(...)) -> None:
    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            entry = await client.get_service_config(key)
            typer.echo(entry.value)

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(...),
    value: str = typer.Argument(...),
    description: str = typer.Option("", "--description", "-d"),
) -> None:
    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            entry = await client.put_service_config(key, value, description=description)
            typer.echo(f"set {entry.config_key} at {entry.updated_at}")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


@config_app.command("unset")
def config_unset(key: str = typer.Argument(...)) -> None:
    async def _go() -> None:
        async with PodManagerClient(host=_host(), port=_port()) as client:
            await client.delete_service_config(key)
            typer.echo("deleted")

    try:
        _run(_go())
    except PodManagerClientError as exc:
        _exit_from_client_error(exc)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
