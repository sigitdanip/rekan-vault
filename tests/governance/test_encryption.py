"""
Tests for AES-256-GCM Credential Envelope Encryption & Key Rotation (RV-DEC-P2-0004).
"""

import os

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
