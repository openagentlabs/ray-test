"""IoC composition root — wires adapters from singleton ``app_config``."""

from __future__ import annotations

from dataclasses import dataclass

from iam_service.auth.token_service import AuthTokenService
from iam_service.core.app_config_store import app_config
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result, Success
from iam_service.database.dynamo_admin import DynamoDatabaseAdmin
from iam_service.database.models.records import (
    LoginTypeRecord,
    SessionRecord,
    SkillListRecord,
    SkillRecord,
    UserTypeRecord,
)
from iam_service.database.repositories.auth_permission_repository import (
    ServiceFunctionRegistryRepository,
    UserPermissionRepository,
)
from iam_service.database.repositories.auth_session_repository import AuthSessionRepository
from iam_service.database.repositories.deployment_admin_repository import DeploymentAdminRepository
from iam_service.database.repositories.invite_repository import InviteRepository
from iam_service.database.repositories.item_repository import ItemRepository
from iam_service.database.repositories.login_repository import LoginRepository
from iam_service.database.repositories.rbac_repository import RbacRepository
from iam_service.database.repositories.user_repository import UserRepository
from iam_service.database.repositories.user_skill_repository import UserSkillRepository
from iam_service.dynamodb.context import DynamoContext
from iam_service.plugins.idp.factory import build_idp_driver
from iam_service.plugins.idp.interface import IdentityProviderDriver
from iam_service.plugins.vault.factory import build_vault_driver
from iam_service.plugins.vault.interface import VaultDriver
from iam_service.services.auth_application import AuthApplication
from iam_service.services.iam_application import IamServiceApplication
from iam_service.services.rbac_service import RbacService


@dataclass(slots=True)
class Repositories:
    """Concrete DynamoDB adapters — infrastructure layer."""

    users: UserRepository
    user_types: ItemRepository[UserTypeRecord]
    login_types: ItemRepository[LoginTypeRecord]
    skill_lists: ItemRepository[SkillListRecord]
    skills: ItemRepository[SkillRecord]
    user_skills: UserSkillRepository
    logins: LoginRepository
    sessions: ItemRepository[SessionRecord]
    invites: InviteRepository
    deployment_admins: DeploymentAdminRepository
    rbac: RbacRepository
    user_permissions: UserPermissionRepository
    service_registry: ServiceFunctionRegistryRepository
    auth_sessions: AuthSessionRepository
    admin: DynamoDatabaseAdmin


@dataclass(slots=True)
class ServiceContainer:
    """Application services and plugin drivers built from ``app_config``."""

    dynamo: DynamoContext
    repos: Repositories
    rbac_service: RbacService
    iam_app: IamServiceApplication
    auth_app: AuthApplication
    vault_driver: VaultDriver
    idp_driver: IdentityProviderDriver
    token_service: AuthTokenService

    @staticmethod
    def build(*, dynamo: DynamoContext) -> Result[ServiceContainer, AppError]:
        """Construct all services; reads config via ``app_config()`` singleton."""
        cfg = app_config()
        tables = cfg.dynamodb.tables

        repos = Repositories(
            users=UserRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.users,
            ),
            user_types=ItemRepository[UserTypeRecord](
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.user_types,
                model=UserTypeRecord,
            ),
            login_types=ItemRepository[LoginTypeRecord](
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.login_types,
                model=LoginTypeRecord,
            ),
            skill_lists=ItemRepository[SkillListRecord](
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.skill_lists,
                model=SkillListRecord,
            ),
            skills=ItemRepository[SkillRecord](
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.skills,
                model=SkillRecord,
            ),
            user_skills=UserSkillRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.user_skills,
            ),
            logins=LoginRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.logins,
            ),
            sessions=ItemRepository[SessionRecord](
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.sessions,
                model=SessionRecord,
            ),
            invites=InviteRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.invites,
            ),
            deployment_admins=DeploymentAdminRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.deployment_admin,
            ),
            rbac=RbacRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                roles_table=tables.roles,
                permissions_table=tables.permissions,
                role_permissions_table=tables.role_permissions,
                user_role_assignments_table=tables.user_role_assignments,
                service_permissions_table=tables.service_permissions,
            ),
            user_permissions=UserPermissionRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.user_permissions,
            ),
            service_registry=ServiceFunctionRegistryRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.service_function_registry,
            ),
            auth_sessions=AuthSessionRepository(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                table_name=tables.auth_sessions,
            ),
            admin=DynamoDatabaseAdmin(
                session=dynamo.session,
                region=dynamo.region,
                endpoint_url=dynamo.endpoint_url,
                tables=tables,
            ),
        )

        rbac_service = RbacService(repo=repos.rbac)

        vault_result = build_vault_driver(cfg.vault)
        if isinstance(vault_result, Failure):
            return vault_result
        idp_result = build_idp_driver(cfg.idp)
        if isinstance(idp_result, Failure):
            return idp_result

        vault_driver = vault_result.unwrap()
        idp_driver = idp_result.unwrap()
        token_service = AuthTokenService(
            vault=vault_driver,
            master_key_id=cfg.vault.master_key_id,
        )

        iam_app = IamServiceApplication(
            app=cfg.app,
            users=repos.users,
            user_types=repos.user_types,
            login_types=repos.login_types,
            skill_lists=repos.skill_lists,
            skills=repos.skills,
            user_skills=repos.user_skills,
            logins=repos.logins,
            sessions=repos.sessions,
            invites=repos.invites,
            deployment_admins=repos.deployment_admins,
            rbac=rbac_service,
            admin=repos.admin,
        )

        auth_app = AuthApplication(
            idp=idp_driver,
            token_service=token_service,
            users=repos.users,
            user_permissions=repos.user_permissions,
            service_registry=repos.service_registry,
            auth_sessions=repos.auth_sessions,
        )

        return Success(
            ServiceContainer(
                dynamo=dynamo,
                repos=repos,
                rbac_service=rbac_service,
                iam_app=iam_app,
                auth_app=auth_app,
                vault_driver=vault_driver,
                idp_driver=idp_driver,
                token_service=token_service,
            ),
        )
