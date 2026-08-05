"""
Credential repository for source connectors (P3).

Wraps the AES-GCM encrypted ``Credential`` model with the four operations a
connector actually needs: store, fetch, update, delete. All plaintext tokens
(Google refresh tokens, Notion API tokens) are encrypted under the active
``KeyManager`` key before reaching the database.

Ponytail: a thin function-per-operation facade rather than a class — there
is exactly one resource type and one set of operations; no need for an
abstraction. The encryption key is created fresh per call so test
``KeyManager`` overrides take effect without shared state.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.governance.encryption import CredentialEncryptor
from rekanvault.storage.models import Credential


def _encryptor() -> CredentialEncryptor:
    return CredentialEncryptor()


async def store_credential(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    plaintext: str,
    key_id: str | None = None,
) -> Credential:
    """Encrypt ``plaintext`` and stage a new ``Credential`` row.

    Args:
        session: Async DB session; the caller commits.
        workspace_id: Owning workspace UUID.
        source_id: Source UUID the credential authenticates.
        plaintext: Secret token to encrypt (refresh token, API key, etc.).
        key_id: Optional override; must match a key already in ``KeyManager``
            custody, otherwise decryption will fail. Defaults to the active key.

    Returns:
        The staged (not yet committed) ``Credential`` row.
    """
    encryptor = _encryptor()
    ciphertext_b64, iv_b64, active_key_id = encryptor.encrypt(plaintext)
    cred = Credential(
        workspace_id=workspace_id,
        source_id=source_id,
        key_id=key_id or active_key_id,
        ciphertext=ciphertext_b64,
        iv=iv_b64,
    )
    session.add(cred)
    return cred


async def get_credential(session: AsyncSession, source_id: uuid.UUID) -> str | None:
    """Fetch and decrypt the most recent credential for ``source_id``.

    Returns ``None`` if no credential exists — callers (e.g. OAuth bootstrap)
    treat that as "needs new login" rather than an error.
    """
    stmt = select(Credential).where(Credential.source_id == source_id).order_by(Credential.updated_at.desc()).limit(1)
    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()
    if cred is None:
        return None
    return _encryptor().decrypt(cred.ciphertext, cred.iv, cred.key_id)


async def update_credential(
    session: AsyncSession,
    source_id: uuid.UUID,
    new_plaintext: str,
) -> Credential:
    """Re-encrypt the existing credential for ``source_id`` with ``new_plaintext``.

    Used for OAuth token refresh — the new access/refresh token replaces the
    old one in place. The row is mutated (ciphertext/iv/key_id/updated_at),
    not duplicated. ``flush()`` so callers see the new values in the same tx.

    Returns the updated row. Raises ``LookupError`` if no credential exists.
    """
    stmt = select(Credential).where(Credential.source_id == source_id).order_by(Credential.updated_at.desc()).limit(1)
    result = await session.execute(stmt)
    cred = result.scalar_one_or_none()
    if cred is None:
        raise LookupError(f"No credential found for source_id={source_id}")
    ciphertext_b64, iv_b64, key_id = _encryptor().encrypt(new_plaintext)
    cred.ciphertext = ciphertext_b64
    cred.iv = iv_b64
    cred.key_id = key_id
    await session.flush()
    return cred


async def delete_credential(session: AsyncSession, source_id: uuid.UUID) -> bool:
    """Remove the credential row for ``source_id``.

    Returns ``True`` if a row was deleted, ``False`` if there was nothing to
    remove. Idempotent — safe to call on disconnect.
    """
    cred = (
        await session.execute(
            select(Credential).where(Credential.source_id == source_id).order_by(Credential.updated_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if cred is None:
        return False
    await session.delete(cred)
    return True
