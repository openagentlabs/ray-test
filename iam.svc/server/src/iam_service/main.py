"""Process entry: load config, configure logging, run managed gRPC server."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from dotenv import load_dotenv

from iam_service.core.app_config_store import app_config, init_app_config
from iam_service.core.container import ServiceContainer
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.observability_config import configure_observability, shutdown_observability
from iam_service.core.results import Failure, Success
from iam_service.dynamodb.context import DynamoContext
from iam_service.grpc_transport.server import GrpcListenServer
from iam_service.http_transport.auth_server import HttpAuthServer
from iam_service.util.exit_codes import AppExitCode
from iam_service.util.parameters import log_parameters
from iam_service.util.process_exit import exit_on_failure
from iam_service.util.validation import validate, validate_database

logger = logging.getLogger(__name__)


def _load_dotenv_beside_config(config_path: Path) -> None:
    import os

    config_dir = config_path.resolve().parent
    repo_root = config_dir.parent.parent
    load_dotenv(config_dir / ".env", override=False)
    load_dotenv(config_dir / ".env.local", override=True)
    shared_env_local = repo_root / "general.ai.agent.svc" / "server" / ".env.local"
    if shared_env_local.is_file():
        load_dotenv(shared_env_local, override=False)
    region = os.environ.get("AWS_DEFAULT_REGION", "").strip()
    if region and not os.environ.get("AWS_REGION", "").strip():
        os.environ["AWS_REGION"] = region


async def _async_main() -> None:
    from iam_service.core.app_config_store import app_config_path, default_config_path

    config_path = default_config_path()
    _load_dotenv_beside_config(config_path)

    loaded = init_app_config(config_path)
    if isinstance(loaded, Failure):
        exit_on_failure(
            code=AppExitCode.CONFIG_LOAD_FAILED,
            err=loaded.failure(),
            logger=logger,
        )

    cfg = app_config()

    try:
        await configure_observability(config=cfg.observability)
    except RuntimeError as exc:
        exit_on_failure(
            code=AppExitCode.CONFIG_LOAD_FAILED,
            err=AppError(
                code=ErrorCodes.INTERNAL,
                message="Observability initialization failed.",
                detail=str(exc),
            ),
            logger=logger,
        )

    log_parameters(app_config=cfg, config_path=app_config_path() or config_path)

    validated = await validate(cfg)
    if isinstance(validated, Failure):
        exit_on_failure(
            code=AppExitCode.STARTUP_VALIDATION_FAILED,
            err=validated.failure(),
            logger=logger,
        )

    dynamo = DynamoContext.from_app_config()
    db_valid = await validate_database(dynamo)
    if isinstance(db_valid, Failure):
        exit_on_failure(
            code=AppExitCode.DATABASE_VALIDATION_FAILED,
            err=db_valid.failure(),
            logger=logger,
        )

    built = ServiceContainer.build(dynamo=dynamo)
    if isinstance(built, Failure):
        exit_on_failure(
            code=AppExitCode.CONFIG_LOAD_FAILED,
            err=built.failure(),
            logger=logger,
        )
    container = built.unwrap()

    key_ready = await container.token_service.ensure_master_key_exists()
    if isinstance(key_ready, Failure):
        exit_on_failure(
            code=AppExitCode.STARTUP_VALIDATION_FAILED,
            err=key_ready.failure(),
            logger=logger,
        )

    bootstrap = await container.iam_app.check_if_new_deployment_can_create_admin()
    if isinstance(bootstrap, Failure):
        exit_on_failure(
            code=AppExitCode.DEPLOYMENT_ADMIN_BOOTSTRAP_FAILED,
            err=bootstrap.failure(),
            logger=logger,
        )

    server = GrpcListenServer(
        app_config=cfg,
        api_service_config=cfg.api_service,
        iam_app=container.iam_app,
    )
    started = await server.open()
    if isinstance(started, Failure):
        exit_on_failure(
            code=AppExitCode.GRPC_SERVER_FAILED,
            err=started.failure(),
            logger=logger,
        )

    http_auth_server: HttpAuthServer | None = None
    if cfg.http_auth.enabled:
        http_auth_server = HttpAuthServer(
            config=cfg.http_auth,
            auth_app=container.auth_app,
        )
        http_started = await http_auth_server.open()
        if isinstance(http_started, Failure):
            await server.close()
            exit_on_failure(
                code=AppExitCode.GRPC_SERVER_FAILED,
                err=http_started.failure(),
                logger=logger,
            )

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    use_signals = False
    try:
        loop.add_signal_handler(signal.SIGINT, stop.set)
        loop.add_signal_handler(signal.SIGTERM, stop.set)
        use_signals = True
    except NotImplementedError:
        pass

    if not use_signals:
        try:
            await server.join()
        finally:
            try:
                closed = await server.close()
            except asyncio.CancelledError:
                closed = Success(None)
            if isinstance(closed, Failure):
                err = closed.failure()
                logger.error(
                    "gRPC server shutdown issue: %s (%s)",
                    err.message,
                    err.code,
                )
                if err.detail:
                    logger.error("%s", err.detail)
            if http_auth_server is not None:
                await http_auth_server.close()
            await shutdown_observability()
        return

    join_task = asyncio.create_task(server.join())
    sig_task = asyncio.create_task(stop.wait())
    _, pending = await asyncio.wait(
        {join_task, sig_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        closed = await server.close()
    except asyncio.CancelledError:
        closed = Success(None)
    if isinstance(closed, Failure):
        err = closed.failure()
        logger.error("gRPC server shutdown issue: %s (%s)", err.message, err.code)
        if err.detail:
            logger.error("%s", err.detail)

    if http_auth_server is not None:
        await http_auth_server.close()

    await shutdown_observability()


def run() -> None:
    """Console script: load ``app_config.toml`` and run the gRPC server."""
    try:
        asyncio.run(_async_main())
    except asyncio.CancelledError:
        raise SystemExit(int(AppExitCode.INTERRUPTED)) from None
