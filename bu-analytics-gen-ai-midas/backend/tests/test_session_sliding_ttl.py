"""
Unit tests for ISU0003 fix — Redis sid TTL sliding window.

Covers:
  InMemorySessionStore.extend():
    1. Advancing the expiry of an existing key.
    2. No-op (no KeyError) when the key is absent.
  RedisSessionStore.extend():
    3. Calls redis.expire() with the prefixed key and clamped TTL.
    4. Swallows Redis exceptions and does not propagate them.
  SessionManager._authenticate_verbose() (via authenticate_access_token_verbose()):
    5. Valid token + valid sid  → extend() called with correct sid and ttl.
    6. Valid token + invalid sid → "sid_invalid" returned; extend() not called.
    7. Token without sid claim  → extend() not called (backward compat).
"""

import time
import unittest
from datetime import datetime, timezone
from typing import Optional
from unittest import mock


# ---------------------------------------------------------------------------
# InMemorySessionStore tests
# ---------------------------------------------------------------------------

class TestInMemorySessionStoreExtend(unittest.IsolatedAsyncioTestCase):
    """IsolatedAsyncioTestCase gives each test its own asyncio event loop."""

    def _make_store(self):
        from app.core.session.session_backends import InMemorySessionStore
        return InMemorySessionStore()

    async def test_extend_advances_expiry_of_existing_key(self) -> None:
        """extend() on a live key must push its expiry further into the future."""
        store = self._make_store()
        sid = "test-sid-1"
        username = "alice"

        await store.save(sid, username, ttl_seconds=60)

        before_extend = store._data[sid][1]  # original expiry epoch
        await store.extend(sid, ttl_seconds=3600)
        after_extend = store._data[sid][1]   # new expiry epoch

        self.assertGreater(after_extend, before_extend)
        # New expiry must be roughly now + 3600 s (within a 2-second tolerance).
        self.assertAlmostEqual(after_extend, time.time() + 3600, delta=2)
        # Username must be preserved unchanged.
        self.assertEqual(store._data[sid][0], username)

    async def test_extend_on_missing_key_is_noop(self) -> None:
        """extend() on an absent key must not raise and must not create a new entry."""
        store = self._make_store()
        # Should complete without exception.
        await store.extend("nonexistent-sid", ttl_seconds=3600)
        self.assertNotIn("nonexistent-sid", store._data)

    async def test_extend_with_minimum_ttl_clamp(self) -> None:
        """TTL of 0 is clamped to 1 so the key is not immediately expired."""
        store = self._make_store()
        sid = "clamp-sid"
        await store.save(sid, "bob", ttl_seconds=60)
        await store.extend(sid, ttl_seconds=0)
        # Key should still be present and expiry >= now.
        self.assertIn(sid, store._data)
        self.assertGreater(store._data[sid][1], time.time() - 1)

    async def test_extend_does_not_resurrect_expired_key(self) -> None:
        """
        extend() on a key whose expiry epoch has already passed must be a no-op.
        The in-memory store evicts lazily; an already-expired key sitting in _data
        must never be granted a new TTL by a direct extend() call.
        """
        store = self._make_store()
        sid = "expired-sid"
        # Manually plant an already-expired entry in the private dict.
        store._data[sid] = ("alice", time.time() - 1)  # expired 1 second ago

        await store.extend(sid, ttl_seconds=3600)

        # The key must remain with its original (expired) expiry, not a new one.
        self.assertIn(sid, store._data)
        self.assertLessEqual(store._data[sid][1], time.time())


# ---------------------------------------------------------------------------
# RedisSessionStore tests
# ---------------------------------------------------------------------------

class TestRedisSessionStoreExtend(unittest.IsolatedAsyncioTestCase):

    def _make_store_with_mock_redis(self):
        """Construct a RedisSessionStore with redis.asyncio replaced by a MagicMock."""
        import redis.asyncio as redis_module

        mock_redis = mock.AsyncMock()
        with mock.patch.object(redis_module, "from_url", return_value=mock_redis):
            from app.core.session.session_backends import RedisSessionStore
            store = RedisSessionStore(url="redis://localhost:6379", key_prefix="test:")
        # Patch the already-constructed internal redis client reference.
        store._redis = mock_redis
        return store, mock_redis

    async def test_extend_calls_redis_expire_with_prefixed_key(self) -> None:
        """extend() must call redis.expire(<prefix><sid>, ttl) exactly once."""
        store, mock_redis = self._make_store_with_mock_redis()
        mock_redis.expire = mock.AsyncMock(return_value=True)

        await store.extend("abc-123", ttl_seconds=3600)

        mock_redis.expire.assert_awaited_once_with("test:abc-123", 3600)

    async def test_extend_clamps_ttl_to_minimum_one(self) -> None:
        """A zero TTL must be clamped to 1 before passing to Redis."""
        store, mock_redis = self._make_store_with_mock_redis()
        mock_redis.expire = mock.AsyncMock(return_value=True)

        await store.extend("abc-123", ttl_seconds=0)

        mock_redis.expire.assert_awaited_once_with("test:abc-123", 1)

    async def test_extend_swallows_redis_exception_and_does_not_raise(self) -> None:
        """A Redis failure in extend() must be caught; the call must not propagate."""
        store, mock_redis = self._make_store_with_mock_redis()
        mock_redis.expire = mock.AsyncMock(side_effect=OSError("connection refused"))

        # Must not raise.
        await store.extend("abc-123", ttl_seconds=3600)

    async def test_extend_logs_warning_on_redis_failure(self) -> None:
        """A Redis failure in extend() must emit a logger.warning."""
        store, mock_redis = self._make_store_with_mock_redis()
        mock_redis.expire = mock.AsyncMock(side_effect=OSError("timeout"))

        with mock.patch("app.core.session.session_backends.logger") as mock_logger:
            await store.extend("abc-123", ttl_seconds=3600)

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn("extend", warning_msg.lower())


