from datetime import datetime, timezone

import bcrypt
import pytest

from web_gateway.core.exceptions import ConflictException, ForbiddenException, NotFoundException, UnauthorizedException
from web_gateway.core.rbac import has_permission
from web_gateway.core.security import create_access_token, decode_access_token, hash_password, verify_password


class TestSecurity:
    def test_hash_password_roundtrip(self):
        pw = "securePassword123!"
        hashed = hash_password(pw)
        assert hashed != pw
        assert hashed.startswith("$2b$")
        assert verify_password(pw, hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_hash_password_different_salts(self):
        pw = "samepassword"
        h1 = hash_password(pw)
        h2 = hash_password(pw)
        assert h1 != h2

    def test_create_and_decode_token(self):
        token = create_access_token(user_id=42, role="admin")
        assert isinstance(token, str)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_decode_invalid_token(self):
        assert decode_access_token("invalid.token.here") is None
        assert decode_access_token("") is None

    def test_decode_expired_token(self):
        from jose import jwt
        from web_gateway.core.config import settings
        expired = jwt.encode(
            {"sub": "1", "role": "admin", "exp": 1000000},
            settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
        assert decode_access_token(expired) is None


class TestRBAC:
    def test_admin_has_all(self):
        assert has_permission("admin", "patients", "*")
        assert has_permission("admin", "users", "create")
        assert has_permission("admin", "settings", "backup")

    def test_orthodontist_permissions(self):
        assert has_permission("orthodontist", "patients", "create")
        assert has_permission("orthodontist", "patients", "read")
        assert has_permission("orthodontist", "analyses", "validate")
        assert has_permission("orthodontist", "analyses", "delete_own")
        assert has_permission("orthodontist", "reports", "sign")
        assert not has_permission("orthodontist", "settings", "*")
        assert not has_permission("orthodontist", "users", "create")

    def test_assistant_permissions(self):
        assert has_permission("assistant", "patients", "create")
        assert has_permission("assistant", "patients", "read")
        assert has_permission("assistant", "analyses", "read")
        assert not has_permission("assistant", "analyses", "validate")
        assert not has_permission("assistant", "analyses", "delete_own")
        assert not has_permission("assistant", "reports", "sign")

    def test_intern_permissions(self):
        assert has_permission("intern", "patients", "read")
        assert has_permission("intern", "analyses", "read")
        assert not has_permission("intern", "patients", "create")
        assert not has_permission("intern", "analyses", "delete_own")
        assert not has_permission("intern", "reports", "sign")

    def test_unknown_role(self):
        assert not has_permission("hacker", "patients", "read")


class TestExceptions:
    def test_not_found_exception(self):
        exc = NotFoundException("Test not found")
        assert exc.status_code == 404
        assert exc.detail == "Test not found"

    def test_forbidden_exception(self):
        exc = ForbiddenException()
        assert exc.status_code == 403
        assert exc.detail == "Accès refusé"

    def test_unauthorized_exception(self):
        exc = UnauthorizedException()
        assert exc.status_code == 401
        assert exc.detail == "Non authentifié"

    def test_conflict_exception(self):
        exc = ConflictException("Email exists")
        assert exc.status_code == 409
        assert exc.detail == "Email exists"
