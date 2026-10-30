"""
Integration tests for ResearchOrchestrator and SourceFilter.
Verifies stage transitions, URL deduplication, and execution tracing.
"""

from unittest.mock import MagicMock
import pytest

from backend.agent.source_filter import SourceFilter
from backend.orchestrator import ResearchOrchestrator
from backend.schemas import (
    ConfidenceLevel,
    KeyFinding,
    PlanStep,
    ResearchPlan,
    ResearchRequest,
    ResearchResponse,
    RetrievalStatus,
    SourceItem,
)


def test_source_filter_deduplication_and_tracking_strip():
    """Verifies that query parameters like utm_source are stripped and identical URLs deduplicated."""
    sf = SourceFilter()

    raw_results = [
        {
            "title": "Chroma DB Overview",
            "url": "https://www.trychroma.com/blog/intro?utm_source=twitter&utm_medium=social#overview",
            "snippet": "Chroma is an open source embedding database.",
        },
        {
            "title": "Chroma DB Overview Duplicate",
            "url": "https://www.trychroma.com/blog/intro?ref=hackernews",
            "snippet": "Chroma is an open source embedding database.",
        },
        {
            "title": "Qdrant Vector Engine",
            "url": "https://qdrant.tech",
            "snippet": "Vector search engine and database.",
        },
    ]

    filtered = sf.filter_and_rank(
        raw_search_results=raw_results,
        scraped_pages={},
        query="chroma vector database",
        max_sources=5,
    )

    # The two Chroma URLs point to the same canonical path, so deduplication must yield 2 total sources
    assert len(filtered) == 2
    assert filtered[0].id == "[S1]"
    assert filtered[1].id == "[S2]"

    # Verify tracking parameter removal
    urls = [s.url for s in filtered]
    for u in urls:
        assert "utm_source" not in u
        assert "#overview" not in u


def test_orchestrator_pipeline_flow():
    """Tests the orchestrator pipeline end-to-end with mock tools and verifies execution trace."""
    mock_search = MagicMock()
    mock_search.search.return_value = [
        {"title": "Vector DB A", "url": "https://example.com/a", "snippet": "Feature A details"},
        {"title": "Vector DB B", "url": "https://example.com/b", "snippet": "Feature B details"},
    ]

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {
        "url": "https://example.com/a",
        "status": "success",
        "title": "Vector DB A",
        "extracted_text": "Detailed body content for Vector DB A",
        "domain": "example.com",
    }

    orchestrator = ResearchOrchestrator(
        search_tool=mock_search,
        web_retrieval_tool=mock_retrieval,
    )

    req = ResearchRequest(
        question="Compare Vector DB A vs Vector DB B for enterprise RAG",
        max_sources=3,
        include_web_scraping=True,
    )

    response = orchestrator.run(req)

    # Validations
    assert isinstance(response, ResearchResponse)
    assert response.question == req.question
    assert len(response.sources_used) >= 1
    assert response.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    # Check execution trace
    stages = [step.stage for step in response.execution_trace]
    assert "Analysis & Planning" in stages
    assert "Tool Selection" in stages
    assert "Web Search" in stages
    assert "Source Filtering" in stages
    assert "Answer Synthesis" in stages
    assert "Workflow Complete" in stages

    for step in response.execution_trace:
        assert step.duration_ms is not None or step.status == "started"
        assert step.timestamp is not None
