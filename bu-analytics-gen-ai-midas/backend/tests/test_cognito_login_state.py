"""Unit tests for the signed cg_login binding cookie."""

import unittest
from dataclasses import dataclass

from app.services.cognito import login_state
from app.services.cognito.login_state import (
    LoginStateInvalid,
    issue,
    sha256_hex,
    verify,
)


@dataclass(frozen=True)
class _StubSettings:
    login_cookie_secret: str = "unit-test-secret-" + "x" * 48
    login_cookie_ttl_seconds: int = 600


_VERIFIER = "v" * 64  # valid PKCE range (43..128)


class TestLoginState(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = login_state.get_cognito_settings
        login_state.get_cognito_settings = lambda: _StubSettings()  # type: ignore[assignment]

    def tearDown(self) -> None:
        login_state.get_cognito_settings = self._orig  # type: ignore[assignment]

    def test_roundtrip(self) -> None:
        vhash = sha256_hex(_VERIFIER)
        token, binding = issue(vhash, settings=_StubSettings())
        b2 = verify(
            token,
            expected_state=binding.state,
            expected_verifier=_VERIFIER,
            settings=_StubSettings(),
        )
        self.assertEqual(b2.state, binding.state)
        self.assertEqual(b2.nonce, binding.nonce)
        self.assertEqual(b2.verifier_hash, vhash)

    def test_state_mismatch(self) -> None:
        vhash = sha256_hex(_VERIFIER)
        token, binding = issue(vhash, settings=_StubSettings())
        with self.assertRaises(LoginStateInvalid):
            verify(
                token,
                expected_state=binding.state + "x",
                expected_verifier=_VERIFIER,
                settings=_StubSettings(),
            )

    def test_verifier_mismatch(self) -> None:
        vhash = sha256_hex(_VERIFIER)
        token, binding = issue(vhash, settings=_StubSettings())
        with self.assertRaises(LoginStateInvalid):
            verify(
                token,
                expected_state=binding.state,
                expected_verifier="a" * 64,
                settings=_StubSettings(),
            )

    def test_tampered_token(self) -> None:
        vhash = sha256_hex(_VERIFIER)
        token, binding = issue(vhash, settings=_StubSettings())
        tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
        with self.assertRaises(LoginStateInvalid):
            verify(
                tampered,
                expected_state=binding.state,
                expected_verifier=_VERIFIER,
                settings=_StubSettings(),
            )

    def test_wrong_secret_rejected(self) -> None:
        vhash = sha256_hex(_VERIFIER)
        token, binding = issue(vhash, settings=_StubSettings())

        @dataclass(frozen=True)
        class _Other:
            login_cookie_secret: str = "different-secret-" + "y" * 48
            login_cookie_ttl_seconds: int = 600

        with self.assertRaises(LoginStateInvalid):
            verify(
                token,
                expected_state=binding.state,
                expected_verifier=_VERIFIER,
                settings=_Other(),
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
