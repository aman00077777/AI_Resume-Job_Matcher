"""Resume PDF parsing service.

Extracts raw text from PDF files using PyPDF2, then uses Claude to
structure the text into skills, experience, education, and job titles.
"""

import json
from io import BytesIO

from PyPDF2 import PdfReader
import requests
from loguru import logger

from app.config import get_settings
from app.models.schemas import ParsedResume, EducationEntry


class ResumeParsingError(Exception):
    """Raised when resume parsing fails."""
    pass


# ─── Gemini prompt for structuring resume text ───────────────────────────────

RESUME_PARSE_PROMPT = """You are an expert resume parser. Extract structured information from the following resume text.

Analyze the text carefully and return a JSON object with these exact fields:

- "skills": A list of all technical and soft skills mentioned (e.g., "Python", "Machine Learning", "Leadership"). Extract every skill you can identify.
- "experience_years": Estimated total years of professional experience as an integer. Calculate from work history dates if available, otherwise estimate from context.
- "education": A list of education entries, each with "degree", "institution", and "year" (graduation year as string, or null if unknown).
- "job_titles": A list of job titles the person has held, ordered from most recent to oldest.
- "summary": A concise 2-sentence professional summary of this candidate.

Return ONLY valid JSON.

Resume text:
{resume_text}"""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text content from a PDF file.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        Concatenated text from all pages.

    Raises:
        ResumeParsingError: If the PDF cannot be read or contains no text.
    """
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as e:
        logger.error(f"Failed to read PDF: {e}")
        raise ResumeParsingError(f"Could not read PDF file: {e}")

    if len(reader.pages) == 0:
        raise ResumeParsingError("PDF has no pages.")

    text_parts = []
    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        except Exception as e:
            logger.warning(f"Failed to extract text from page {i + 1}: {e}")

    full_text = "\n".join(text_parts).strip()

    if not full_text:
        raise ResumeParsingError(
            "Could not extract any text from the PDF. "
            "The file may be image-based (scanned). "
            "Please upload a text-based PDF."
        )

    return full_text


def structure_resume_with_gemini(raw_text: str) -> ParsedResume:
    """Use Gemini to parse raw resume text into structured fields.

    Args:
        raw_text: Plain text extracted from the resume PDF.

    Returns:
        A ParsedResume with skills, experience, education, etc.

    Raises:
        ResumeParsingError: If Gemini returns unparseable output.
    """
    settings = get_settings()
    api_key = settings.gemini_api_key

    prompt = RESUME_PARSE_PROMPT.format(resume_text=raw_text[:15000])  # Cap to avoid token limits

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            try:
                err_data = response.json()
                msg = err_data.get("error", {}).get("message", response.text)
            except Exception:
                msg = response.text
            raise ResumeParsingError(f"Gemini API error (HTTP {response.status_code}): {msg}")
            
        response_json = response.json()

        response_text = response_json["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Strip markdown code fences if Gemini added them despite instructions
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        data = json.loads(response_text)

        # Build education entries
        education = []
        for edu in data.get("education", []):
            if isinstance(edu, dict):
                education.append(EducationEntry(
                    degree=edu.get("degree", ""),
                    institution=edu.get("institution", ""),
                    year=edu.get("year"),
                ))

        return ParsedResume(
            skills=data.get("skills", []),
            experience_years=int(data.get("experience_years", 0)),
            education=education,
            job_titles=data.get("job_titles", []),
            summary=data.get("summary", ""),
        )

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}")
        raise ResumeParsingError("Failed to parse resume — AI returned invalid output. Please try again.")
    except Exception as e:
        logger.error(f"Gemini API error during resume parsing: {e}")
        raise ResumeParsingError(f"Resume parsing failed: {e}")


def parse_resume(pdf_bytes: bytes, filename: str = "resume.pdf") -> dict:
    """Full pipeline: PDF bytes -> extracted text -> structured resume data.

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF.
        filename: Original filename for logging.

    Returns:
        Dictionary with raw_text and all parsed fields, ready for DB insert.
    """
    logger.info(f"Parsing resume: {filename} ({len(pdf_bytes)} bytes)")

    raw_text = extract_text_from_pdf(pdf_bytes)
    logger.info(f"Extracted {len(raw_text)} chars from {filename}")

    parsed = structure_resume_with_gemini(raw_text)
    logger.info(f"Parsed resume: {len(parsed.skills)} skills, {parsed.experience_years} years exp")

    return {
        "filename": filename,
        "raw_text": raw_text,
        "skills": parsed.skills,
        "experience_years": parsed.experience_years,
        "education": [edu.model_dump() for edu in parsed.education],
        "job_titles": parsed.job_titles,
        "summary": parsed.summary,
    }
