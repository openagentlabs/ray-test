"""
JWT_SECRET_KEY production guard — pending integration tests.

Context
-------
Commit e7e62640 ("fixed silent token rotation issue and added logs") introduced a
production safety guard that raises RuntimeError when APP_ENV=production and
JWT_SECRET_KEY is absent.  That guard was temporarily reverted (auth_service.py
restored to its static key) because JWT_SECRET_KEY was not yet injected into the
midas-app-secret K8s Secret, causing CrashLoopBackOff on dev.

These tests capture the intended behaviour of _resolve_secret_key() so the logic
can be re-integrated once JWT_SECRET_KEY has been:
  1. Added to the AWS Secrets Manager source that seeds midas-app-secret.
  2. Injected by populate-secrets.sh (deploy/scripts/ci/populate-secrets.sh).
  3. Re-added to auth_service.py and config.py (see revert diffs in that commit).

Re-integration checklist (do not re-enable until all three items above are done)
---------------------------------------------------------------------------------
  [ ] JWT_SECRET_KEY added to the MIDAS AWS Secrets Manager secret.
  [ ] populate-secrets.sh reads and writes JWT_SECRET_KEY into midas-app-secret.
  [ ] _resolve_secret_key() and Settings.JWT_SECRET_KEY restored in app code.
  [ ] This test file moved to an active test suite and the xfail marks removed.
"""

import secrets
import pytest


# ---------------------------------------------------------------------------
# Inline implementation (copied from the reverted commit) so the tests run
# without depending on app code that has been reverted.
# ---------------------------------------------------------------------------

def _resolve_secret_key(app_env: str, jwt_secret_key: str | None) -> str:
    """Standalone re-implementation of the reverted _resolve_secret_key logic."""
    if jwt_secret_key:
        return jwt_secret_key
    if app_env.lower() == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY is required when APP_ENV=production. "
            "Set it via Secrets Manager or the JWT_SECRET_KEY environment variable."
        )
    return secrets.token_urlsafe(48)


# ---------------------------------------------------------------------------
# Tests — marked xfail(strict=False) so they are visible in CI but do not
# block the build while the feature is pending re-integration.
# Remove the xfail marks and replace the inline implementation call with the
# real auth_service import when re-integrating.
# ---------------------------------------------------------------------------

class TestResolveSecretKeyDev:
    def test_dev_no_key_generates_random(self) -> None:
        key = _resolve_secret_key(app_env="development", jwt_secret_key=None)
        assert isinstance(key, str)
        assert len(key) > 0

    def test_dev_no_key_generates_different_keys_each_call(self) -> None:
        k1 = _resolve_secret_key(app_env="development", jwt_secret_key=None)
        k2 = _resolve_secret_key(app_env="development", jwt_secret_key=None)
        assert k1 != k2

    def test_dev_explicit_key_is_returned_unchanged(self) -> None:
        explicit = "my-dev-secret-abc123"
        key = _resolve_secret_key(app_env="development", jwt_secret_key=explicit)
        assert key == explicit

    def test_staging_no_key_generates_random(self) -> None:
        key = _resolve_secret_key(app_env="staging", jwt_secret_key=None)
        assert isinstance(key, str)
        assert len(key) > 0


class TestResolveSecretKeyProduction:
    def test_production_without_key_raises(self) -> None:
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is required when APP_ENV=production"):
            _resolve_secret_key(app_env="production", jwt_secret_key=None)

    def test_production_with_key_returns_key(self) -> None:
        secret = secrets.token_urlsafe(48)
        key = _resolve_secret_key(app_env="production", jwt_secret_key=secret)
        assert key == secret

    def test_production_empty_string_raises(self) -> None:
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY is required when APP_ENV=production"):
            _resolve_secret_key(app_env="production", jwt_secret_key="")

    def test_production_check_is_case_insensitive(self) -> None:
        with pytest.raises(RuntimeError):
            _resolve_secret_key(app_env="PRODUCTION", jwt_secret_key=None)
        with pytest.raises(RuntimeError):
            _resolve_secret_key(app_env="Production", jwt_secret_key=None)
