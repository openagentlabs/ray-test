"""Settings resolution: missing-field errors and URL composition."""

import unittest
from unittest import mock

from app.services.cognito import settings as cognito_settings_module
from app.services.cognito.settings import CognitoConfigError


class _AppSettingsStub:
    APP_ENV = "development"
    COGNITO_DOMAIN = "https://midas.auth.us-east-1.amazoncognito.com"
    COGNITO_REGION = "us-east-1"
    COGNITO_USER_POOL_ID = "us-east-1_TEST123"
    COGNITO_CLIENT_ID = "abc123clientid"
    COGNITO_CLIENT_SECRET = "supersecret"
    COGNITO_REDIRECT_URIS = "http://localhost:5173/auth/callback,https://app.example.com/auth/callback"
    COGNITO_LOGOUT_REDIRECT_URI = "http://localhost:5173/"
    COGNITO_SCOPES = "openid email profile"
    COGNITO_IDP_NAME = "MicrosoftEntraID"
    COGNITO_COOKIE_SECURE = True
    COGNITO_LOGIN_COOKIE_SECRET = "test-secret-aaaa-bbbb-cccc-dddd"
    COGNITO_LOGIN_COOKIE_TTL = 600
    COGNITO_REFRESH_COOKIE_TTL_DAYS = 30


class TestCognitoSettings(unittest.TestCase):
    def setUp(self) -> None:
        cognito_settings_module.get_cognito_settings.cache_clear()

    def tearDown(self) -> None:
        cognito_settings_module.get_cognito_settings.cache_clear()

    def test_happy_path(self) -> None:
        with mock.patch.object(cognito_settings_module, "app_settings", _AppSettingsStub()):
            cfg = cognito_settings_module.get_cognito_settings()
        self.assertEqual(
            cfg.authorize_url,
            "https://midas.auth.us-east-1.amazoncognito.com/oauth2/authorize",
        )
        self.assertEqual(
            cfg.jwks_url,
            "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123/.well-known/jwks.json",
        )
        self.assertEqual(
            cfg.issuer,
            "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST123",
        )
        self.assertTrue(cfg.redirect_uri_allowed("http://localhost:5173/auth/callback"))
        self.assertFalse(cfg.redirect_uri_allowed("http://evil.example.com/cb"))

    def test_missing_domain_raises(self) -> None:
        stub = _AppSettingsStub()
        stub.COGNITO_DOMAIN = None
        with mock.patch.object(cognito_settings_module, "app_settings", stub):
            with self.assertRaises(CognitoConfigError) as ctx:
                cognito_settings_module.get_cognito_settings()
        self.assertIn("COGNITO_DOMAIN", str(ctx.exception))

    def test_prod_requires_cookie_secret(self) -> None:
        stub = _AppSettingsStub()
        stub.APP_ENV = "production"
        stub.COGNITO_LOGIN_COOKIE_SECRET = None
        with mock.patch.object(cognito_settings_module, "app_settings", stub):
            with self.assertRaises(CognitoConfigError):
                cognito_settings_module.get_cognito_settings()

    def test_public_spa_client_no_secret_accepted(self) -> None:
        """A Cognito SPA (public) app client has no client secret; resolution must still succeed."""
        stub = _AppSettingsStub()
        stub.COGNITO_CLIENT_SECRET = None
        with mock.patch.object(cognito_settings_module, "app_settings", stub):
            cfg = cognito_settings_module.get_cognito_settings()
        self.assertIsNone(cfg.client_secret)
        self.assertEqual(cfg.client_id, "abc123clientid")

    def test_public_spa_client_empty_secret_accepted(self) -> None:
        """Empty-string secret (common when operators leave `COGNITO_CLIENT_SECRET=` in .env) is treated as absent."""
        stub = _AppSettingsStub()
        stub.COGNITO_CLIENT_SECRET = ""
        with mock.patch.object(cognito_settings_module, "app_settings", stub):
            cfg = cognito_settings_module.get_cognito_settings()
        self.assertIsNone(cfg.client_secret)

    def test_dev_generates_cookie_secret_fallback(self) -> None:
        stub = _AppSettingsStub()
        stub.COGNITO_LOGIN_COOKIE_SECRET = None
        with mock.patch.object(cognito_settings_module, "app_settings", stub):
            cfg = cognito_settings_module.get_cognito_settings()
        self.assertTrue(cfg.login_cookie_secret)
        self.assertGreaterEqual(len(cfg.login_cookie_secret), 32)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
