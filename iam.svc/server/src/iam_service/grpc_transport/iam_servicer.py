"""gRPC ``IamService`` servicer — transport only; delegates to ``IamServiceApplication``."""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import TypeVar
from uuid import UUID, uuid4

from grpc import aio

from iam.v1 import iam_pb2, iam_pb2_grpc
from iam_service.core.errors import AppError
from iam_service.core.results import Failure, Result
from iam_service.grpc_transport.metadata import invocation_metadata_as_map
from iam_service.grpc_transport.status_map import status_code_for_app_error
from iam_service.observability.correlation import (
    CORRELATION_METADATA_KEY,
    new_correlation_token,
    reset_correlation_token,
)
from iam_service.services.iam_application import IamServiceApplication

logger = logging.getLogger(__name__)

TResp = TypeVar("TResp")


class IamGrpcServicer(iam_pb2_grpc.IamServiceServicer):
    """Maps protobuf requests/responses and ``Result`` to gRPC status codes."""

    __slots__ = ("_app", "_handler_id")

    def __init__(self, *, app: IamServiceApplication, handler_id: UUID | None = None) -> None:
        self._app = app
        self._handler_id = handler_id if handler_id is not None else uuid4()

    async def _dispatch(
        self,
        context: aio.ServicerContext,
        work: Awaitable[Result[TResp, AppError]],
        *,
        rpc_name: str,
    ) -> TResp:
        meta = invocation_metadata_as_map(context)
        cid_in = meta.get(CORRELATION_METADATA_KEY)
        token, resolved = new_correlation_token(cid_in)
        logger.debug(
            "iam_servicer_invoke rpc=%s handler_id=%s cid=%s", rpc_name, self._handler_id, resolved
        )
        try:
            outcome = await work
            if isinstance(outcome, Failure):
                err = outcome.failure()
                code = status_code_for_app_error(err)
                logger.warning(
                    "iam_servicer_failure rpc=%s handler_id=%s code=%s app_code=%s",
                    rpc_name,
                    self._handler_id,
                    code,
                    err.code,
                )
                await context.abort(code, err.message)
                msg = "context.abort should not return"
                raise AssertionError(msg)
            return outcome.unwrap()
        finally:
            reset_correlation_token(token)

    async def Ping(
        self, request: iam_pb2.PingRequest, context: aio.ServicerContext
    ) -> iam_pb2.PingReply:
        return await self._dispatch(context, self._app.ping(request), rpc_name="Ping")

    async def Echo(
        self, request: iam_pb2.EchoRequest, context: aio.ServicerContext
    ) -> iam_pb2.EchoReply:
        return await self._dispatch(context, self._app.echo(request), rpc_name="Echo")

    async def RecordCount(
        self,
        request: iam_pb2.RecordCountRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.RecordCountReply:
        return await self._dispatch(
            context, self._app.record_count(request), rpc_name="RecordCount"
        )

    async def EnsureInitialUser(
        self,
        request: iam_pb2.EnsureInitialUserRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.EnsureInitialUserReply:
        return await self._dispatch(
            context, self._app.ensure_initial_user(request), rpc_name="EnsureInitialUser"
        )

    async def ResetDatabase(
        self,
        request: iam_pb2.ResetDatabaseRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ResetDatabaseReply:
        return await self._dispatch(
            context, self._app.reset_database(request), rpc_name="ResetDatabase"
        )

    async def GetUserByEmail(
        self,
        request: iam_pb2.GetUserByEmailRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserLong:
        return await self._dispatch(
            context, self._app.get_user_by_email(request), rpc_name="GetUserByEmail"
        )

    async def GetUserData(
        self,
        request: iam_pb2.GetUserDataRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.GetUserDataReply:
        return await self._dispatch(
            context, self._app.get_user_data(request), rpc_name="GetUserData"
        )

    async def CreateUser(
        self, request: iam_pb2.CreateUserRequest, context: aio.ServicerContext
    ) -> iam_pb2.User:
        return await self._dispatch(context, self._app.create_user(request), rpc_name="CreateUser")

    async def GetUserShort(
        self,
        request: iam_pb2.GetUserRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserShort:
        return await self._dispatch(
            context, self._app.get_user_short(request), rpc_name="GetUserShort"
        )

    async def GetUserLong(
        self, request: iam_pb2.GetUserRequest, context: aio.ServicerContext
    ) -> iam_pb2.UserLong:
        return await self._dispatch(
            context, self._app.get_user_long(request), rpc_name="GetUserLong"
        )

    async def UpdateUser(
        self, request: iam_pb2.UpdateUserRequest, context: aio.ServicerContext
    ) -> iam_pb2.User:
        return await self._dispatch(context, self._app.update_user(request), rpc_name="UpdateUser")

    async def SoftDeleteUser(
        self,
        request: iam_pb2.SoftDeleteUserRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.User:
        return await self._dispatch(
            context, self._app.soft_delete_user(request), rpc_name="SoftDeleteUser"
        )

    async def ListUsersByAccount(
        self,
        request: iam_pb2.ListUsersByAccountRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListUsersByAccountReply:
        return await self._dispatch(
            context,
            self._app.list_users_by_account(request),
            rpc_name="ListUsersByAccount",
        )

    async def GetUserTypeStats(
        self,
        request: iam_pb2.GetUserTypeStatsRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.GetUserTypeStatsReply:
        return await self._dispatch(
            context,
            self._app.get_user_type_stats(request),
            rpc_name="GetUserTypeStats",
        )

    async def CreateUserType(
        self,
        request: iam_pb2.CreateUserTypeRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserType:
        return await self._dispatch(
            context, self._app.create_user_type(request), rpc_name="CreateUserType"
        )

    async def GetUserType(
        self, request: iam_pb2.GetUserTypeRequest, context: aio.ServicerContext
    ) -> iam_pb2.UserType:
        return await self._dispatch(
            context, self._app.get_user_type(request), rpc_name="GetUserType"
        )

    async def UpdateUserType(
        self,
        request: iam_pb2.UpdateUserTypeRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserType:
        return await self._dispatch(
            context, self._app.update_user_type(request), rpc_name="UpdateUserType"
        )

    async def SoftDeleteUserType(
        self,
        request: iam_pb2.SoftDeleteUserTypeRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserType:
        return await self._dispatch(
            context,
            self._app.soft_delete_user_type(request),
            rpc_name="SoftDeleteUserType",
        )

    async def ListUserTypes(
        self,
        request: iam_pb2.ListUserTypesRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListUserTypesReply:
        return await self._dispatch(
            context, self._app.list_user_types(request), rpc_name="ListUserTypes"
        )

    async def CreateLoginType(
        self,
        request: iam_pb2.CreateLoginTypeRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.LoginType:
        return await self._dispatch(
            context, self._app.create_login_type(request), rpc_name="CreateLoginType"
        )

    async def GetLoginType(
        self,
        request: iam_pb2.GetLoginTypeRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.LoginType:
        return await self._dispatch(
            context, self._app.get_login_type(request), rpc_name="GetLoginType"
        )

    async def UpdateLoginType(
        self,
        request: iam_pb2.UpdateLoginTypeRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.LoginType:
        return await self._dispatch(
            context, self._app.update_login_type(request), rpc_name="UpdateLoginType"
        )

    async def SoftDeleteLoginType(
        self,
        request: iam_pb2.SoftDeleteLoginTypeRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.LoginType:
        return await self._dispatch(
            context,
            self._app.soft_delete_login_type(request),
            rpc_name="SoftDeleteLoginType",
        )

    async def ListLoginTypes(
        self,
        request: iam_pb2.ListLoginTypesRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListLoginTypesReply:
        return await self._dispatch(
            context, self._app.list_login_types(request), rpc_name="ListLoginTypes"
        )

    async def CreateSkillList(
        self,
        request: iam_pb2.CreateSkillListRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.SkillList:
        return await self._dispatch(
            context, self._app.create_skill_list(request), rpc_name="CreateSkillList"
        )

    async def GetSkillList(
        self,
        request: iam_pb2.GetSkillListRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.SkillList:
        return await self._dispatch(
            context, self._app.get_skill_list(request), rpc_name="GetSkillList"
        )

    async def UpdateSkillList(
        self,
        request: iam_pb2.UpdateSkillListRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.SkillList:
        return await self._dispatch(
            context, self._app.update_skill_list(request), rpc_name="UpdateSkillList"
        )

    async def SoftDeleteSkillList(
        self,
        request: iam_pb2.SoftDeleteSkillListRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.SkillList:
        return await self._dispatch(
            context,
            self._app.soft_delete_skill_list(request),
            rpc_name="SoftDeleteSkillList",
        )

    async def ListSkills(
        self,
        request: iam_pb2.ListSkillsRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListSkillsReply:
        return await self._dispatch(context, self._app.list_skills(request), rpc_name="ListSkills")

    async def CreateSkill(
        self, request: iam_pb2.CreateSkillRequest, context: aio.ServicerContext
    ) -> iam_pb2.Skill:
        return await self._dispatch(
            context, self._app.create_skill(request), rpc_name="CreateSkill"
        )

    async def GetSkill(
        self, request: iam_pb2.GetSkillRequest, context: aio.ServicerContext
    ) -> iam_pb2.Skill:
        return await self._dispatch(context, self._app.get_skill(request), rpc_name="GetSkill")

    async def UpdateSkill(
        self, request: iam_pb2.UpdateSkillRequest, context: aio.ServicerContext
    ) -> iam_pb2.Skill:
        return await self._dispatch(
            context, self._app.update_skill(request), rpc_name="UpdateSkill"
        )

    async def SoftDeleteSkill(
        self, request: iam_pb2.SoftDeleteSkillRequest, context: aio.ServicerContext
    ) -> iam_pb2.Skill:
        return await self._dispatch(
            context, self._app.soft_delete_skill(request), rpc_name="SoftDeleteSkill"
        )

    async def ListUserSkills(
        self,
        request: iam_pb2.ListUserSkillsRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListUserSkillsReply:
        return await self._dispatch(
            context, self._app.list_user_skills(request), rpc_name="ListUserSkills"
        )

    async def CreateUserSkill(
        self,
        request: iam_pb2.CreateUserSkillRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserSkill:
        return await self._dispatch(
            context, self._app.create_user_skill(request), rpc_name="CreateUserSkill"
        )

    async def SoftDeleteUserSkill(
        self,
        request: iam_pb2.SoftDeleteUserSkillRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserSkill:
        return await self._dispatch(
            context, self._app.soft_delete_user_skill(request), rpc_name="SoftDeleteUserSkill"
        )

    async def ReplaceUserSkills(
        self,
        request: iam_pb2.ReplaceUserSkillsRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ReplaceUserSkillsReply:
        return await self._dispatch(
            context, self._app.replace_user_skills(request), rpc_name="ReplaceUserSkills"
        )

    async def CreateLogin(
        self, request: iam_pb2.CreateLoginRequest, context: aio.ServicerContext
    ) -> iam_pb2.Login:
        return await self._dispatch(
            context, self._app.create_login(request), rpc_name="CreateLogin"
        )

    async def GetLogin(
        self, request: iam_pb2.GetLoginRequest, context: aio.ServicerContext
    ) -> iam_pb2.Login:
        return await self._dispatch(context, self._app.get_login(request), rpc_name="GetLogin")

    async def UpdateLogin(
        self, request: iam_pb2.UpdateLoginRequest, context: aio.ServicerContext
    ) -> iam_pb2.Login:
        return await self._dispatch(
            context, self._app.update_login(request), rpc_name="UpdateLogin"
        )

    async def SoftDeleteLogin(
        self,
        request: iam_pb2.SoftDeleteLoginRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.Login:
        return await self._dispatch(
            context, self._app.soft_delete_login(request), rpc_name="SoftDeleteLogin"
        )

    async def ListLoginsByUserId(
        self,
        request: iam_pb2.ListLoginsByUserIdRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListLoginsByUserIdReply:
        return await self._dispatch(
            context,
            self._app.list_logins_by_user_id(request),
            rpc_name="ListLoginsByUserId",
        )

    async def GenerateInvite(
        self,
        request: iam_pb2.GenerateInviteRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.Invite:
        return await self._dispatch(
            context, self._app.generate_invite(request), rpc_name="GenerateInvite"
        )

    async def ListInvites(
        self,
        request: iam_pb2.ListInvitesRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListInvitesReply:
        return await self._dispatch(
            context, self._app.list_invites(request), rpc_name="ListInvites"
        )

    async def SoftDeleteInvite(
        self,
        request: iam_pb2.SoftDeleteInviteRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.Invite:
        return await self._dispatch(
            context, self._app.soft_delete_invite(request), rpc_name="SoftDeleteInvite"
        )

    async def RedeemInvite(
        self, request: iam_pb2.RedeemInviteRequest, context: aio.ServicerContext
    ) -> iam_pb2.Invite:
        return await self._dispatch(
            context, self._app.redeem_invite(request), rpc_name="RedeemInvite"
        )

    async def SignUpUser(
        self,
        request: iam_pb2.SignUpUserRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.SignUpUserReply:
        return await self._dispatch(context, self._app.sign_up_user(request), rpc_name="SignUpUser")

    async def SignInCheck(
        self,
        request: iam_pb2.SignInCheckRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.SignInCheckReply:
        return await self._dispatch(
            context, self._app.sign_in_check(request), rpc_name="SignInCheck"
        )

    async def SignIn(
        self, request: iam_pb2.SignInRequest, context: aio.ServicerContext
    ) -> iam_pb2.Session:
        return await self._dispatch(context, self._app.sign_in(request), rpc_name="SignIn")

    async def SignOut(
        self,
        request: iam_pb2.SignOutRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.SignOutReply:
        return await self._dispatch(context, self._app.sign_out(request), rpc_name="SignOut")

    async def ListRoles(
        self,
        request: iam_pb2.ListRolesRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListRolesReply:
        return await self._dispatch(context, self._app.list_roles(request), rpc_name="ListRoles")

    async def CreateRole(
        self,
        request: iam_pb2.CreateRoleRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.Role:
        return await self._dispatch(context, self._app.create_role(request), rpc_name="CreateRole")

    async def ListPermissions(
        self,
        request: iam_pb2.ListPermissionsRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListPermissionsReply:
        return await self._dispatch(
            context, self._app.list_permissions(request), rpc_name="ListPermissions"
        )

    async def CreatePermission(
        self,
        request: iam_pb2.CreatePermissionRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.Permission:
        return await self._dispatch(
            context, self._app.create_permission(request), rpc_name="CreatePermission"
        )

    async def AttachPermissionToRole(
        self,
        request: iam_pb2.AttachPermissionToRoleRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.RolePermission:
        return await self._dispatch(
            context,
            self._app.attach_permission_to_role(request),
            rpc_name="AttachPermissionToRole",
        )

    async def AssignRoleToUser(
        self,
        request: iam_pb2.AssignRoleToUserRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.UserRoleAssignment:
        return await self._dispatch(
            context, self._app.assign_role_to_user(request), rpc_name="AssignRoleToUser"
        )

    async def RevokeRoleFromUser(
        self,
        request: iam_pb2.RevokeRoleFromUserRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.RevokeRoleFromUserReply:
        return await self._dispatch(
            context,
            self._app.revoke_role_from_user(request),
            rpc_name="RevokeRoleFromUser",
        )

    async def ListUserRoles(
        self,
        request: iam_pb2.ListUserRolesRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListUserRolesReply:
        return await self._dispatch(
            context, self._app.list_user_roles(request), rpc_name="ListUserRoles"
        )

    async def CheckUserAuthAndPermissions(
        self,
        request: iam_pb2.CheckUserAuthAndPermissionsRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.CheckUserAuthAndPermissionsReply:
        return await self._dispatch(
            context,
            self._app.check_user_auth_and_permissions(request),
            rpc_name="CheckUserAuthAndPermissions",
        )

    async def ListServicePermissions(
        self,
        request: iam_pb2.ListServicePermissionsRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ListServicePermissionsReply:
        return await self._dispatch(
            context,
            self._app.list_service_permissions(request),
            rpc_name="ListServicePermissions",
        )

    async def RegisterServicePermission(
        self,
        request: iam_pb2.RegisterServicePermissionRequest,
        context: aio.ServicerContext,
    ) -> iam_pb2.ServicePermission:
        return await self._dispatch(
            context,
            self._app.register_service_permission(request),
            rpc_name="RegisterServicePermission",
        )
