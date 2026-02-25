"""
Tests for app.core.security — JWT tokens, password hashing.

These tests exercise the pure-logic helpers and do NOT require Redis.
Redis-dependent helpers (revoke_token, is_token_revoked) are tested
via mocking.
"""
import time
from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from jose import jwt


# ---------------------------------------------------------------------------
# Token creation & verification
# ---------------------------------------------------------------------------

class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_token_is_valid_jwt(self):
        from app.core.security import create_access_token
        from app.core.config import settings

        token = create_access_token(subject="admin")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "admin"

    def test_token_contains_required_claims(self):
        from app.core.security import create_access_token
        from app.core.config import settings

        token = create_access_token(subject="testuser")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert "sub" in payload
        assert "exp" in payload
        assert "jti" in payload
        assert "iat" in payload

    def test_token_subject_is_string(self):
        """Even if an int is passed, sub should be stored as a string."""
        from app.core.security import create_access_token
        from app.core.config import settings

        token = create_access_token(subject=42)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "42"

    def test_custom_expiry(self):
        from app.core.security import create_access_token
        from app.core.config import settings

        delta = timedelta(minutes=5)
        token = create_access_token(subject="admin", expires_delta=delta)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # The exp should be roughly 5 minutes from now
        now = time.time()
        assert payload["exp"] - now < 310  # within ~5 min + small margin
        assert payload["exp"] - now > 250  # not too early

    def test_default_expiry_uses_settings(self):
        from app.core.security import create_access_token
        from app.core.config import settings

        token = create_access_token(subject="admin")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        expected_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        now = time.time()
        # Token should expire within the configured window (allow 10s margin)
        diff = payload["exp"] - now
        assert abs(diff - expected_seconds) < 10

    def test_each_token_has_unique_jti(self):
        from app.core.security import create_access_token
        from app.core.config import settings

        token1 = create_access_token(subject="admin")
        token2 = create_access_token(subject="admin")

        p1 = jwt.decode(token1, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        p2 = jwt.decode(token2, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert p1["jti"] != p2["jti"]


# ---------------------------------------------------------------------------
# Password hashing & verification
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """Tests for get_password_hash() and verify_password()."""

    def test_hash_and_verify_roundtrip(self):
        from app.core.security import get_password_hash, verify_password

        raw = "my-secure-p@ssw0rd!"
        hashed = get_password_hash(raw)
        assert verify_password(raw, hashed) is True

    def test_wrong_password_fails(self):
        from app.core.security import get_password_hash, verify_password

        hashed = get_password_hash("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_is_not_plaintext(self):
        from app.core.security import get_password_hash

        raw = "password123"
        hashed = get_password_hash(raw)
        assert hashed != raw
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_same_password_produces_different_hashes(self):
        """Bcrypt uses random salt; two hashes of the same password differ."""
        from app.core.security import get_password_hash

        h1 = get_password_hash("password")
        h2 = get_password_hash("password")
        assert h1 != h2


# ---------------------------------------------------------------------------
# Token revocation (mocked Redis)
# ---------------------------------------------------------------------------

class TestTokenRevocation:
    """Tests for revoke_token() and is_token_revoked() with mocked Redis."""

    @patch("app.core.security._get_redis")
    def test_revoke_token_sets_key_with_ttl(self, mock_get_redis):
        from app.core.security import revoke_token

        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        revoke_token("test-jti-123", ttl=3600)
        mock_redis.setex.assert_called_once_with(
            "revoked_token:test-jti-123", 3600, "1"
        )

    @patch("app.core.security._get_redis")
    def test_is_token_revoked_returns_true_when_key_exists(self, mock_get_redis):
        from app.core.security import is_token_revoked

        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.exists.return_value = 1
        assert is_token_revoked("revoked-jti") is True

    @patch("app.core.security._get_redis")
    def test_is_token_revoked_returns_false_when_key_missing(self, mock_get_redis):
        from app.core.security import is_token_revoked

        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.exists.return_value = 0
        assert is_token_revoked("valid-jti") is False
