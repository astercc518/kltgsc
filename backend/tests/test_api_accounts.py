"""
Tests for the /api/v1/accounts endpoints.

Uses the in-memory SQLite session and TestClient from conftest.
External services (Celery, Telegram, etc.) are not invoked; the tests
focus on HTTP status codes, DB mutations, and input validation.
"""
import os
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# List accounts
# ---------------------------------------------------------------------------

class TestGetAccounts:

    def test_empty_list(self, client):
        resp = client.get("/api/v1/accounts/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self, client):
        client.post("/api/v1/accounts/", json={
            "phone_number": "+1000000001",
            "session_string": "",
            "status": "init",
        })
        resp = client.get("/api/v1/accounts/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["phone_number"] == "+1000000001"

    def test_filter_by_status(self, client):
        client.post("/api/v1/accounts/", json={
            "phone_number": "+2000000001",
            "session_string": "",
            "status": "active",
        })
        client.post("/api/v1/accounts/", json={
            "phone_number": "+2000000002",
            "session_string": "",
            "status": "banned",
        })
        resp = client.get("/api/v1/accounts/", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(a["status"] == "active" for a in data)


# ---------------------------------------------------------------------------
# Get single account
# ---------------------------------------------------------------------------

class TestGetAccount:

    def test_get_existing(self, client, sample_account):
        resp = client.get(f"/api/v1/accounts/{sample_account.id}")
        assert resp.status_code == 200
        assert resp.json()["phone_number"] == sample_account.phone_number

    def test_get_not_found(self, client):
        resp = client.get("/api/v1/accounts/999999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Create account
# ---------------------------------------------------------------------------

class TestCreateAccount:

    def test_create_success(self, client):
        resp = client.post("/api/v1/accounts/", json={
            "phone_number": "+3000000001",
            "session_string": "sess",
            "status": "init",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["phone_number"] == "+3000000001"
        assert "id" in data

    def test_create_duplicate_phone_fails(self, client):
        payload = {
            "phone_number": "+3000000002",
            "session_string": "",
            "status": "init",
        }
        client.post("/api/v1/accounts/", json=payload)
        resp = client.post("/api/v1/accounts/", json=payload)
        # SQLite will raise IntegrityError -> 500
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Delete account
# ---------------------------------------------------------------------------

class TestDeleteAccount:

    def test_delete_existing(self, client, sample_account):
        resp = client.delete(f"/api/v1/accounts/{sample_account.id}")
        assert resp.status_code == 200
        # Verify gone
        resp2 = client.get(f"/api/v1/accounts/{sample_account.id}")
        assert resp2.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/v1/accounts/999999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Batch delete
# ---------------------------------------------------------------------------

class TestBatchDelete:

    def test_batch_delete(self, client):
        # Create two accounts
        r1 = client.post("/api/v1/accounts/", json={
            "phone_number": "+4000000001",
            "session_string": "",
            "status": "init",
        })
        r2 = client.post("/api/v1/accounts/", json={
            "phone_number": "+4000000002",
            "session_string": "",
            "status": "init",
        })
        id1 = r1.json()["id"]
        id2 = r2.json()["id"]

        resp = client.post("/api/v1/accounts/batch/delete", json={
            "account_ids": [id1, id2],
        })
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 2

        # Both should be gone
        assert client.get(f"/api/v1/accounts/{id1}").status_code == 404
        assert client.get(f"/api/v1/accounts/{id2}").status_code == 404

    def test_batch_delete_nonexistent_ids(self, client):
        resp = client.post("/api/v1/accounts/batch/delete", json={
            "account_ids": [888888, 999999],
        })
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 0


# ---------------------------------------------------------------------------
# Account count
# ---------------------------------------------------------------------------

class TestGetAccountCount:

    def test_count_empty(self, client):
        resp = client.get("/api/v1/accounts/count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_count_after_create(self, client, sample_account):
        resp = client.get("/api/v1/accounts/count")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1


# ---------------------------------------------------------------------------
# Upload session — path traversal safety
# ---------------------------------------------------------------------------

class TestUploadPathSafety:
    """
    The upload endpoint sanitizes filenames via os.path.basename and
    checks that the resolved path stays within the sessions/ directory.
    """

    @patch("app.api.v1.endpoints.accounts.parse_session_file", return_value=("+5555555555", {}))
    @patch("app.api.v1.endpoints.accounts.auto_assign_proxy")
    @patch("app.api.v1.endpoints.accounts.encrypt_new_session_file", side_effect=Exception("skip"))
    def test_traversal_stripped(self, _enc, _proxy, _parse, client):
        """A filename like '../../etc/passwd' should be stripped to 'passwd'."""
        import io

        content = b"\x00" * 100  # dummy session bytes
        files = {"file": ("../../etc/passwd", io.BytesIO(content), "application/octet-stream")}
        resp = client.post("/api/v1/accounts/upload", files=files)
        # Should succeed — the basename logic strips the traversal
        assert resp.status_code == 200

    @patch("app.api.v1.endpoints.accounts.parse_session_file", return_value=("+6666666666", {}))
    @patch("app.api.v1.endpoints.accounts.auto_assign_proxy")
    @patch("app.api.v1.endpoints.accounts.encrypt_new_session_file", side_effect=Exception("skip"))
    def test_dotfile_rejected(self, _enc, _proxy, _parse, client):
        """Filenames starting with '.' should be rejected."""
        import io

        content = b"\x00" * 100
        files = {"file": (".hidden", io.BytesIO(content), "application/octet-stream")}
        resp = client.post("/api/v1/accounts/upload", files=files)
        assert resp.status_code == 400
