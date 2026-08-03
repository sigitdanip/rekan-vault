"""
Tests for Supabase Auth & JWT Context Resolution (RV-DEC-P2-0002 & RV-DEC-P2-0003).
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from rekanvault.governance.auth import (
    JWTAuthError,
    resolve_actor_context,
    verify_supabase_jwt,
)


def test_verify_and_resolve_jwt() -> None:
    payload = {
        "sub": "user_uuid_12345",
        "email": "sigit@rekanvault.local",
        "app_metadata": {"workspace_ids": ["ws_101", "ws_102"]},
        "role": "authenticated",
    }
    encoded = jwt.encode(payload, "secret", algorithm="HS256")

    claims = verify_supabase_jwt(f"Bearer {encoded}")
    assert claims["sub"] == "user_uuid_12345"

    ctx = resolve_actor_context(claims)
    assert ctx.actor_id == "user_uuid_12345"
    assert ctx.email == "sigit@rekanvault.local"
    assert "ws_101" in ctx.workspace_ids
    assert ctx.is_system is False


def test_missing_token_raises_jwt_error() -> None:
    with pytest.raises(JWTAuthError):
        verify_supabase_jwt("")


def test_expired_jwt_rejected() -> None:
    """P2-T7: JWT with exp claim in the past must be rejected (401-equivalent)."""
    past_exp = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {"sub": "user_uuid_12345", "exp": past_exp}
    encoded = jwt.encode(payload, "secret", algorithm="HS256")

    with pytest.raises(JWTAuthError):
        verify_supabase_jwt(f"Bearer {encoded}")


def test_wrong_issuer_jwt_rejected() -> None:
    """P2-T7: JWT with issuer not matching RV_SUPABASE_JWT_ISSUER must be rejected."""
    import os

    os.environ["RV_SUPABASE_JWT_ISSUER"] = "http://localhost:54321/auth/v1"
    try:
        payload = {
            "sub": "user_uuid_12345",
            "iss": "https://evil.example.com/auth/v1",
        }
        encoded = jwt.encode(payload, "secret", algorithm="HS256")

        with pytest.raises(JWTAuthError):
            verify_supabase_jwt(f"Bearer {encoded}")
    finally:
        os.environ.pop("RV_SUPABASE_JWT_ISSUER", None)
