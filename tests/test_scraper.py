"""Tests for the Firecrawl scraper service.

Test cases:
4. Edge case: Career page returns no jobs -> empty list, no crash.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.services.scraper import (
    scrape_career_page,
    ScrapingError,
    _is_job_url,
    _extract_title_from_content,
    _extract_location_from_content,
    _compute_content_hash,
)


class TestUrlFiltering:
    """Tests for URL pattern matching."""

    def test_identifies_job_urls(self):
        assert _is_job_url("https://company.com/jobs/123") is True
        assert _is_job_url("https://company.com/careers/swe") is True
        assert _is_job_url("https://company.com/positions/backend") is True

    def test_excludes_non_job_urls(self):
        assert _is_job_url("https://company.com/blog/update") is False
        assert _is_job_url("https://company.com/about") is False
        assert _is_job_url("https://company.com/privacy") is False

    def test_generic_url_is_excluded(self):
        """URLs without job keywords should be excluded."""
        assert _is_job_url("https://company.com/products") is False


class TestContentExtraction:
    """Tests for title and location extraction from markdown."""

    def test_extracts_h1_title(self):
        markdown = "# Senior Backend Engineer\n\nJoin our team..."
        assert _extract_title_from_content(markdown, "https://co.com/jobs/123") == "Senior Backend Engineer"

    def test_falls_back_to_url_slug(self):
        markdown = "No headings here, just body text."
        result = _extract_title_from_content(markdown, "https://co.com/jobs/senior-backend-engineer")
        assert result == "Senior Backend Engineer"

    def test_extracts_location(self):
        markdown = "Location: San Francisco, CA\nType: Full-time"
        result = _extract_location_from_content(markdown)
        assert "San Francisco" in result

    def test_detects_remote(self):
        markdown = "This is a Remote position."
        result = _extract_location_from_content(markdown)
        assert "Remote" in result

    def test_returns_empty_when_no_location(self):
        markdown = "We are hiring great engineers."
        result = _extract_location_from_content(markdown)
        assert result == ""


class TestContentHash:
    """Tests for deduplication hashing."""

    def test_same_content_same_hash(self):
        h1 = _compute_content_hash("Same content")
        h2 = _compute_content_hash("Same content")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = _compute_content_hash("Content A")
        h2 = _compute_content_hash("Content B")
        assert h1 != h2


class TestScrapeCareerPage:
    """Tests for the main scraping function."""

    @patch("app.services.scraper.FirecrawlApp")
    def test_returns_empty_when_no_jobs_found(self, MockFirecrawl):
        """Test 4: Career page with no job URLs -> empty list, no crash."""
        mock_app = MagicMock()
        # map_url returns links that don't match job patterns
        mock_app.map_url.return_value = [
            "https://company.com/about",
            "https://company.com/blog",
            "https://company.com/contact",
        ]
        MockFirecrawl.return_value = mock_app

        result = scrape_career_page("https://company.com/careers")

        assert result == []
        mock_app.scrape_url.assert_not_called()

    @patch("app.services.scraper.FirecrawlApp")
    def test_scrapes_and_returns_jobs(self, MockFirecrawl):
        """Happy path: discover job URLs -> scrape them -> return ScrapedJob list."""
        mock_app = MagicMock()
        mock_app.map_url.return_value = [
            "https://company.com/jobs/swe-123",
            "https://company.com/jobs/pm-456",
        ]
        mock_app.scrape_url.return_value = {
            "markdown": "# Software Engineer\n\nLocation: Remote\n\nWe need a great engineer...",
        }
        MockFirecrawl.return_value = mock_app

        result = scrape_career_page("https://company.com/careers")

        assert len(result) == 2
        assert result[0].title == "Software Engineer"
        assert result[0].url == "https://company.com/jobs/swe-123"

    @patch("app.services.scraper.FirecrawlApp")
    def test_deduplicates_with_existing_hashes(self, MockFirecrawl):
        """Jobs with content hashes already in DB should be skipped."""
        mock_app = MagicMock()
        mock_app.map_url.return_value = ["https://company.com/jobs/swe-123"]

        content = "# Software Engineer\n\nJoin us for great work opportunities."
        mock_app.scrape_url.return_value = {"markdown": content}
        MockFirecrawl.return_value = mock_app

        existing = {_compute_content_hash(content)}
        result = scrape_career_page("https://company.com/careers", existing_hashes=existing)

        assert len(result) == 0

    @patch("app.services.scraper.FirecrawlApp")
    def test_handles_map_url_failure(self, MockFirecrawl):
        """If map_url fails, raise ScrapingError."""
        mock_app = MagicMock()
        mock_app.map_url.side_effect = Exception("API rate limit")
        MockFirecrawl.return_value = mock_app

        with pytest.raises(ScrapingError, match="Could not discover"):
            scrape_career_page("https://company.com/careers")

    @patch("app.services.scraper.FirecrawlApp")
    def test_skips_failed_individual_scrapes(self, MockFirecrawl):
        """Individual scrape failures should be skipped, not crash."""
        mock_app = MagicMock()
        mock_app.map_url.return_value = [
            "https://company.com/jobs/swe-1",
            "https://company.com/jobs/swe-2",
        ]
        # First scrape fails, second succeeds
        mock_app.scrape_url.side_effect = [
            None,
            {"markdown": "# Good Job\n\nLocation: NYC\n\nThis is a valid long enough job description."},
        ]
        MockFirecrawl.return_value = mock_app

        result = scrape_career_page("https://company.com/careers")

        # Only the successful scrape should be in results
        assert len(result) == 1
        assert result[0].title == "Good Job"
