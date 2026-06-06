"""Tests for the Claude matching engine.

Test cases:
5. Happy path: Match SWE resume against SWE job -> score > 70.
Plus: weight calculation, fallback scores, clamping.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from app.services.matcher import (
    evaluate_match,
    calculate_overall_score,
    _clamp,
    _fallback_scores,
    WEIGHTS,
)
from app.models.schemas import MatchScoreBreakdown


class TestCalculateOverallScore:
    """Tests for the weighted score calculation."""

    def test_perfect_scores(self):
        breakdown = MatchScoreBreakdown(
            skills_score=100,
            experience_score=100,
            title_score=100,
            location_score=100,
        )
        assert calculate_overall_score(breakdown) == 100

    def test_zero_scores(self):
        breakdown = MatchScoreBreakdown(
            skills_score=0,
            experience_score=0,
            title_score=0,
            location_score=0,
        )
        assert calculate_overall_score(breakdown) == 0

    def test_weighted_calculation(self):
        breakdown = MatchScoreBreakdown(
            skills_score=80,
            experience_score=60,
            title_score=70,
            location_score=100,
        )
        expected = round(0.35 * 80 + 0.25 * 60 + 0.25 * 70 + 0.15 * 100)
        assert calculate_overall_score(breakdown) == expected

    def test_weights_sum_to_one(self):
        """Verify that the weights add up to 1.0."""
        assert sum(WEIGHTS.values()) == pytest.approx(1.0)


class TestClamp:
    """Tests for the clamping utility."""

    def test_clamps_high_values(self):
        assert _clamp(150) == 100

    def test_clamps_low_values(self):
        assert _clamp(-10) == 0

    def test_passes_through_valid_values(self):
        assert _clamp(75) == 75

    def test_handles_float(self):
        assert _clamp(85.7) == 85

    def test_handles_invalid_type(self):
        assert _clamp("not a number") == 0


class TestFallbackScores:
    """Tests for fallback score generation."""

    def test_returns_zero_scores(self):
        result = _fallback_scores("Test Job")
        assert result["overall_score"] == 0
        assert result["skills_score"] == 0
        assert result["matching_skills"] == []
        assert "failed" in result["summary"].lower() or "re-evaluated" in result["summary"].lower()


class TestEvaluateMatch:
    """Tests for the full Gemini matching pipeline."""

    @patch("app.services.matcher.requests.post")
    def test_evaluates_good_match(
        self,
        mock_post,
        sample_resume_data,
        sample_job_description,
        mock_gemini_match_response,
    ):
        """Test 5: Match SWE resume against SWE job -> overall score > 70."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_gemini_match_response
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = evaluate_match(
            resume_data=sample_resume_data,
            job_title="Senior Backend Engineer",
            job_description=sample_job_description,
            job_location="Remote (US)",
            location_preference="San Francisco, CA",
        )

        assert result["overall_score"] > 70
        assert result["skills_score"] == 85
        assert result["experience_score"] == 90
        assert "Python" in result["matching_skills"]
        assert len(result["summary"]) > 0

    @patch("app.services.matcher.requests.post")
    def test_returns_fallback_on_invalid_json(
        self,
        mock_post,
        sample_resume_data,
        sample_job_description,
    ):
        """Gemini returns garbage -> fallback scores, no crash."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "I cannot evaluate this match."}
                        ]
                    }
                }
            ]
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = evaluate_match(
            resume_data=sample_resume_data,
            job_title="Random Job",
            job_description=sample_job_description,
        )

        assert result["overall_score"] == 0
        assert "failed" in result["summary"].lower() or "re-evaluated" in result["summary"].lower()

    @patch("app.services.matcher.requests.post")
    def test_returns_fallback_on_api_error(
        self,
        mock_post,
        sample_resume_data,
        sample_job_description,
    ):
        """Gemini API throws exception -> fallback scores, no crash."""
        mock_post.side_effect = Exception("API key invalid")

        result = evaluate_match(
            resume_data=sample_resume_data,
            job_title="Any Job",
            job_description=sample_job_description,
        )

        assert result["overall_score"] == 0

    @patch("app.services.matcher.requests.post")
    def test_clamps_out_of_range_scores(
        self,
        mock_post,
        sample_resume_data,
        sample_job_description,
    ):
        """Gemini returns scores > 100 -> clamped to 100."""
        response_inner = json.dumps({
            "skills_score": 150,
            "experience_score": -10,
            "title_score": 80,
            "location_score": 100,
            "matching_skills": [],
            "missing_skills": [],
            "summary": "Test",
        })
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": response_inner}
                        ]
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = evaluate_match(
            resume_data=sample_resume_data,
            job_title="Test Job",
            job_description=sample_job_description,
        )

        assert result["skills_score"] == 100  # Clamped from 150
        assert result["experience_score"] == 0  # Clamped from -10
