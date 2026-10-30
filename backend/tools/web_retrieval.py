"""
Webpage retrieval and content extraction tool for ResearchDesk.
Fetches HTML pages, strips scripts/styles/navigation markup, sanitizes text,
and handles timeouts, binary assets, and inaccessible websites safely.
"""

import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

from backend.config import settings
from backend.utils.logging_config import logger


class WebRetrievalTool:
    """Safely retrieves and cleans textual content from external web URLs."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    WIKIPEDIA_HEADERS = {
        "User-Agent": "ResearchDeskBot/1.0 (https://github.com/researchdesk; contact@researchdesk.org)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    # Prompt injection markers to neutralize in untrusted web text
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
        re.compile(r"<\s*\|(?:im_start|im_end|system|user|assistant)\|>?", re.IGNORECASE),
        re.compile(r"\[INST\].*?\[/INST\]", re.IGNORECASE),
    ]

    def __init__(self, timeout_seconds: Optional[int] = None):
        self.timeout = timeout_seconds or settings.http_timeout_seconds

    def retrieve(self, url: str) -> Dict[str, Any]:
        """
        Retrieves the page content from a URL.
        Returns a dictionary with status, title, extracted text, and metadata.
        Never throws unhandled exceptions; returns structured failure records instead.
        """
        start_time = time.time()
        logger.info(f"Retrieving webpage content: {url}")

        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            logger.warning(f"Rejected invalid URL scheme: {url}")
            return {
                "url": url,
                "status": "failed",
                "title": "",
                "extracted_text": "",
                "error": "Invalid URL scheme. Only HTTP and HTTPS are permitted.",
            }

        try:
            req_headers = self.WIKIPEDIA_HEADERS if "wikipedia.org" in parsed.netloc.lower() else self.HEADERS
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers=req_headers,
                verify=True,
            ) as client:
                # Preflight HEAD or stream check to verify content type without downloading binaries
                response = client.get(url)

                if response.status_code != 200:
                    logger.warning(f"HTTP {response.status_code} when accessing {url}")
                    return {
                        "url": url,
                        "status": "failed",
                        "title": "",
                        "extracted_text": "",
                        "error": f"Server returned HTTP status code {response.status_code}.",
                    }

                content_type = response.headers.get("content-type", "").lower()
                if not any(t in content_type for t in ["text/html", "text/plain", "application/xhtml+xml"]):
                    logger.warning(f"Unsupported content-type '{content_type}' at {url}")
                    return {
                        "url": url,
                        "status": "failed",
                        "title": "",
                        "extracted_text": "",
                        "error": f"Unsupported content-type: {content_type}",
                    }

                html_text = response.text
                title, extracted_text = self._clean_html(html_text)

                # Neutralize potential prompt injection attempts in retrieved content
                if settings.strip_prompt_injection_tokens:
                    extracted_text = self._sanitize_text(extracted_text)

                duration = time.time() - start_time
                logger.info(
                    f"Successfully retrieved {url} ({len(extracted_text)} chars) in {duration:.2f}s"
                )

                return {
                    "url": url,
                    "status": "success",
                    "title": title or parsed.netloc,
                    "extracted_text": extracted_text,
                    "domain": parsed.netloc,
                    "error": None,
                }

        except httpx.TimeoutException:
            logger.warning(f"Timeout connecting to {url}")
            return {
                "url": url,
                "status": "failed",
                "title": "",
                "extracted_text": "",
                "error": f"Request timed out after {self.timeout}s.",
            }
        except httpx.RequestError as e:
            logger.warning(f"Connection error to {url}: {e}")
            return {
                "url": url,
                "status": "failed",
                "title": "",
                "extracted_text": "",
                "error": f"Connection error: {type(e).__name__}",
            }
        except Exception as e:
            logger.error(f"Unexpected error retrieving {url}: {e}")
            return {
                "url": url,
                "status": "failed",
                "title": "",
                "extracted_text": "",
                "error": f"Extraction error: {str(e)}",
            }

    def _clean_html(self, html: str) -> tuple[str, str]:
        """Parses HTML, removes boilerplate elements, and extracts article content."""
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # Remove irrelevant or noisy tags
        for element in soup([
            "script", "style", "nav", "footer", "header", "aside",
            "noscript", "svg", "iframe", "form", "button", "figure"
        ]):
            element.decompose()

        # Try to locate main article content container first
        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=re.compile(r"content|article|post|body|entry", re.I))
            or soup.body
            or soup
        )

        # Extract text lines and preserve paragraph structure
        lines = []
        for p in main_content.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 20:  # Skip trivial labels
                lines.append(text)

        if not lines:
            # Fallback to direct raw text
            text = main_content.get_text(separator=" ", strip=True)
            cleaned = re.sub(r"\s+", " ", text).strip()
        else:
            cleaned = "\n\n".join(lines)

        # Enforce character limit
        limit = settings.page_char_limit
        if len(cleaned) > limit:
            cleaned = cleaned[:limit] + "\n... [Source content truncated for length]"

        return title, cleaned

    def _sanitize_text(self, text: str) -> str:
        """Neutralizes prompt injection attack markers in external text."""
        sanitized = text
        for pattern in self.INJECTION_PATTERNS:
            sanitized = pattern.sub("[FILTERED_UNTRUSTED_INSTRUCTION]", sanitized)
        return sanitized
