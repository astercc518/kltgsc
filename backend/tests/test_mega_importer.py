"""
Tests for MegaImporter — URL validation and Zip Slip detection.

No actual MEGA downloads or archive operations are performed.
We test the static/class methods directly to avoid heavy imports (opentele, etc.).
"""
import os
import re
import pytest


# Import only the regex pattern and static method without triggering
# the full MegaImporter import chain (mega, opentele, etc.)
MEGA_URL_PATTERN = re.compile(r'^https://mega\.nz/(file|folder)/[A-Za-z0-9#!_-]+$')


def _safe_extract_check(members, extract_to: str):
    """Copy of MegaImporter._safe_extract_check for testing without full import."""
    real_extract = os.path.realpath(extract_to)
    for member_name in members:
        target = os.path.realpath(os.path.join(extract_to, member_name))
        if not target.startswith(real_extract + os.sep) and target != real_extract:
            raise ValueError(f"Zip Slip detected: {member_name}")


def _extract_phone(text: str):
    """Copy of MegaImporter._extract_phone for testing."""
    if not text:
        return None
    match = re.search(r'\+?\d{7,15}', text)
    if match:
        return match.group(0)
    return None


# ---------------------------------------------------------------------------
# MEGA URL validation
# ---------------------------------------------------------------------------

class TestMegaUrlValidation:
    """Tests the MEGA_URL_PATTERN regex used to validate download URLs."""

    VALID_URLS = [
        "https://mega.nz/file/AbCdEfGh#12345678",
        "https://mega.nz/folder/XyZaBcDe#some_key",
        "https://mega.nz/file/AAAAAAAA#BBBBBBBB",
        "https://mega.nz/folder/abcdefgh#ijklmnop-qrs",
        "https://mega.nz/file/test1234#key_value-data!here",
    ]

    INVALID_URLS = [
        "",
        "not a url",
        "http://mega.nz/file/abc#123",          # http, not https
        "https://evil.com/file/abc#123",         # wrong domain
        "https://mega.nz/",                      # missing path
        "https://mega.nz/file/",                 # missing id
        "ftp://mega.nz/file/abc#123",            # wrong scheme
        "https://mega.nz/something/abc#123",     # wrong path type (not file/folder)
        "https://mega.nz/file/abc#123; rm -rf /",  # injection attempt
        "https://mega.nz/file/abc#123\nhttp://evil.com",  # newline injection
    ]

    @pytest.mark.parametrize("url", VALID_URLS)
    def test_valid_urls_accepted(self, url):
        assert MEGA_URL_PATTERN.match(url) is not None

    @pytest.mark.parametrize("url", INVALID_URLS)
    def test_invalid_urls_rejected(self, url):
        assert MEGA_URL_PATTERN.match(url) is None


# ---------------------------------------------------------------------------
# Zip Slip protection
# ---------------------------------------------------------------------------

class TestZipSlipDetection:
    """Tests _safe_extract_check against path traversal attacks."""

    def test_safe_members_pass(self, tmp_path):
        members = [
            "session1.session",
            "subdir/session2.session",
            "a/b/c/deep.dat",
        ]
        _safe_extract_check(members, str(tmp_path))

    def test_traversal_detected(self, tmp_path):
        members = ["../../etc/passwd"]
        with pytest.raises(ValueError, match="Zip Slip"):
            _safe_extract_check(members, str(tmp_path))

    def test_absolute_path_detected(self, tmp_path):
        members = ["/etc/shadow"]
        with pytest.raises(ValueError, match="Zip Slip"):
            _safe_extract_check(members, str(tmp_path))

    def test_dot_dot_in_middle(self, tmp_path):
        members = ["a/../../etc/passwd"]
        with pytest.raises(ValueError, match="Zip Slip"):
            _safe_extract_check(members, str(tmp_path))

    def test_mixed_safe_and_unsafe(self, tmp_path):
        """Even one malicious entry should cause rejection."""
        members = [
            "safe_file.txt",
            "../evil.sh",
        ]
        with pytest.raises(ValueError, match="Zip Slip"):
            _safe_extract_check(members, str(tmp_path))

    def test_empty_members_pass(self, tmp_path):
        _safe_extract_check([], str(tmp_path))


# ---------------------------------------------------------------------------
# Phone number extraction
# ---------------------------------------------------------------------------

class TestExtractPhone:

    def test_extract_from_digits(self):
        assert _extract_phone("+1234567890") == "+1234567890"

    def test_extract_without_plus(self):
        assert _extract_phone("1234567890") == "1234567890"

    def test_extract_from_mixed_text(self):
        result = _extract_phone("user_+79123456789_tdata")
        assert result == "+79123456789"

    def test_no_phone_returns_none(self):
        assert _extract_phone("no-digits-here") is None

    def test_empty_string(self):
        assert _extract_phone("") is None

    def test_none_input(self):
        assert _extract_phone(None) is None
