"""
HTTP client factory for source connectors (Google Drive, Notion).

Each connector instance gets its own ``httpx.AsyncClient`` configured with:
  * IPv4-only transport (``local_address="0.0.0.0"``) — this host has a broken
    IPv6 stack; curl works, Python ``httpx`` hangs without this override.
  * Per-call timeout read from config (default 30s).
"""

from __future__ import annotations

import httpx

from apps.api.config import settings

# ``local_address="0.0.0.0"`` forces IPv4 on the dual-stack socket — see module docstring.
_IPV4_TRANSPORT = httpx.AsyncHTTPTransport(local_address="0.0.0.0")

# Type alias — ``httpx.AsyncClient`` is already the type. Re-exporting keeps
# connector call-sites decoupled from the factory internals.
SourceClient = httpx.AsyncClient


def create_source_client(timeout_seconds: int | None = None) -> SourceClient:
    """Build a fresh ``httpx.AsyncClient`` with IPv4-only transport.

    Ponytail: one client per connector — no module-level singleton. Sharing a
    client across connectors with different timeouts would force every caller
    through the same ``Timeout`` object, defeating the per-connector config.

    Args:
        timeout_seconds: Override the per-request timeout. When ``None`` the
            ``RV_GOOGLE_API_TIMEOUT_SECONDS`` config is used. Notion callers
            should pass ``settings.RV_NOTION_API_TIMEOUT_SECONDS`` explicitly.

    Returns:
        An un-started ``httpx.AsyncClient`` bound to the IPv4 transport.
    """
    seconds = timeout_seconds if timeout_seconds is not None else settings.RV_GOOGLE_API_TIMEOUT_SECONDS
    return httpx.AsyncClient(transport=_IPV4_TRANSPORT, timeout=httpx.Timeout(seconds))
