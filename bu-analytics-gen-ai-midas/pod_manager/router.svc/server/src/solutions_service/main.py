"""Process entry: load config, configure logging, run managed gRPC server."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

from dotenv import load_dotenv

from solutions_service.auth.jwt_validator import CognitoConfig as JwtCognitoConfig
from solutions_service.auth.jwt_validator import JwtValidator
from solutions_service.core.app_config import DEFAULT_APPLICATION_LOG_LEVEL, AppConfig
from solutions_service.core.logging_config import configure_logging
from solutions_service.core.results import Failure
from solutions_service.database.repositories.assignment_events_repository import (
    AssignmentEventsRepository,
)
from solutions_service.database.repositories.backend_pool_repository import BackendPoolRepository
from solutions_service.database.repositories.service_config_repository import (
    ServiceConfigRepository,
)
from solutions_service.database.repositories.solution_document_repository import (
    SolutionDocumentRepository,
)
from solutions_service.database.repositories.user_assignment_repository import (
    UserAssignmentRepository,
)
from solutions_service.database.schema import RoutingTableNames, create_schema, validate_schema_contract
from solutions_service.drivers.eks.kubernetes import KubernetesEksClusterDriver
from solutions_service.drivers.envoy.grpc_management import GrpcEnvoyDriver
from solutions_service.drivers.envoy.noop import NoopEnvoyDriver
from solutions_service.drivers.store.postgres import PostgresAssignmentStoreDriver
from solutions_service.ext_authz.assignment_cache import AssignmentRouteCache
from solutions_service.postgres.context import PostgresContext
from solutions_service.ext_authz.check_handler import ExtAuthzCheckHandler
from solutions_service.grpc_transport.server import GrpcListenServer
from solutions_service.handlers.config.config_handler import ConfigRpcHandler
from solutions_service.handlers.pool.pool_handler import PoolRpcHandler
from solutions_service.reconciliation.assignment_reaper import AssignmentReaper
from solutions_service.reconciliation.backend_pool_reconciler import BackendPoolReconciler
from solutions_service.util.exit_codes import AppExitCode
from solutions_service.util.parameters import log_parameters
from solutions_service.util.process_exit import exit_on_failure
from solutions_service.util.validation import validate, validate_database

logger = logging.getLogger(__name__)


def _default_config_path() -> Path:
    return Path(os.environ.get("SOLUTIONS_APP_CONFIG_PATH", "app_config.toml"))


def _align_aws_region_env() -> None:
    region = os.environ.get("AWS_DEFAULT_REGION", "").strip()
    if region and not os.environ.get("AWS_REGION", "").strip():
        os.environ["AWS_REGION"] = region


def _load_dotenv_beside_config(config_path: Path) -> None:
    config_dir = config_path.resolve().parent
    load_dotenv(config_dir / ".env", override=False)
    load_dotenv(config_dir / ".env.local", override=True)
    _align_aws_region_env()


async def _async_main() -> None:
    configure_logging(
        level_name=os.environ.get(
            "SOLUTIONS_LOG_LEVEL",
            os.environ.get("LOG_LEVEL", DEFAULT_APPLICATION_LOG_LEVEL),
        ),
    )
    config_path = _default_config_path()
    _load_dotenv_beside_config(config_path)

    loaded = AppConfig.load(config_path)
    if isinstance(loaded, Failure):
        exit_on_failure(
            code=AppExitCode.CONFIG_LOAD_FAILED,
            err=loaded.failure(),
            logger=logger,
        )
    app_config = loaded.unwrap()
    configure_logging(level_name=app_config.app.log_level)

    log_parameters(app_config=app_config, config_path=config_path)

    validated = await validate(app_config)
    if isinstance(validated, Failure):
        exit_on_failure(
            code=AppExitCode.STARTUP_VALIDATION_FAILED,
            err=validated.failure(),
            logger=logger,
        )

    pg_loaded = await PostgresContext.from_app_config(app_config)
    if isinstance(pg_loaded, Failure):
        exit_on_failure(
            code=AppExitCode.DATABASE_VALIDATION_FAILED,
            err=pg_loaded.failure(),
            logger=logger,
        )
    pg = pg_loaded.unwrap()

    db_valid = await validate_database(pg)
    if isinstance(db_valid, Failure):
        exit_on_failure(
            code=AppExitCode.DATABASE_VALIDATION_FAILED,
            err=db_valid.failure(),
            logger=logger,
        )

    table_names = RoutingTableNames(
        schema=app_config.postgres.schema_name,
        backend_pool=app_config.physical_table("backend_pool"),
        login_pod_pool=app_config.physical_table("login_pod_pool"),
        user_assignments=app_config.physical_table("user_assignments"),
        assignment_events=app_config.physical_table("assignment_events"),
        solution_documents=app_config.physical_table("solution_documents"),
        service_config=app_config.physical_table("service_config"),
    )
    schema_ready = await create_schema(pg.pool, table_names)
    if isinstance(schema_ready, Failure):
        exit_on_failure(
            code=AppExitCode.DATABASE_VALIDATION_FAILED,
            err=schema_ready.failure(),
            logger=logger,
        )
    schema_valid = await validate_schema_contract(pg.pool, table_names)
    if isinstance(schema_valid, Failure):
        exit_on_failure(
            code=AppExitCode.DATABASE_VALIDATION_FAILED,
            err=schema_valid.failure(),
            logger=logger,
        )

    backend_pool_repo = BackendPoolRepository(
        pool=pg.pool,
        table_name=table_names.backend_pool,
    )
    login_pod_pool_repo = BackendPoolRepository(
        pool=pg.pool,
        table_name=table_names.login_pod_pool,
    )
    user_assignments_repo = UserAssignmentRepository(
        pool=pg.pool,
        table_name=table_names.user_assignments,
    )
    assignment_events_repo = AssignmentEventsRepository(
        pool=pg.pool,
        table_name=table_names.assignment_events,
    )
    service_config_repo = ServiceConfigRepository(
        pool=pg.pool,
        table_name=table_names.service_config,
    )
    _ = SolutionDocumentRepository(
        pool=pg.pool,
        table_name=table_names.solution_documents,
    )

    assignment_store = PostgresAssignmentStoreDriver(
        pool=pg.pool,
        backend_pool_table=table_names.backend_pool,
        login_pod_pool_table=table_names.login_pod_pool,
        user_assignments_table=table_names.user_assignments,
        backend_pool_repository=backend_pool_repo,
        login_pod_pool_repository=login_pod_pool_repo,
        user_assignment_repository=user_assignments_repo,
    )
    route_cache = AssignmentRouteCache()

    jwt_validator: JwtValidator | None = None
    if app_config.cognito.enabled and app_config.cognito.issuer and app_config.cognito.audience:
        jwt_validator = JwtValidator(
            cognito=JwtCognitoConfig(
                issuer=app_config.cognito.issuer,
                audience=app_config.cognito.audience,
                jwks_uri=app_config.cognito.jwks_uri,
            ),
        )

    pool_handler = PoolRpcHandler(
        assignment_store=assignment_store,
        assignment_events_repository=assignment_events_repo,
        route_cache=route_cache,
    )
    config_handler = ConfigRpcHandler(
        app_config=app_config,
        service_config_repository=service_config_repo,
    )
    ext_authz_handler = ExtAuthzCheckHandler(
        app_config=app_config,
        assignment_store=assignment_store,
        route_cache=route_cache,
        jwt_validator=jwt_validator,
    )
    if app_config.envoy_management.enabled:
        envoy_driver = GrpcEnvoyDriver(
            admin_host=app_config.envoy_management.admin_host,
            admin_port=app_config.envoy_management.admin_port,
        )
    else:
        envoy_driver = NoopEnvoyDriver()
    validated_envoy = await envoy_driver.validate_config()
    if isinstance(validated_envoy, Failure):
        logger.warning(
            "envoy_validate_skipped: %s",
            validated_envoy.failure().message,
        )

    server = GrpcListenServer(
        app_config=app_config,
        pool_handler=pool_handler,
        config_handler=config_handler,
        ext_authz_check_handler=ext_authz_handler,
    )
    started = await server.open()
    if isinstance(started, Failure):
        exit_on_failure(
            code=AppExitCode.GRPC_SERVER_FAILED,
            err=started.failure(),
            logger=logger,
        )

    reconcile_stop = asyncio.Event()
    reconcile_task: asyncio.Task[None] | None = None
    reaper_task: asyncio.Task[None] | None = None
    cluster_driver: KubernetesEksClusterDriver | None = None

    if app_config.reconciliation.enabled and app_config.kubernetes.enabled:
        cluster_driver = KubernetesEksClusterDriver(kubernetes_config=app_config.kubernetes)
        reconciler = BackendPoolReconciler(
            app_config=app_config,
            cluster_driver=cluster_driver,
            backend_pool_repository=backend_pool_repo,
        )
        reconcile_task = asyncio.create_task(
            reconciler.run_until_stopped(reconcile_stop),
            name="backend_pool_reconciler",
        )
        logger.info("reconciliation_task_started")

    if app_config.reaper.enabled:
        reaper = AssignmentReaper(
            reaper_config=app_config.reaper,
            assignment_store=assignment_store,
            user_assignment_repository=user_assignments_repo,
            assignment_events_repository=assignment_events_repo,
            route_cache=route_cache,
        )
        reaper_task = asyncio.create_task(
            reaper.run_until_stopped(reconcile_stop),
            name="assignment_reaper",
        )
        logger.info("reaper_task_started")

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    use_signals = False
    try:
        loop.add_signal_handler(signal.SIGINT, stop.set)
        loop.add_signal_handler(signal.SIGTERM, stop.set)
        use_signals = True
    except NotImplementedError:
        pass

    async def _shutdown_background() -> None:
        reconcile_stop.set()
        for task in (reconcile_task, reaper_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if cluster_driver is not None:
            await cluster_driver.close()
        if app_config.envoy_management.enabled:
            drained = await envoy_driver.drain_listeners()
            if isinstance(drained, Failure):
                logger.warning("envoy_drain_failed: %s", drained.failure().message)
        await pg.close()

    try:
        if not use_signals:
            try:
                await server.join()
            finally:
                await _shutdown_background()
                closed = await server.close()
                if isinstance(closed, Failure):
                    _log_shutdown_error(closed.failure())
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
    finally:
        await _shutdown_background()
        closed = await server.close()
        if isinstance(closed, Failure):
            _log_shutdown_error(closed.failure())


def _log_shutdown_error(err: object) -> None:
    from solutions_service.core.errors import AppError

    if isinstance(err, AppError):
        logger.error("gRPC server shutdown issue: %s (%s)", err.message, err.code)
        if err.detail:
            logger.error("%s", err.detail)


def run() -> None:
    """Console script: load ``app_config.toml`` and run the gRPC server."""
    try:
        asyncio.run(_async_main())
    except asyncio.CancelledError:
        raise SystemExit(int(AppExitCode.INTERRUPTED)) from None
