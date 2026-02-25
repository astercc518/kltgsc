"""
Tests for app.services.mega_importer — URL validation and Zip Slip detection.

No actual MEGA downloads or archive operations are performed.
"""
import os
import pytest

from app.services.mega_importer import MegaImporter


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
        assert MegaImporter.MEGA_URL_PATTERN.match(url) is not None

    @pytest.mark.parametrize("url", INVALID_URLS)
    def test_invalid_urls_rejected(self, url):
        assert MegaImporter.MEGA_URL_PATTERN.match(url) is None


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
        # Should not raise
        MegaImporter._safe_extract_check(members, str(tmp_path))

    def test_traversal_detected(self, tmp_path):
        members = ["../../etc/passwd"]
        with pytest.raises(ValueError, match="Zip Slip"):
            MegaImporter._safe_extract_check(members, str(tmp_path))

    def test_absolute_path_detected(self, tmp_path):
        members = ["/etc/shadow"]
        with pytest.raises(ValueError, match="Zip Slip"):
            MegaImporter._safe_extract_check(members, str(tmp_path))

    def test_dot_dot_in_middle(self, tmp_path):
        members = ["a/../../etc/passwd"]
        with pytest.raises(ValueError, match="Zip Slip"):
            MegaImporter._safe_extract_check(members, str(tmp_path))

    def test_mixed_safe_and_unsafe(self, tmp_path):
        """Even one malicious entry should cause rejection."""
        members = [
            "safe_file.txt",
            "../evil.sh",
        ]
        with pytest.raises(ValueError, match="Zip Slip"):
            MegaImporter._safe_extract_check(members, str(tmp_path))

    def test_empty_members_pass(self, tmp_path):
        MegaImporter._safe_extract_check([], str(tmp_path))


# ---------------------------------------------------------------------------
# Phone number extraction
# ---------------------------------------------------------------------------

class TestExtractPhone:

    def _make_importer(self):
        """Create an importer without actually logging in to MEGA."""
        importer = object.__new__(MegaImporter)
        return importer

    def test_extract_from_digits(self):
        imp = self._make_importer()
        assert imp._extract_phone("+1234567890") == "+1234567890"

    def test_extract_without_plus(self):
        imp = self._make_importer()
        assert imp._extract_phone("1234567890") == "1234567890"

    def test_extract_from_mixed_text(self):
        imp = self._make_importer()
        result = imp._extract_phone("user_+79123456789_tdata")
        assert result == "+79123456789"

    def test_no_phone_returns_none(self):
        imp = self._make_importer()
        assert imp._extract_phone("no-digits-here") is None

    def test_empty_string(self):
        imp = self._make_importer()
        assert imp._extract_phone("") is None

    def test_none_input(self):
        imp = self._make_importer()
        assert imp._extract_phone(None) is None
