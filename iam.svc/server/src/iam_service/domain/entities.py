"""Domain entity aliases — persistence records are the canonical domain shape."""

from __future__ import annotations

from iam_service.database.models.records import (
    AuthSessionRecord,
    DeploymentAdminRecord,
    InviteRecord,
    LoginRecord,
    LoginTypeRecord,
    PermissionRecord,
    RoleRecord,
    SessionRecord,
    SkillListRecord,
    SkillRecord,
    UserRecord,
    UserSkillRecord,
    UserTypeRecord,
)

User = UserRecord
UserType = UserTypeRecord
Login = LoginRecord
LoginType = LoginTypeRecord
Session = SessionRecord
Invite = InviteRecord
Skill = SkillRecord
SkillList = SkillListRecord
UserSkill = UserSkillRecord
Role = RoleRecord
Permission = PermissionRecord
DeploymentAdmin = DeploymentAdminRecord
AuthSession = AuthSessionRecord
