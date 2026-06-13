"""Server-side session management (ElastiCache / Redis / in-memory via configuration)."""

from app.core.session.contracts import (
    IRedisUrlProvider,
    ISessionAuthenticator,
    ISessionStore,
)
from app.core.session.path_policy import (
    DefaultSessionSkipPathPolicy,
    IPublicPathPolicy,
    default_session_skip_path_policy,
)
from app.core.session.session_factory import build_session_manager, build_session_store
from app.core.session.session_http_responses import (
    build_session_expired_detail,
    build_session_expired_json_response,
)
from app.core.session.session_manager import SessionManager

__all__ = [
    "IRedisUrlProvider",
    "ISessionAuthenticator",
    "ISessionStore",
    "IPublicPathPolicy",
    "DefaultSessionSkipPathPolicy",
    "default_session_skip_path_policy",
    "SessionManager",
    "build_session_expired_detail",
    "build_session_expired_json_response",
    "build_session_manager",
    "build_session_store",
]
