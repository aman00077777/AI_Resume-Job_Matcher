"""Tests for Discord alert formatting and sending."""

from unittest.mock import patch, MagicMock

import pytest

from app.services.discord_alerts import (
    send_match_alert,
    send_scrape_summary,
    _build_score_bar,
)


class TestScoreBar:
    """Tests for the visual score bar builder."""

    def test_full_score(self):
        bar = _build_score_bar(100)
        assert bar == "[==========]"

    def test_zero_score(self):
        bar = _build_score_bar(0)
        assert bar == "[----------]"

    def test_half_score(self):
        bar = _build_score_bar(50)
        assert "=" in bar and "-" in bar


class TestSendMatchAlert:
    """Tests for Discord match alert sending."""

    @patch("app.services.discord_alerts.requests.post")
    def test_sends_alert_successfully(self, mock_post):
        """Successful webhook POST -> returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        result = send_match_alert(
            job_title="Senior Engineer",
            company_name="Stripe",
            overall_score=92,
            skills_score=90,
            experience_score=85,
            title_score=95,
            location_score=100,
            matching_skills=["Python", "FastAPI"],
            missing_skills=["Go"],
            summary="Excellent match for this role.",
            job_url="https://stripe.com/jobs/123",
            job_location="Remote",
            webhook_url="https://discord.com/api/webhooks/test/test",
        )

        assert result is True
        mock_post.assert_called_once()

        # Verify the payload structure
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "embeds" in payload
        embed = payload["embeds"][0]
        assert "Senior Engineer" in embed["title"]
        assert "Stripe" in embed["title"]
        assert embed["color"] == 0x00E676  # Green for 90+

    @patch("app.services.discord_alerts.requests.post")
    def test_handles_webhook_failure(self, mock_post):
        """Non-204 response -> returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        result = send_match_alert(
            job_title="Test",
            company_name="Test",
            overall_score=85,
            skills_score=80,
            experience_score=80,
            title_score=80,
            location_score=80,
            matching_skills=[],
            missing_skills=[],
            summary="Test",
            job_url="https://test.com",
            job_location="Remote",
            webhook_url="https://discord.com/api/webhooks/test/test",
        )

        assert result is False

    def test_skips_when_no_webhook_url(self):
        """Empty webhook URL -> returns False, no HTTP call."""
        result = send_match_alert(
            job_title="Test",
            company_name="Test",
            overall_score=85,
            skills_score=80,
            experience_score=80,
            title_score=80,
            location_score=80,
            matching_skills=[],
            missing_skills=[],
            summary="Test",
            job_url="https://test.com",
            job_location="Remote",
            webhook_url="",
        )

        assert result is False

    @patch("app.services.discord_alerts.requests.post")
    def test_handles_network_error(self, mock_post):
        """Network error -> returns False, no crash."""
        import requests
        mock_post.side_effect = requests.RequestException("Connection refused")

        result = send_match_alert(
            job_title="Test",
            company_name="Test",
            overall_score=85,
            skills_score=80,
            experience_score=80,
            title_score=80,
            location_score=80,
            matching_skills=[],
            missing_skills=[],
            summary="Test",
            job_url="https://test.com",
            job_location="Remote",
            webhook_url="https://discord.com/api/webhooks/test/test",
        )

        assert result is False


class TestSendScrapeSummary:
    """Tests for the scrape summary notification."""

    @patch("app.services.discord_alerts.requests.post")
    def test_sends_summary(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        result = send_scrape_summary(
            webhook_url="https://discord.com/api/webhooks/test/test",
            jobs_found=25,
            new_jobs=10,
            matches_above_threshold=3,
            alerts_sent=3,
            errors=[],
        )

        assert result is True

    @patch("app.services.discord_alerts.requests.post")
    def test_includes_errors_in_summary(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        send_scrape_summary(
            webhook_url="https://discord.com/api/webhooks/test/test",
            jobs_found=5,
            new_jobs=0,
            matches_above_threshold=0,
            alerts_sent=0,
            errors=["Failed to scrape company.com"],
        )

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        description = payload["embeds"][0]["description"]
        assert "Errors" in description
