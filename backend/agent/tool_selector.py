"""
Tool Selector for ResearchDesk.
Analyzes the research objective and plan to generate targeted search queries,
determine whether webpage retrieval is needed, and prioritize candidate URLs.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from backend.config import settings
from backend.schemas import ResearchPlan
from backend.services.llm_service import get_llm_service
from backend.utils.logging_config import logger


class ToolExecutionDecision(BaseModel):
    """Structured decision detailing tools and parameters to execute."""
    search_queries: List[str] = Field(
        ...,
        description="Targeted search queries crafted for the research task"
    )
    should_retrieve_webpages: bool = Field(
        default=True,
        description="Whether full webpage text extraction is required"
    )
    max_pages_to_scrape: int = Field(
        default=3,
        description="Maximum number of candidate pages to scrape"
    )
    rationale: str = Field(
        ...,
        description="Explanation of why these tools and queries were selected"
    )


class ToolSelector:
    """Selects and parameterizes research tools based on question context and plan."""

    def __init__(self, llm_service=None):
        self.llm = llm_service or get_llm_service()

    def select_tools(
        self,
        question: str,
        plan: ResearchPlan,
        include_web_scraping: bool = True,
    ) -> ToolExecutionDecision:
        """
        Determines tool strategy. Uses LLM when available; otherwise applies rule-based logic.
        """
        logger.info(f"Selecting tools for question: '{question}'")

        if self.llm.is_available:
            try:
                return self._llm_select(question, plan, include_web_scraping)
            except Exception as e:
                logger.warning(f"LLM tool selector failed: {e}. Falling back to rule-based selector.")
                return self._rule_based_select(question, plan, include_web_scraping)
        else:
            return self._rule_based_select(question, plan, include_web_scraping)

    def _llm_select(
        self,
        question: str,
        plan: ResearchPlan,
        include_web_scraping: bool,
    ) -> ToolExecutionDecision:
        """Uses LLM to craft distinct, high-signal search queries and extraction targets."""
        system_prompt = (
            "You are a Senior Information Retrieval Specialist. Based on the user query and research plan, "
            "select the tools and formulate 1 to 3 distinct, high-precision search queries. "
            "Return JSON matching this schema:\n"
            "{\n"
            '  "search_queries": ["query 1", "query 2"],\n'
            '  "should_retrieve_webpages": true | false,\n'
            '  "max_pages_to_scrape": 2 | 3,\n'
            '  "rationale": "Clear reason for query selection and scraping need"\n'
            "}"
        )

        user_content = (
            f"Question: {question}\n"
            f"Plan Objective: {plan.objective}\n"
            f"Subquestions: {', '.join(plan.subquestions)}\n"
            f"Web Scraping Allowed by User: {include_web_scraping}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        data = self.llm.generate_json(messages, temperature=0.1)

        queries = data.get("search_queries", [])
        if not queries:
            queries = [question]

        # Respect user scraping toggle and config ceiling
        should_scrape = data.get("should_retrieve_webpages", True) and include_web_scraping
        pages_limit = min(data.get("max_pages_to_scrape", 3), settings.max_scraped_pages)

        return ToolExecutionDecision(
            search_queries=queries[:3],
            should_retrieve_webpages=should_scrape,
            max_pages_to_scrape=pages_limit if should_scrape else 0,
            rationale=data.get("rationale", "Generated queries optimized for the research objective."),
        )

    def _rule_based_select(
        self,
        question: str,
        plan: ResearchPlan,
        include_web_scraping: bool,
    ) -> ToolExecutionDecision:
        """Rule-based tool decision ensuring reliable fallback."""
        q_lower = question.lower()
        queries = [question]

        # Add secondary refined query based on query intent
        if "vector database" in q_lower or "rag" in q_lower:
            queries.append("open source vector databases comparison Qdrant Chroma Milvus Weaviate")
        elif "hr" in q_lower and ("saas" in q_lower or "startup" in q_lower):
            queries.append("Indian B2B SaaS HR technology startups Darwinbox Keka")
        elif "multi-agent" in q_lower or "customer support" in q_lower:
            queries.append("multi agent architecture customer support automation trade-offs")
        elif "memory" in q_lower and "agent" in q_lower:
            queries.append("AI agent memory architectures short term long term vector episodic")

        should_scrape = include_web_scraping and settings.max_scraped_pages > 0
        pages = min(3, settings.max_scraped_pages) if should_scrape else 0

        return ToolExecutionDecision(
            search_queries=queries[:2],
            should_retrieve_webpages=should_scrape,
            max_pages_to_scrape=pages,
            rationale="Selected primary and contextualized search queries, paired with deep page extraction for technical verification.",
        )