# ---------------------------------------------------------------------------
# SessionManager tests — sliding-window wired into _authenticate_verbose()
# ---------------------------------------------------------------------------

def _make_user_in_db(username: str = "alice") -> "UserInDB":
    from app.models.schemas import UserInDB
    return UserInDB(
        id=1,
        username=username,
        full_name="Alice",
        email="alice@example.com",
        hashed_password="$2b$12$dummyhash",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_token_data(username: str = "alice", session_id: Optional[str] = "sid-abc"):
    from app.models.schemas import TokenData
    return TokenData(username=username, session_id=session_id)


class TestSessionManagerSlidingTTL(unittest.IsolatedAsyncioTestCase):

    def _make_manager(self, store):
        from app.core.session.session_manager import SessionManager
        return SessionManager(store=store, ttl_seconds=3600)

    async def test_valid_token_valid_sid_calls_extend(self) -> None:
        """
        When the JWT is valid and the sid exists in the store, extend() must be
        called with the correct session_id and the manager's ttl_seconds.
        """
        store = mock.AsyncMock()
        store.is_valid = mock.AsyncMock(return_value=True)
        store.extend = mock.AsyncMock()

        manager = self._make_manager(store)

        token_data = _make_token_data(username="alice", session_id="sid-abc")
        user = _make_user_in_db("alice")

        with mock.patch("app.core.session.session_manager.verify_token", return_value=token_data), \
             mock.patch("app.core.session.session_manager.user_db") as mock_db:
            mock_db.get_user_by_username.return_value = user
            result_user, reason = await manager.authenticate_access_token_verbose("dummy-token")

        self.assertEqual(reason, "ok")
        self.assertEqual(result_user, user)
        store.extend.assert_awaited_once_with("sid-abc", 3600)

    async def test_invalid_sid_does_not_call_extend(self) -> None:
        """
        When the sid is not found in the store (expired or invalid), the manager
        must return "sid_invalid" and must NOT call extend().
        """
        store = mock.AsyncMock()
        store.is_valid = mock.AsyncMock(return_value=False)
        store.extend = mock.AsyncMock()

        manager = self._make_manager(store)

        token_data = _make_token_data(username="alice", session_id="expired-sid")
        user = _make_user_in_db("alice")

        with mock.patch("app.core.session.session_manager.verify_token", return_value=token_data), \
             mock.patch("app.core.session.session_manager.user_db") as mock_db:
            mock_db.get_user_by_username.return_value = user
            result_user, reason = await manager.authenticate_access_token_verbose("dummy-token")

        self.assertIsNone(result_user)
        self.assertEqual(reason, "sid_invalid")
        store.extend.assert_not_awaited()

    async def test_token_without_sid_does_not_call_extend(self) -> None:
        """
        Tokens issued without a sid claim (backward compatibility) must still
        authenticate successfully without touching extend().
        """
        store = mock.AsyncMock()
        store.is_valid = mock.AsyncMock()
        store.extend = mock.AsyncMock()

        manager = self._make_manager(store)

        # session_id=None simulates a legacy token with no sid claim.
        token_data = _make_token_data(username="alice", session_id=None)
        user = _make_user_in_db("alice")

        with mock.patch("app.core.session.session_manager.verify_token", return_value=token_data), \
             mock.patch("app.core.session.session_manager.user_db") as mock_db:
            mock_db.get_user_by_username.return_value = user
            result_user, reason = await manager.authenticate_access_token_verbose("dummy-token")

        self.assertEqual(reason, "ok")
        self.assertEqual(result_user, user)
        store.is_valid.assert_not_awaited()
        store.extend.assert_not_awaited()

    async def test_invalid_jwt_does_not_call_extend(self) -> None:
        """A completely invalid JWT must return 'jwt_invalid' without touching the store."""
        store = mock.AsyncMock()
        store.extend = mock.AsyncMock()

        manager = self._make_manager(store)

        with mock.patch("app.core.session.session_manager.verify_token", return_value=None):
            result_user, reason = await manager.authenticate_access_token_verbose("bad-token")

        self.assertIsNone(result_user)
        self.assertEqual(reason, "jwt_invalid")
        store.extend.assert_not_awaited()

    async def test_extend_failure_does_not_block_validated_request(self) -> None:
        """
        If extend() raises unexpectedly the authenticated request must still succeed
        with reason "ok". The TTL slide is best-effort: its failure must never cause a 500.
        """
        store = mock.AsyncMock()
        store.is_valid = mock.AsyncMock(return_value=True)
        store.extend = mock.AsyncMock(side_effect=RuntimeError("store backend down"))

        manager = self._make_manager(store)

        token_data = _make_token_data(username="alice", session_id="sid-ok")
        user = _make_user_in_db("alice")

        with mock.patch("app.core.session.session_manager.verify_token", return_value=token_data), \
             mock.patch("app.core.session.session_manager.user_db") as mock_db:
            mock_db.get_user_by_username.return_value = user
            # Must not raise despite extend() failing.
            result_user, reason = await manager.authenticate_access_token_verbose("dummy-token")

        self.assertEqual(reason, "ok")
        self.assertEqual(result_user, user)
        store.extend.assert_awaited_once()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
