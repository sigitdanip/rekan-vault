"""
RekanVault AES-GCM Credential Envelope Encryption (RV-DEC-P2-0004)
Provides AES-256-GCM encryption/decryption with key rotation support,
including a mandatory re-encryption step before retiring a previous key.
"""

from __future__ import annotations

import base64
import os
import uuid
from typing import TYPE_CHECKING, Dict, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings

if TYPE_CHECKING:
    from rekanvault.storage.models import Credential


class KeyManager:
    """Manages active and previous AES-GCM keys for zero-downtime rotation."""

    def __init__(self) -> None:
        self.keys: Dict[str, bytes] = {}
        self.active_key_id: str = settings.RV_ACTIVE_CREDENTIAL_KEY_ID

        # Load active key
        if settings.RV_CREDENTIAL_KEY_ACTIVE:
            key_id, raw_b64 = self._parse_key_str(settings.RV_CREDENTIAL_KEY_ACTIVE)
            self.keys[key_id] = raw_b64
            self.active_key_id = key_id

        # Load previous key if provided
        if settings.RV_CREDENTIAL_KEY_PREVIOUS:
            key_id, raw_b64 = self._parse_key_str(settings.RV_CREDENTIAL_KEY_PREVIOUS)
            self.keys[key_id] = raw_b64

        # Fallback/Parse legacy multi-key string if provided
        if settings.RV_CREDENTIAL_ENCRYPTION_KEYS:
            for item in settings.RV_CREDENTIAL_ENCRYPTION_KEYS.split(","):
                if item.strip():
                    key_id, raw_b64 = self._parse_key_str(item.strip())
                    self.keys[key_id] = raw_b64

    @staticmethod
    def _parse_key_str(key_str: str) -> Tuple[str, bytes]:
        if ":" not in key_str:
            raise ValueError("Key specification must be formatted as key_id:base64key")
        key_id, b64_val = key_str.split(":", 1)
        key_bytes = base64.b64decode(b64_val.strip())
        if len(key_bytes) != 32:
            raise ValueError(f"AES-GCM key must be exactly 32 bytes (256 bits), got {len(key_bytes)} bytes")
        return key_id.strip(), key_bytes

    def get_key(self, key_id: str) -> bytes:
        if key_id not in self.keys:
            raise KeyError(f"Encryption key ID '{key_id}' not found in KeyManager custody")
        return self.keys[key_id]

    def get_active_key(self) -> Tuple[str, bytes]:
        if self.active_key_id not in self.keys:
            # If default test key ID missing, generate transient dev key
            transient_bytes = b"0" * 32
            self.keys[self.active_key_id] = transient_bytes
        return self.active_key_id, self.keys[self.active_key_id]


class CredentialEncryptor:
    """Encrypts and decrypts secret strings using AES-256-GCM."""

    def __init__(self, key_manager: KeyManager | None = None) -> None:
        self.key_manager = key_manager or KeyManager()

    def encrypt(self, plaintext: str) -> Tuple[str, str, str]:
        """
        Encrypt plaintext string using active key.
        Returns (ciphertext_b64, iv_b64, key_id).
        """
        key_id, key_bytes = self.key_manager.get_active_key()
        aesgcm = AESGCM(key_bytes)
        iv = os.urandom(12)  # 96-bit IV recommended for GCM
        ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
        return (
            base64.b64encode(ciphertext).decode("ascii"),
            base64.b64encode(iv).decode("ascii"),
            key_id,
        )

    def decrypt(self, ciphertext_b64: str, iv_b64: str, key_id: str) -> str:
        """Decrypt ciphertext using specified key ID."""
        key_bytes = self.key_manager.get_key(key_id)
        aesgcm = AESGCM(key_bytes)
        ciphertext = base64.b64decode(ciphertext_b64.encode("ascii"))
        iv = base64.b64decode(iv_b64.encode("ascii"))
        plaintext_bytes = aesgcm.decrypt(iv, ciphertext, None)
        return plaintext_bytes.decode("utf-8")

    async def encrypt_and_persist(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        plaintext: str,
    ) -> Credential:
        """Encrypt ``plaintext`` and stage a new ``Credential`` row on ``session``.

        The caller owns the transaction — they decide when to ``commit()``.
        Uses the active key from ``KeyManager``. Existing rows for the same
        ``source_id`` are NOT removed here; callers wanting upsert semantics
        should use ``rekanvault.sources.credential_repo`` instead.
        """
        # Local import: avoids a circular import (storage -> governance) and
        # keeps the encryption module's import graph flat for tests.
        from rekanvault.storage.models import Credential

        ciphertext_b64, iv_b64, key_id = self.encrypt(plaintext)
        cred = Credential(
            workspace_id=workspace_id,
            source_id=source_id,
            key_id=key_id,
            ciphertext=ciphertext_b64,
            iv=iv_b64,
        )
        session.add(cred)
        return cred

    async def reencrypt_credentials(self, session: AsyncSession) -> int:
        """
        P2-T8: Re-encrypt every credential row still encrypted under a non-active
        key onto the current active key. Call this BEFORE retiring a previous key
        from RV_CREDENTIAL_KEY_PREVIOUS.

        Returns the number of rows re-encrypted.
        """
        from rekanvault.storage.models import Credential

        active_key_id = self.key_manager.active_key_id
        stmt = select(Credential).where(Credential.key_id != active_key_id)
        result = await session.execute(stmt)
        stale_credentials = result.scalars().all()

        count = 0
        for cred in stale_credentials:
            plaintext = self.decrypt(cred.ciphertext, cred.iv, cred.key_id)
            new_ciphertext, new_iv, new_key_id = self.encrypt(plaintext)
            cred.ciphertext = new_ciphertext
            cred.iv = new_iv
            cred.key_id = new_key_id
            count += 1

        return count
