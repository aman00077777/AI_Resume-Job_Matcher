"""Tests for the resume parsing service.

Test cases:
1. Happy path: Parse well-formatted resume text -> structured output.
2. Edge case: Empty/corrupted PDF -> ResumeParsingError.
3. Edge case: Image-only (no text) PDF -> ResumeParsingError.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from app.services.resume_parser import (
    extract_text_from_pdf,
    structure_resume_with_gemini,
    parse_resume,
    ResumeParsingError,
)


class TestExtractTextFromPdf:
    """Tests for PDF text extraction."""

    def test_extracts_text_from_valid_pdf(self, sample_pdf_bytes):
        """Test 1: Happy path — extract text from a valid PDF."""
        text = extract_text_from_pdf(sample_pdf_bytes)
        # The minimal PDF contains "John Doe"
        assert len(text) > 0

    def test_raises_on_empty_bytes(self):
        """Test 2: Edge case — empty bytes should raise ResumeParsingError."""
        with pytest.raises(ResumeParsingError, match="Could not read PDF"):
            extract_text_from_pdf(b"")

    def test_raises_on_corrupted_pdf(self):
        """Test 2b: Edge case — corrupted/non-PDF bytes."""
        with pytest.raises(ResumeParsingError, match="Could not read PDF"):
            extract_text_from_pdf(b"this is not a pdf file at all")

    def test_raises_on_image_only_pdf(self):
        """Test 3: Edge case — PDF with no extractable text.

        We simulate this by creating a mock PdfReader whose pages
        return empty strings.
        """
        with patch("app.services.resume_parser.PdfReader") as MockReader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = ""

            mock_reader = MagicMock()
            mock_reader.pages = [mock_page]
            MockReader.return_value = mock_reader

            with pytest.raises(ResumeParsingError, match="Could not extract any text"):
                extract_text_from_pdf(b"fake-pdf-bytes")


class TestStructureResumeWithGemini:
    """Tests for Gemini-powered resume structuring."""

    @patch("app.services.resume_parser.requests.post")
    def test_parses_valid_response(self, mock_post, sample_resume_text, mock_gemini_resume_response):
        """Gemini returns valid JSON -> ParsedResume with correct fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_gemini_resume_response
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = structure_resume_with_gemini(sample_resume_text)

        assert len(result.skills) == 5
        assert result.experience_years == 6
        assert len(result.education) == 1
        assert result.education[0].institution == "MIT"
        assert "Senior Software Engineer" in result.job_titles

    @patch("app.services.resume_parser.requests.post")
    def test_raises_on_invalid_json(self, mock_post, sample_resume_text):
        """Gemini returns non-JSON text -> ResumeParsingError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "This is not valid JSON at all"}
                        ]
                    }
                }
            ]
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with pytest.raises(ResumeParsingError, match="invalid output"):
            structure_resume_with_gemini(sample_resume_text)

    @patch("app.services.resume_parser.requests.post")
    def test_handles_code_fenced_response(self, mock_post, sample_resume_text, mock_gemini_resume_response):
        """Gemini wraps JSON in code fences -> still parses correctly."""
        inner_json = mock_gemini_resume_response["candidates"][0]["content"]["parts"][0]["text"]
        fenced = f"```json\n{inner_json}\n```"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": fenced}
                        ]
                    }
                }
            ]
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = structure_resume_with_gemini(sample_resume_text)
        assert len(result.skills) > 0


class TestParseResume:
    """Integration tests for the full parse_resume pipeline."""

    @patch("app.services.resume_parser.structure_resume_with_gemini")
    @patch("app.services.resume_parser.extract_text_from_pdf")
    def test_full_pipeline_happy_path(self, mock_extract, mock_structure, sample_pdf_bytes):
        """Full pipeline: PDF -> text -> structured data."""
        from app.models.schemas import ParsedResume

        mock_extract.return_value = "John Doe, Senior Engineer, Python, 5 years"
        mock_structure.return_value = ParsedResume(
            skills=["Python"],
            experience_years=5,
            education=[],
            job_titles=["Senior Engineer"],
            summary="Test summary",
        )

        result = parse_resume(sample_pdf_bytes, "test.pdf")

        assert result["filename"] == "test.pdf"
        assert result["skills"] == ["Python"]
        assert result["experience_years"] == 5
        mock_extract.assert_called_once()
        mock_structure.assert_called_once()

    def test_rejects_empty_pdf(self):
        """Empty PDF bytes -> ResumeParsingError."""
        with pytest.raises(ResumeParsingError):
            parse_resume(b"", "empty.pdf")
