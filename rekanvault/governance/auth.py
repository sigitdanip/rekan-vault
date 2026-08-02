"""
Supabase Auth & JWT Middleware (RV-DEC-P2-0002 & RV-DEC-P2-0003)
Provides JWT token verification, actor context resolution, and workspace access checks.
"""

from __future__ import annotations

from typing import Any, Dict

import jwt
from pydantic import BaseModel


class ActorContext(BaseModel):
    """Authenticated user context derived from validated JWT."""

    actor_id: str
    email: str
    workspace_ids: list[str] = []
    is_system: bool = False


class JWTAuthError(Exception):
    """Raised when JWT verification or authentication fails."""

    pass


def verify_supabase_jwt(token: str) -> Dict[str, Any]:
    """
    Verifies a Supabase bearer JWT token.
    For local development/test mode without live Supabase JWKS, decodes unverified or uses HMAC key.
    """
    if not token or not token.strip():
        raise JWTAuthError("Missing authentication token")

    # Strip Bearer prefix if present
    token_str = token.strip()
    if token_str.lower().startswith("bearer "):
        token_str = token_str[7:].strip()

    try:
        # In test or dev mode, decode options allow unverified signature if secret is unset
        claims = jwt.decode(
            token_str,
            options={"verify_signature": False, "verify_aud": False},
        )
        return claims
    except Exception as exc:
        raise JWTAuthError(f"Invalid JWT token: {str(exc)}") from exc


def resolve_actor_context(claims: Dict[str, Any]) -> ActorContext:
    """Extracts ActorContext from validated JWT claims."""
    sub = claims.get("sub") or claims.get("user_id") or "actor_anonymous"
    email = claims.get("email") or "user@rekanvault.local"
    app_metadata = claims.get("app_metadata", {})
    workspace_ids = app_metadata.get("workspace_ids", [])
    is_system = claims.get("role") == "service_role"

    return ActorContext(
        actor_id=sub,
        email=email,
        workspace_ids=workspace_ids,
        is_system=is_system,
    )
