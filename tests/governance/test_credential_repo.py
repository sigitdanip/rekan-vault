"""
Tests for the encrypted credential repository (P3).

Follows existing patterns: no conftest.py, inline ``AsyncMock``/``MagicMock``
for the ``AsyncSession``, no fixtures. Round-trip tests use a real
``CredentialEncryptor`` with a synthetic ``KeyManager`` so we exercise the
actual encrypt/decrypt path, not a mock.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from rekanvault.governance.encryption import CredentialEncryptor, KeyManager
from rekanvault.sources import credential_repo
from rekanvault.storage.models import Credential

# ---------- helpers ---------------------------------------------------------


def _make_encryptor_with_key(key_id: str = "test-key") -> tuple[CredentialEncryptor, bytes]:
    """Return an encryptor bound to a fresh random 32-byte key under ``key_id``."""
    km = KeyManager()
    raw_key = os.urandom(32)
    km.keys[key_id] = raw_key
    km.active_key_id = key_id
    return CredentialEncryptor(key_manager=km), raw_key


def _mock_session_with_credential(cred: Credential | None) -> AsyncMock:
    """Return an ``AsyncMock`` session whose ``execute`` resolves to ``cred``."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = cred
    # ``update_credential`` / ``delete_credential`` chain
    # ``.order_by(...).limit(1)`` — emulate that by attaching the same result.
    session.execute.return_value = result
    return session


# ---------- store_credential -------------------------------------------------


@pytest.mark.asyncio
async def test_store_credential_decrypts_correctly() -> None:
    """Stored ciphertext must round-trip back to the same plaintext via decrypt."""
    encryptor, _ = _make_encryptor_with_key()
    original_factory = credential_repo._encryptor
    credential_repo._encryptor = lambda: encryptor  # type: ignore[assignment]
    try:
        session = AsyncMock()
        workspace_id = uuid.uuid4()
        source_id = uuid.uuid4()
        plaintext = "google_refresh_token_abc"

        cred = await credential_repo.store_credential(
            session=session,
            workspace_id=workspace_id,
            source_id=source_id,
            plaintext=plaintext,
        )

        assert isinstance(cred, Credential)
        assert cred.workspace_id == workspace_id
        assert cred.source_id == source_id
        assert cred.ciphertext != plaintext
        session.add.assert_called_once_with(cred)

        # Round-trip with the same encryptor — ciphertext must decrypt cleanly.
        decrypted = encryptor.decrypt(cred.ciphertext, cred.iv, cred.key_id)
        assert decrypted == plaintext
    finally:
        credential_repo._encryptor = original_factory  # type: ignore[assignment]


# ---------- get_credential ---------------------------------------------------


@pytest.mark.asyncio
async def test_get_credential_when_none_exists_returns_none() -> None:
    """Missing credential must return ``None`` (not raise) — used on cold start."""
    session = _mock_session_with_credential(cred=None)

    result = await credential_repo.get_credential(session=session, source_id=uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_store_then_get_roundtrip() -> None:
    """End-to-end: store via the repo, then read it back as plaintext."""
    encryptor, _ = _make_encryptor_with_key()

    # We need both operations to see the same encryptor instance — patch the
    # repo's factory so the get-side uses the same key the store-side used.
    original_factory = credential_repo._encryptor
    credential_repo._encryptor = lambda: encryptor  # type: ignore[assignment]
    try:
        # Phase 1: store
        write_session = AsyncMock()
        workspace_id = uuid.uuid4()
        source_id = uuid.uuid4()
        plaintext = "notion_secret_token_xyz"
        cred = await credential_repo.store_credential(
            session=write_session,
            workspace_id=workspace_id,
            source_id=source_id,
            plaintext=plaintext,
        )

        # Phase 2: read back from a session that finds that exact credential
        read_session = _mock_session_with_credential(cred=cred)
        result = await credential_repo.get_credential(session=read_session, source_id=source_id)
    finally:
        credential_repo._encryptor = original_factory  # type: ignore[assignment]

    assert result == plaintext


# ---------- update_credential -----------------------------------------------


@pytest.mark.asyncio
async def test_update_credential_replaces_plaintext() -> None:
    """``update_credential`` must re-encrypt the row in place with the new token."""
    encryptor, _ = _make_encryptor_with_key()
    original_factory = credential_repo._encryptor
    credential_repo._encryptor = lambda: encryptor  # type: ignore[assignment]
    try:
        # Seed an existing credential (encrypted with the same key)
        old_token = "old_refresh_token_111"
        c_b64, iv_b64, key_id = encryptor.encrypt(old_token)
        existing = Credential(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            key_id=key_id,
            ciphertext=c_b64,
            iv=iv_b64,
        )

        session = _mock_session_with_credential(cred=existing)
        new_token = "new_refresh_token_222"

        updated = await credential_repo.update_credential(
            session=session,
            source_id=existing.source_id,
            new_plaintext=new_token,
        )
    finally:
        credential_repo._encryptor = original_factory  # type: ignore[assignment]

    assert updated is existing
    # Decrypting with the same key yields the new plaintext, not the old one.
    decrypted = encryptor.decrypt(updated.ciphertext, updated.iv, updated.key_id)
    assert decrypted == new_token
    assert decrypted != old_token
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_credential_missing_raises_lookup_error() -> None:
    session = _mock_session_with_credential(cred=None)
    with pytest.raises(LookupError):
        await credential_repo.update_credential(
            session=session,
            source_id=uuid.uuid4(),
            new_plaintext="any",
        )


# ---------- delete_credential -----------------------------------------------


@pytest.mark.asyncio
async def test_delete_credential_removes_row() -> None:
    """``delete_credential`` must call ``session.delete`` and return ``True``."""
    cred = Credential(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        key_id="any",
        ciphertext="any",
        iv="any",
    )
    session = _mock_session_with_credential(cred=cred)

    deleted = await credential_repo.delete_credential(session=session, source_id=cred.source_id)
    assert deleted is True
    session.delete.assert_awaited_once_with(cred)


@pytest.mark.asyncio
async def test_delete_credential_when_missing_returns_false() -> None:
    """Idempotent delete: no row present -> ``False``, no exception."""
    session = _mock_session_with_credential(cred=None)

    deleted = await credential_repo.delete_credential(session=session, source_id=uuid.uuid4())
    assert deleted is False
    session.delete.assert_not_called()


# ---------- get after delete: implicit round-trip ---------------------------


@pytest.mark.asyncio
async def test_delete_then_get_returns_none() -> None:
    """Round-trip: delete a credential, then get_credential must return ``None``."""
    cred = Credential(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        key_id="any",
        ciphertext="any",
        iv="any",
    )
    session = _mock_session_with_credential(cred=cred)

    # First call: credential present, gets deleted
    deleted = await credential_repo.delete_credential(session=session, source_id=cred.source_id)
    assert deleted is True

    # Second call: chain a fresh "no row" result for the post-delete get
    post_result = MagicMock()
    post_result.scalar_one_or_none.return_value = None
    session.execute.return_value = post_result

    result = await credential_repo.get_credential(session=session, source_id=cred.source_id)
    assert result is None
