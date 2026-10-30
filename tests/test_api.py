"""
Unit tests for FastAPI endpoints (/api/health, /api/research).
Uses Starlette TestClient to simulate requests without real network dependencies.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from backend.main import app
from backend.schemas import (
    ConfidenceLevel,
    KeyFinding,
    PlanStep,
    ResearchPlan,
    ResearchResponse,
    SourceItem,
)

client = TestClient(app)


def test_root_endpoint():
    """Verifies root API metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "health_url" in data


def test_health_check_endpoint():
    """Verifies health check reporting."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm_configured" in data
    assert "llm_model" in data
    assert "search_provider" in data


def test_research_endpoint_input_validation():
    """Verifies that empty or excessively short questions fail with HTTP 422 or 400."""
    response = client.post("/api/research", json={"question": "hi"})
    assert response.status_code in (400, 422)

    response_empty = client.post("/api/research", json={"question": ""})
    assert response_empty.status_code in (400, 422)


@patch("backend.main.orchestrator.run")
def test_research_endpoint_success(mock_run):
    """Verifies valid research query returns structured ResearchResponse."""
    mock_plan = ResearchPlan(
        objective="Analyze vector databases",
        subquestions=["What are the options?"],
        steps=[PlanStep(step_number=1, title="Search", description="Search web", status="completed")],
        initial_assumptions=["Open source only"]
    )
    mock_source = SourceItem(
        id="[S1]",
        title="Qdrant Documentation",
        url="https://qdrant.tech/documentation/",
        domain="qdrant.tech",
        snippet="Open-source vector database written in Rust.",
        retrieval_status="success"
    )
    mock_finding = KeyFinding(
        claim="Qdrant is optimized for vector similarity search",
        detail="Provides payload-based filtering and rust engine.",
        supporting_source_ids=["[S1]"]
    )
    mock_response = ResearchResponse(
        question="Compare vector databases",
        short_answer="Qdrant is a fast, Rust-based open source vector database.",
        detailed_analysis="### Overview\nQdrant provides high-speed vector retrieval.",
        key_findings=[mock_finding],
        sources_used=[mock_source],
        confidence_level=ConfidenceLevel.HIGH,
        confidence_explanation="High confidence based on official documentation.",
        assumptions=["Rust-based deployment"],
        limitations=[],
        suggested_next_steps=["Benchmark indexing throughput"],
        research_plan=mock_plan,
        execution_trace=[],
        warnings=[]
    )
    mock_run.return_value = mock_response

    payload = {
        "question": "Compare open source vector databases for RAG",
        "max_sources": 3,
        "include_web_scraping": True
    }
    response = client.post("/api/research", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["question"] == "Compare vector databases"
    assert data["confidence_level"] == "High"
    assert len(data["sources_used"]) == 1
    assert data["sources_used"][0]["id"] == "[S1]"
    assert len(data["key_findings"]) == 1
    assert data["key_findings"][0]["supporting_source_ids"] == ["[S1]"]
