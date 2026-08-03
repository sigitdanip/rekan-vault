"""
Tests for AES-256-GCM Credential Envelope Encryption & Key Rotation (RV-DEC-P2-0004).
"""

import os
import uuid

import pytest

from rekanvault.governance.encryption import CredentialEncryptor, KeyManager


def test_encryption_decryption_roundtrip() -> None:
    raw_key = os.urandom(32)
    km = KeyManager()

    km.keys["test-key-1"] = raw_key
    km.active_key_id = "test-key-1"

    encryptor = CredentialEncryptor(key_manager=km)
    secret = "oauth_refresh_token_secret_12345"

    ciphertext_b64, iv_b64, key_id = encryptor.encrypt(secret)
    assert key_id == "test-key-1"
    assert ciphertext_b64 != secret
    assert iv_b64 != ""

    decrypted = encryptor.decrypt(ciphertext_b64, iv_b64, key_id)
    assert decrypted == secret


def test_key_rotation_decryption_fallback() -> None:
    key_v1 = os.urandom(32)
    key_v2 = os.urandom(32)

    km1 = KeyManager()
    km1.keys["key-v1"] = key_v1
    km1.active_key_id = "key-v1"
    enc1 = CredentialEncryptor(key_manager=km1)

    secret = "super_secret_token"
    c_b64, iv_b64, key_id = enc1.encrypt(secret)
    assert key_id == "key-v1"

    # Rotate active key to key-v2, keep key-v1 in custody
    km2 = KeyManager()
    km2.keys["key-v2"] = key_v2
    km2.keys["key-v1"] = key_v1
    km2.active_key_id = "key-v2"
    enc2 = CredentialEncryptor(key_manager=km2)

    # Old ciphertext encrypted with key-v1 can still be decrypted by enc2
    decrypted = enc2.decrypt(c_b64, iv_b64, "key-v1")
    assert decrypted == secret

    # New encryption will use key-v2
    new_c, new_iv, new_key_id = enc2.encrypt(secret)
    assert new_key_id == "key-v2"


def test_missing_key_raises_key_error() -> None:
    km = KeyManager()
    enc = CredentialEncryptor(key_manager=km)
    with pytest.raises(KeyError):
        enc.decrypt("dummy_c", "dummy_iv", "non_existent_key")


@pytest.mark.asyncio
async def test_reencrypt_credentials_clears_outgoing_key() -> None:
    """P2-T8: Re-encrypt all credential rows off outgoing key before retirement."""
    from unittest.mock import AsyncMock, MagicMock

    from rekanvault.storage.models import Credential

    key_v1 = os.urandom(32)
    key_v2 = os.urandom(32)

    # Setup: key-v2 is active, key-v1 is previous (still in custody)
    km = KeyManager()
    km.keys["key-v2"] = key_v2
    km.keys["key-v1"] = key_v1
    km.active_key_id = "key-v2"
    enc = CredentialEncryptor(key_manager=km)

    # Encrypt once with key-v1 active
    km_v1 = KeyManager()
    km_v1.keys["key-v1"] = key_v1
    km_v1.active_key_id = "key-v1"
    enc_v1 = CredentialEncryptor(key_manager=km_v1)
    old_ciphertext, old_iv, _ = enc_v1.encrypt("my-refresh-token-abc")

    # Simulate stored credential still on old key
    cred = Credential(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        key_id="key-v1",
        ciphertext=old_ciphertext,
        iv=old_iv,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [cred]

    session = AsyncMock()
    session.execute.return_value = mock_result

    # Re-encrypt: should move credential from key-v1 to key-v2
    reencrypted_count = await enc.reencrypt_credentials(session)
    assert reencrypted_count == 1
    assert cred.key_id == "key-v2"

    # Decrypted plaintext should be the original secret
    decrypted = enc.decrypt(cred.ciphertext, cred.iv, "key-v2")
    assert decrypted == "my-refresh-token-abc"


@pytest.mark.asyncio
async def test_no_credentials_to_reencrypt_returns_zero() -> None:
    """P2-T8: When all credentials are already on active key, re-encrypt returns 0."""
    from unittest.mock import AsyncMock, MagicMock

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    session = AsyncMock()
    session.execute.return_value = mock_result

    km = KeyManager()
    km.keys["key-v1"] = os.urandom(32)
    km.active_key_id = "key-v1"
    enc = CredentialEncryptor(key_manager=km)

    count = await enc.reencrypt_credentials(session)
    assert count == 0
