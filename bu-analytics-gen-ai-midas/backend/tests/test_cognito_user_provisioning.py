"""JIT provisioning: username derivation and race-tolerant read-back."""

import unittest
from datetime import datetime
from unittest import mock

from app.services.cognito import user_provisioning
from app.services.cognito.user_provisioning import (
    COGNITO_USERNAME_PREFIX,
    _cognito_username,
    _default_full_name,
    get_or_create_from_cognito,
)


def _make_user(**overrides):
    from app.models.schemas import UserInDB

    base = dict(
        id=1,
        username=f"{COGNITO_USERNAME_PREFIX}abc-sub-1234",
        full_name="Jane Doe",
        email="jane@example.com",
        hashed_password="$2b$12$dummyhashvalue",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    base.update(overrides)
    return UserInDB(**base)


class TestUsernameDerivation(unittest.TestCase):
    def test_prefix_applied(self) -> None:
        self.assertTrue(_cognito_username("abc").startswith(COGNITO_USERNAME_PREFIX))

    def test_truncated_to_50_chars(self) -> None:
        name = _cognito_username("x" * 200)
        self.assertLessEqual(len(name), 50)

    def test_default_full_name_prefers_claim(self) -> None:
        self.assertEqual(
            _default_full_name("  Jane  ", "jane@example.com", "abc"),
            "Jane",
        )

    def test_default_full_name_falls_back_to_email(self) -> None:
        self.assertEqual(
            _default_full_name(None, "jane@example.com", "abc"),
            "jane@example.com",
        )

    def test_default_full_name_falls_back_to_sub(self) -> None:
        self.assertEqual(_default_full_name(None, None, "abc-123"), "abc-123")


class TestGetOrCreate(unittest.TestCase):
    def test_empty_sub_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_or_create_from_cognito(sub="", email=None, full_name=None)

    def test_existing_user_returned(self) -> None:
        existing = _make_user()
        with mock.patch.object(user_provisioning, "user_db") as udb:
            udb.get_user_by_username.return_value = existing
            result = get_or_create_from_cognito(
                sub="abc-sub-1234",
                email="jane@example.com",
                full_name="Jane Doe",
            )
        self.assertIs(result, existing)
        udb.create_user.assert_not_called()

    def test_new_user_created(self) -> None:
        new = _make_user(id=2)
        with mock.patch.object(user_provisioning, "user_db") as udb:
            udb.get_user_by_username.return_value = None
            udb.create_user.return_value = new
            result = get_or_create_from_cognito(
                sub="abc-sub-1234",
                email="jane@example.com",
                full_name="Jane Doe",
            )
        self.assertIs(result, new)
        udb.create_user.assert_called_once()

    def test_race_condition_reads_back(self) -> None:
        winner = _make_user(id=3)
        with mock.patch.object(user_provisioning, "user_db") as udb:
            # First lookup: not found. create_user fails (None). Re-lookup: other coroutine won.
            udb.get_user_by_username.side_effect = [None, winner]
            udb.create_user.return_value = None
            result = get_or_create_from_cognito(
                sub="abc-sub-1234",
                email="jane@example.com",
                full_name="Jane Doe",
            )
        self.assertIs(result, winner)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
