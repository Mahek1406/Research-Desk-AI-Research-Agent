"""
Source Filtering and Normalization Engine for ResearchDesk.
Deduplicates URLs, validates schemes, cleans tracking parameters,
filters noise, ranks by query alignment, and assigns source tokens [S1], [S2].
"""

import re
from typing import Any, Dict, List, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from backend.schemas import RetrievalStatus, SourceItem
from backend.utils.logging_config import logger


class SourceFilter:
    """Filters, normalizes, and packages retrieved external references."""

    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term",
        "utm_content", "fbclid", "gclid", "ref", "source"
    }

    def filter_and_rank(
        self,
        raw_search_results: List[Dict[str, Any]],
        scraped_pages: Dict[str, Dict[str, Any]],
        query: str,
        max_sources: int = 5,
    ) -> List[SourceItem]:
        """
        Processes search hits and scraped pages into a clean, deduplicated, ranked source list.
        """
        logger.info(
            f"Filtering {len(raw_search_results)} search results and {len(scraped_pages)} retrieved pages."
        )

        seen_urls: Set[str] = set()
        seen_domains: Set[str] = set()
        valid_candidates: List[Dict[str, Any]] = []

        query_keywords = set(re.findall(r"\w{3,}", query.lower()))

        for item in raw_search_results:
            raw_url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            snippet = item.get("snippet", "").strip()

            if not raw_url or not title:
                continue

            clean_url = self._normalize_url(raw_url)
            if not clean_url:
                continue

            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            domain = urlparse(clean_url).netloc.lower()

            # Calculate keyword relevance score
            combined_text = f"{title} {snippet}".lower()
            overlap_count = sum(1 for kw in query_keywords if kw in combined_text)
            relevance_score = overlap_count / max(len(query_keywords), 1)

            # Check if this URL has deeply extracted body text
            scraped_data = scraped_pages.get(clean_url) or scraped_pages.get(raw_url)
            extracted_text = None
            retrieval_status = RetrievalStatus.PARTIAL

            if scraped_data:
                if scraped_data.get("status") == "success" and scraped_data.get("extracted_text"):
                    extracted_text = scraped_data["extracted_text"]
                    retrieval_status = RetrievalStatus.SUCCESS
                    # Reward sources with validated deep content
                    relevance_score += 0.5
                elif scraped_data.get("status") == "failed":
                    retrieval_status = RetrievalStatus.FAILED

            valid_candidates.append({
                "title": title,
                "url": clean_url,
                "domain": domain,
                "snippet": snippet,
                "extracted_text": extracted_text,
                "retrieval_status": retrieval_status,
                "relevance_score": relevance_score,
            })

        # Sort primarily by relevance, prioritizing successfully retrieved in-depth pages
        valid_candidates.sort(
            key=lambda x: (
                1 if x["retrieval_status"] == RetrievalStatus.SUCCESS else 0,
                x["relevance_score"]
            ),
            reverse=True,
        )

        # Truncate to desired max sources
        selected_candidates = valid_candidates[:max_sources]

        # Package into structured SourceItem instances with explicit tokens
        final_sources: List[SourceItem] = []
        for idx, c in enumerate(selected_candidates, start=1):
            source_id = f"[S{idx}]"
            final_sources.append(
                SourceItem(
                    id=source_id,
                    title=c["title"],
                    url=c["url"],
                    domain=c["domain"],
                    snippet=c["snippet"],
                    extracted_text=c["extracted_text"],
                    retrieval_status=c["retrieval_status"],
                    relevance_note=f"Keyword relevance overlap: {c['relevance_score']:.2f}",
                )
            )

        logger.info(f"Retained {len(final_sources)} high-signal sources after filtering.")
        return final_sources

    def _normalize_url(self, url: str) -> str:
        """Strips query trackers, normalizes host, and removes fragments."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return ""
            if not parsed.netloc:
                return ""

            # Filter out tracking query parameters
            query_dict = parse_qs(parsed.query, keep_blank_values=False)
            filtered_query = {
                k: v for k, v in query_dict.items() if k.lower() not in self.TRACKING_PARAMS
            }

            clean_query = urlencode(filtered_query, doseq=True)

            normalized = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/") if parsed.path != "/" else "/",
                parsed.params,
                clean_query,
                "",  # remove fragment anchor
            ))
            return normalized
        except Exception:
            return ""
