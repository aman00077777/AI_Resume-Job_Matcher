"""Tests for FastAPI endpoints.

Tests auth flow, resume upload, and source management endpoints
with mocked Supabase client.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestHealthCheck:
    """Test the health check endpoint."""

    def test_health_returns_200(self, api_client):
        client, _ = api_client
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_returns_api_info(self, api_client):
        client, _ = api_client
        response = client.get("/")
        assert response.status_code == 200
        assert "name" in response.json()


class TestAuthFlow:
    """Test authentication behavior."""

    def test_protected_endpoint_without_token(self, api_client):
        """Accessing protected endpoint without auth -> 401."""
        client, _ = api_client
        response = client.get("/api/sources")
        assert response.status_code == 401

    def test_protected_endpoint_with_invalid_token(self, api_client):
        """Invalid token -> 401."""
        client, mock_db = api_client
        mock_db.auth.get_user.side_effect = Exception("Invalid token")

        response = client.get(
            "/api/sources",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_protected_endpoint_with_service_key(self, api_client):
        """Service API key grants access."""
        client, mock_db = api_client

        # Mock the sources query
        mock_result = MagicMock()
        mock_result.data = []
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

        response = client.get(
            "/api/sources",
            headers={"Authorization": "Bearer test-service-api-key"},
        )
        # Service key works for get_current_user but require_user rejects it
        assert response.status_code == 403


class TestSourceEndpoints:
    """Test company source CRUD endpoints."""

    def test_add_source(self, api_client):
        """POST /api/sources -> 201."""
        client, mock_db = api_client

        # Mock duplicate check
        mock_existing = MagicMock()
        mock_existing.data = []

        # Mock insert
        mock_insert = MagicMock()
        mock_insert.data = [{
            "id": "src-1",
            "user_id": "test-user-id",
            "company_name": "Stripe",
            "career_url": "https://stripe.com/jobs",
            "is_active": True,
            "last_scraped_at": None,
            "created_at": "2025-01-01T00:00:00Z",
        }]

        table_mock = MagicMock()
        # Chain for duplicate check
        table_mock.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_existing
        # Chain for insert
        table_mock.insert.return_value.execute.return_value = mock_insert

        mock_db.table.return_value = table_mock

        response = client.post(
            "/api/sources",
            headers={"Authorization": "Bearer test-token"},
            json={
                "company_name": "Stripe",
                "career_url": "https://stripe.com/jobs",
            },
        )

        assert response.status_code == 201
        assert response.json()["company_name"] == "Stripe"

    def test_list_sources(self, api_client):
        """GET /api/sources -> 200 with list."""
        client, mock_db = api_client

        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "src-1",
                "user_id": "test-user-id",
                "company_name": "Stripe",
                "career_url": "https://stripe.com/jobs",
                "is_active": True,
                "last_scraped_at": None,
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]

        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

        response = client.get(
            "/api/sources",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["company_name"] == "Stripe"


class TestResumeEndpoints:
    """Test resume upload endpoints."""

    def test_rejects_non_pdf(self, api_client):
        """Uploading a non-PDF file -> 400."""
        client, _ = api_client

        response = client.post(
            "/api/resumes/upload",
            headers={"Authorization": "Bearer test-token"},
            files={"file": ("resume.txt", b"not a pdf", "text/plain")},
        )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]
