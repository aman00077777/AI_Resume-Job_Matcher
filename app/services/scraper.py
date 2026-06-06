"""Firecrawl-powered career page scraper.

Uses Firecrawl's map_url to discover job listing URLs on a career page,
then scrapes individual listings. Implements content hashing for
deduplication so we never re-process unchanged job postings.
"""

import hashlib
import re
from dataclasses import dataclass, field

from firecrawl import FirecrawlApp
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings


@dataclass
class ScrapedJob:
    """A single job listing scraped from a career page."""

    title: str
    description: str
    location: str
    url: str
    content_hash: str


class ScrapingError(Exception):
    """Raised when scraping fails."""
    pass


# ─── URL filtering patterns ──────────────────────────────────────────────────

JOB_URL_PATTERNS = [
    r"/jobs?/",
    r"/careers?/",
    r"/positions?/",
    r"/openings?/",
    r"/opportunities/",
    r"/roles?/",
    r"/vacancies/",
    r"/apply/",
    r"/job-board/",
    r"/work-with-us/",
]

EXCLUDE_PATTERNS = [
    r"/blog/",
    r"/news/",
    r"/about/",
    r"/privacy",
    r"/terms",
    r"/cookie",
    r"/login",
    r"/signup",
    r"\.pdf$",
    r"\.png$",
    r"\.jpg$",
]


def _is_job_url(url: str) -> bool:
    """Check if a URL looks like a job listing page."""
    url_lower = url.lower()

    # Exclude non-job pages
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, url_lower):
            return False

    # Must match at least one job pattern
    for pattern in JOB_URL_PATTERNS:
        if re.search(pattern, url_lower):
            return True

    return False


def _extract_title_from_content(markdown: str, url: str) -> str:
    """Best-effort extraction of the job title from page content.

    Looks for the first H1 heading in the markdown. Falls back to
    extracting from the URL slug.
    """
    # Try H1 heading
    h1_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    # Try H2 heading
    h2_match = re.search(r"^##\s+(.+)$", markdown, re.MULTILINE)
    if h2_match:
        return h2_match.group(1).strip()

    # Fallback: extract from URL slug
    slug = url.rstrip("/").split("/")[-1]
    title = slug.replace("-", " ").replace("_", " ").title()
    return title if title else "Untitled Position"


def _extract_location_from_content(markdown: str) -> str:
    """Best-effort extraction of location from job content."""
    location_patterns = [
        r"(?:Location|Office|Based in|Where)[:\s]+([^\n]+)",
        r"(?:Remote|Hybrid|On-?site)[^\n]*",
    ]

    for pattern in location_patterns:
        match = re.search(pattern, markdown, re.IGNORECASE)
        if match:
            return match.group(0).strip()[:200]

    return ""


def _compute_content_hash(content: str) -> str:
    """Generate MD5 hash of content for deduplication."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
)
def _scrape_single_url(app: FirecrawlApp, url: str) -> dict | None:
    """Scrape a single URL with retry logic."""
    try:
        result = app.scrape_url(url, params={
            "formats": ["markdown"],
            "onlyMainContent": True,
        })
        return result
    except Exception as e:
        logger.warning(f"Scrape failed for {url}: {e}")
        return None


def scrape_career_page(
    career_url: str,
    existing_hashes: set[str] | None = None,
) -> list[ScrapedJob]:
    """Scrape all job listings from a company career page.

    Workflow:
    1. Use Firecrawl's map_url to discover all links on the career page.
    2. Filter for URLs that look like individual job postings.
    3. Scrape each job posting page for its content.
    4. Deduplicate against existing content hashes.

    Args:
        career_url: The root career/jobs page URL.
        existing_hashes: Set of content_hash values already in the DB.
            Jobs matching these hashes are skipped.

    Returns:
        List of ScrapedJob objects for new/changed listings.
    """
    settings = get_settings()
    if existing_hashes is None:
        existing_hashes = set()

    app = FirecrawlApp(api_key=settings.firecrawl_api_key)

    # Step 1: Discover all URLs on the career page
    logger.info(f"Mapping career page: {career_url}")
    try:
        map_result = app.map_url(career_url)

        if isinstance(map_result, dict):
            all_urls = map_result.get("links", [])
        elif isinstance(map_result, list):
            all_urls = map_result
        else:
            all_urls = []

    except Exception as e:
        logger.error(f"Failed to map career page {career_url}: {e}")
        raise ScrapingError(f"Could not discover job URLs from {career_url}: {e}")

    # Step 2: Filter for job-related URLs
    job_urls = [url for url in all_urls if isinstance(url, str) and _is_job_url(url)]
    logger.info(f"Found {len(job_urls)} job URLs out of {len(all_urls)} total links")

    if not job_urls:
        logger.info(f"No job URLs found on {career_url}")
        return []

    # Cap to configured limit
    max_jobs = settings.scrape_max_jobs_per_source
    if len(job_urls) > max_jobs:
        logger.info(f"Capping from {len(job_urls)} to {max_jobs} job URLs")
        job_urls = job_urls[:max_jobs]

    # Step 3: Scrape each job posting
    jobs: list[ScrapedJob] = []

    for url in job_urls:
        result = _scrape_single_url(app, url)
        if result is None:
            continue

        markdown = result.get("markdown", "")
        if not markdown or len(markdown.strip()) < 50:
            logger.debug(f"Skipping {url}: content too short")
            continue

        # Step 4: Deduplicate
        content_hash = _compute_content_hash(markdown)
        if content_hash in existing_hashes:
            logger.debug(f"Skipping {url}: content unchanged (hash match)")
            continue

        title = _extract_title_from_content(markdown, url)
        location = _extract_location_from_content(markdown)

        jobs.append(ScrapedJob(
            title=title,
            description=markdown[:10000],  # Cap description size
            location=location,
            url=url,
            content_hash=content_hash,
        ))

    logger.info(f"Scraped {len(jobs)} new job listings from {career_url}")
    return jobs
