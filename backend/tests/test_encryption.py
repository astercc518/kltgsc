"""
Tests for app.core.encryption — AES-256-GCM session file encryption.

All tests use temporary files and in-memory data; no external services needed.
"""
import os
import tempfile

import pytest

from app.core.encryption import SessionEncryption, ENCRYPTED_HEADER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_encryption(key: str = "a" * 32) -> SessionEncryption:
    """Create a SessionEncryption instance with a known key."""
    return SessionEncryption(key)


def _write_temp(data: bytes, suffix: str = ".session") -> str:
    """Write *data* to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestSessionEncryptionInit:

    def test_valid_key(self):
        enc = SessionEncryption("f" * 32)
        assert enc is not None

    def test_key_too_short_raises(self):
        with pytest.raises(ValueError, match="at least 32"):
            SessionEncryption("short")

    def test_empty_key_raises(self):
        with pytest.raises(ValueError):
            SessionEncryption("")


# ---------------------------------------------------------------------------
# In-memory encrypt / decrypt roundtrip
# ---------------------------------------------------------------------------

class TestEncryptDecryptRoundtrip:

    def test_roundtrip_small_data(self):
        enc = _make_encryption()
        plaintext = b"hello world"
        ciphertext = enc._encrypt(plaintext)
        result = enc._decrypt(ciphertext)
        assert result == plaintext

    def test_roundtrip_binary_data(self):
        enc = _make_encryption()
        plaintext = os.urandom(4096)
        ciphertext = enc._encrypt(plaintext)
        result = enc._decrypt(ciphertext)
        assert result == plaintext

    def test_roundtrip_empty_data(self):
        enc = _make_encryption()
        plaintext = b""
        ciphertext = enc._encrypt(plaintext)
        result = enc._decrypt(ciphertext)
        assert result == plaintext

    def test_different_encryptions_produce_different_ciphertext(self):
        """Each call generates random salt + nonce, so output must differ."""
        enc = _make_encryption()
        plaintext = b"same data"
        c1 = enc._encrypt(plaintext)
        c2 = enc._encrypt(plaintext)
        assert c1 != c2

    def test_wrong_key_fails(self):
        enc1 = _make_encryption("a" * 32)
        enc2 = _make_encryption("b" * 32)
        ciphertext = enc1._encrypt(b"secret")
        with pytest.raises(Exception):
            enc2._decrypt(ciphertext)


# ---------------------------------------------------------------------------
# File-level encrypt / decrypt
# ---------------------------------------------------------------------------

class TestFileEncryptDecrypt:

    def test_encrypt_file_roundtrip(self):
        enc = _make_encryption()
        plaintext = b"session data here"
        src = _write_temp(plaintext)

        try:
            enc.encrypt_file(src)

            # File should now start with the encrypted header
            with open(src, "rb") as f:
                assert f.read(len(ENCRYPTED_HEADER)) == ENCRYPTED_HEADER

            # Decrypt to a separate output
            fd, dec_path = tempfile.mkstemp(suffix=".dec")
            os.close(fd)
            enc.decrypt_file(src, output_path=dec_path)

            with open(dec_path, "rb") as f:
                assert f.read() == plaintext
            os.unlink(dec_path)
        finally:
            os.unlink(src)

    def test_encrypt_already_encrypted_is_noop(self):
        enc = _make_encryption()
        plaintext = b"data"
        src = _write_temp(plaintext)

        try:
            enc.encrypt_file(src)
            with open(src, "rb") as f:
                first_pass = f.read()

            # Encrypting again should be a no-op
            enc.encrypt_file(src)
            with open(src, "rb") as f:
                second_pass = f.read()

            assert first_pass == second_pass
        finally:
            os.unlink(src)

    def test_decrypt_unencrypted_returns_as_is(self):
        """Decrypting a file without the header returns the file path unchanged."""
        enc = _make_encryption()
        plaintext = b"plain data no header"
        src = _write_temp(plaintext)

        try:
            result_path = enc.decrypt_file(src)
            assert result_path == src  # returned the same path
            with open(result_path, "rb") as f:
                assert f.read() == plaintext
        finally:
            os.unlink(src)

    def test_encrypt_file_to_separate_output(self):
        enc = _make_encryption()
        plaintext = b"keep original"
        src = _write_temp(plaintext)
        fd, out = tempfile.mkstemp(suffix=".enc")
        os.close(fd)

        try:
            enc.encrypt_file(src, output_path=out)

            # Original should be unchanged
            with open(src, "rb") as f:
                assert f.read() == plaintext

            # Output should be encrypted
            with open(out, "rb") as f:
                assert f.read().startswith(ENCRYPTED_HEADER)
        finally:
            os.unlink(src)
            os.unlink(out)


# ---------------------------------------------------------------------------
# Encrypted file detection
# ---------------------------------------------------------------------------

class TestIsEncrypted:

    def test_encrypted_file_detected(self):
        enc = _make_encryption()
        src = _write_temp(b"data")
        try:
            enc.encrypt_file(src)
            assert enc.is_encrypted(src) is True
        finally:
            os.unlink(src)

    def test_plain_file_not_detected(self):
        enc = _make_encryption()
        src = _write_temp(b"just plain text")
        try:
            assert enc.is_encrypted(src) is False
        finally:
            os.unlink(src)

    def test_nonexistent_file_returns_false(self):
        enc = _make_encryption()
        assert enc.is_encrypted("/tmp/nonexistent_file_xyz.session") is False


# ---------------------------------------------------------------------------
# decrypt_to_memory
# ---------------------------------------------------------------------------

class TestDecryptToMemory:

    def test_encrypted_file(self):
        enc = _make_encryption()
        plaintext = b"in-memory test"
        src = _write_temp(plaintext)
        try:
            enc.encrypt_file(src)
            result = enc.decrypt_to_memory(src)
            assert result == plaintext
        finally:
            os.unlink(src)

    def test_unencrypted_file_returns_raw(self):
        enc = _make_encryption()
        plaintext = b"raw bytes"
        src = _write_temp(plaintext)
        try:
            result = enc.decrypt_to_memory(src)
            assert result == plaintext
        finally:
            os.unlink(src)


# ---------------------------------------------------------------------------
# Backward compatibility with old format (no random salt)
# ---------------------------------------------------------------------------

class TestLegacyFormatCompat:
    """
    The old format uses a fixed salt (b"tgsc_session_salt") and stores only
    nonce(12) + ciphertext.  The new _decrypt should handle this transparently.
    """

    def test_old_format_decryption(self):
        enc = _make_encryption()
        plaintext = b"legacy data"

        # Manually produce old-format ciphertext:
        #   nonce(12) + ciphertext  (salt = b"tgsc_session_salt")
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = b"tgsc_session_salt"
        key = enc._derive_key(enc._password, salt)
        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        old_blob = nonce + ciphertext  # 12 + len(ciphertext)

        # _decrypt should handle this (it is < 28 bytes header threshold
        # only when data is very small; for larger data it will try new
        # format first, fail, then fall back to old format)
        result = enc._decrypt(old_blob)
        assert result == plaintext
