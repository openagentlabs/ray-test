"""Re-export static bearer auth for backwards-compatible imports."""

from testing.api_client.auth_protocol import StaticBearerAuthProvider

__all__ = ["StaticBearerAuthProvider"]
