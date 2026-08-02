"""
Tests for Supabase Auth & JWT Context Resolution (RV-DEC-P2-0002 & RV-DEC-P2-0003).
"""

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
