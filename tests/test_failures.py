"""
Failure handling and resilience tests for ResearchDesk.
Tests empty search results, unreachable webpages, and insufficient evidence behavior.
"""

from unittest.mock import MagicMock
import pytest

from backend.orchestrator import ResearchOrchestrator
from backend.schemas import ConfidenceLevel, ResearchRequest


def test_zero_search_results_insufficient_evidence():
    """
    Verifies that when search returns zero results, the agent returns an explicit
    insufficient-evidence report with Low confidence and zero fabricated citations.
    """
    mock_search = MagicMock()
    mock_search.search.return_value = []

    orchestrator = ResearchOrchestrator(search_tool=mock_search)

    req = ResearchRequest(
        question="Query that yields absolutely no external results",
        max_sources=5,
        include_web_scraping=True,
    )

    response = orchestrator.run(req)

    assert response.confidence_level == ConfidenceLevel.LOW
    assert len(response.sources_used) == 0
    assert len(response.key_findings) == 0
    assert "insufficient" in response.short_answer.lower()
    assert any("no usable external sources" in w.lower() for w in response.warnings)


def test_partial_web_retrieval_failure_does_not_crash():
    """
    Verifies that when individual webpages fail (HTTP 500 / timeout),
    the orchestrator continues processing surviving sources without failing.
    """
    mock_search = MagicMock()
    mock_search.search.return_value = [
        {"title": "Broken Page", "url": "https://broken.example.com", "snippet": "Snippet A"},
        {"title": "Healthy Page", "url": "https://healthy.example.com", "snippet": "Snippet B"},
    ]

    mock_retrieval = MagicMock()
    # First URL fails, second succeeds
    def mock_retrieve_side_effect(url):
        if "broken" in url:
            return {
                "url": url,
                "status": "failed",
                "error": "Server connection timeout after 15s",
                "extracted_text": "",
                "title": "",
            }
        return {
            "url": url,
            "status": "success",
            "title": "Healthy Page Title",
            "extracted_text": "Detailed healthy page content.",
            "domain": "healthy.example.com",
        }

    mock_retrieval.retrieve.side_effect = mock_retrieve_side_effect

    orchestrator = ResearchOrchestrator(
        search_tool=mock_search,
        web_retrieval_tool=mock_retrieval,
    )

    req = ResearchRequest(
        question="Test query with partial scraping failure",
        max_sources=5,
        include_web_scraping=True,
    )

    response = orchestrator.run(req)

    # Workflow must succeed despite partial failure
    assert len(response.sources_used) >= 1
    # Check that healthy source was incorporated
    domains = [s.domain for s in response.sources_used]
    assert "healthy.example.com" in domains
