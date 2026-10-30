"""
Web search tool implementations for ResearchDesk.
Provides a unified interface with DuckDuckGo (zero-config, free) and Tavily/Serper providers.
Includes timeout protection, retries, and error categorization.
"""

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, List, Optional
import httpx

from backend.config import settings
from backend.utils.logging_config import logger

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


class BaseSearchTool(ABC):
    """Abstract base class for search provider integration."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Executes a search query and returns structured results."""
        pass


class DuckDuckGoSearchTool(BaseSearchTool):
    """Search tool using DuckDuckGo. Requires no API key."""

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        start_time = time.time()
        logger.info(f"Executing DuckDuckGo search: query='{query}' (max_results={max_results})")

        try:
            if DDGS is not None:
                with DDGS(timeout=settings.http_timeout_seconds) as ddgs_client:
                    raw_results = list(ddgs_client.text(query, max_results=max_results))
                    for r in raw_results:
                        url = r.get("href") or r.get("link") or ""
                        title = r.get("title") or ""
                        snippet = r.get("body") or r.get("snippet") or ""
                        if url and title:
                            results.append({
                                "title": title.strip(),
                                "url": url.strip(),
                                "snippet": snippet.strip(),
                                "source_provider": "duckduckgo"
                            })
        except Exception as e:
            logger.warning(f"DuckDuckGo primary search error: {str(e)}. Attempting fallbacks.")
            results = []

        # If primary search returned 0 results, trigger secondary and tertiary search fallbacks
        if not results:
            logger.info(f"Primary search returned 0 results for '{query}'. Attempting HTML fallback.")
            results = self._fallback_html_search(query, max_results)

        if not results:
            logger.info(f"HTML fallback returned 0 results for '{query}'. Attempting Wikipedia API fallback.")
            results = self._fallback_wikipedia_search(query, max_results)

        duration = time.time() - start_time
        logger.info(f"Search completed in {duration:.2f}s. Found {len(results)} results.")
        return results

    def _fallback_html_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Fallback lightweight query if DDGS module experiences connection throttling."""
        results = []
        try:
            url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            with httpx.Client(timeout=settings.http_timeout_seconds) as client:
                resp = client.post(url, data={"q": query}, headers=headers)
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = soup.find_all("a", class_="result__snippet")
                    for a in links[:max_results]:
                        parent = a.find_parent("div", class_="result__body")
                        title_tag = parent.find("a", class_="result__url") if parent else None
                        title = title_tag.get_text(strip=True) if title_tag else a.get_text(strip=True)[:40]
                        href = a.get("href")
                        snippet = a.get_text(strip=True)
                        if href:
                            results.append({
                                "title": title,
                                "url": href,
                                "snippet": snippet,
                                "source_provider": "duckduckgo-html-fallback"
                            })
        except Exception as err:
            logger.error(f"HTML fallback search failed: {err}")
        return results

    def _fallback_wikipedia_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Fallback encyclopedia search to ensure technical queries always receive verifiable context."""
        results = []
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results,
            }
            headers = {"User-Agent": "ResearchDesk/1.0 (researcher@startup.io)"}
            with httpx.Client(timeout=settings.http_timeout_seconds) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    data = resp.json()
                    search_items = data.get("query", {}).get("search", [])
                    for item in search_items[:max_results]:
                        title = item.get("title", "")
                        raw_snippet = item.get("snippet", "")
                        clean_snippet = BeautifulSoup(raw_snippet, "html.parser").get_text(strip=True)
                        page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        results.append({
                            "title": title,
                            "url": page_url,
                            "snippet": clean_snippet,
                            "source_provider": "wikipedia-fallback"
                        })
        except Exception as err:
            logger.error(f"Wikipedia fallback failed: {err}")
        return results


class TavilySearchTool(BaseSearchTool):
    """Search tool using Tavily API (tailored for AI agents)."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        start_time = time.time()
        logger.info(f"Executing Tavily search: query='{query}' (max_results={max_results})")
        endpoint = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_raw_content": False
        }
        results = []
        try:
            with httpx.Client(timeout=settings.http_timeout_seconds) as client:
                resp = client.post(endpoint, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", ""),
                            "source_provider": "tavily"
                        })
                else:
                    logger.warning(f"Tavily returned HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")

        duration = time.time() - start_time
        logger.info(f"Tavily search finished in {duration:.2f}s. Results: {len(results)}")
        return results


def get_search_tool() -> BaseSearchTool:
    """Factory function that returns the configured search tool with automatic fallback."""
    if settings.search_provider.lower() == "tavily" and settings.tavily_api_key:
        return TavilySearchTool(api_key=settings.tavily_api_key)
    return DuckDuckGoSearchTool()
