"""Repository ports are structural supertypes of DynamoDB adapters."""

from __future__ import annotations

from iam_service.database.repositories.invite_repository import InviteRepository
from iam_service.database.repositories.login_repository import LoginRepository
from iam_service.database.repositories.user_repository import UserRepository
from iam_service.repositories.ports.invite_port import InvitePort
from iam_service.repositories.ports.login_port import LoginPort
from iam_service.repositories.ports.user_port import UserPort


def test_user_repository_satisfies_user_port() -> None:
    """``UserRepository`` implements ``UserPort`` structurally."""
    repo: UserPort = UserRepository  # type: ignore[assignment]
    assert hasattr(repo, "get_by_id")
    assert hasattr(repo, "put")


def test_login_repository_satisfies_login_port() -> None:
    """``LoginRepository`` implements ``LoginPort`` structurally."""
    repo: LoginPort = LoginRepository  # type: ignore[assignment]
    assert hasattr(repo, "query_by_user")


def test_invite_repository_satisfies_invite_port() -> None:
    """``InviteRepository`` implements ``InvitePort`` structurally."""
    repo: InvitePort = InviteRepository  # type: ignore[assignment]
    assert hasattr(repo, "scan_page")
