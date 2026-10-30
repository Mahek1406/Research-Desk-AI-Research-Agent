"""
Research Orchestrator for ResearchDesk.
Coordinates the end-to-end agentic workflow: planning, tool selection,
search execution, web scraping, source filtering, synthesis, and tracing.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from backend.agent.planner import QuestionPlanner
from backend.agent.source_filter import SourceFilter
from backend.agent.synthesizer import AnswerSynthesizer
from backend.agent.tool_selector import ToolSelector
from backend.schemas import (
    ExecutionTraceStep,
    ResearchRequest,
    ResearchResponse,
)
from backend.tools.web_retrieval import WebRetrievalTool
from backend.tools.web_search import get_search_tool
from backend.utils.logging_config import logger


class ResearchOrchestrator:
    """Explicit sequential coordinator for research execution."""

    def __init__(
        self,
        planner: Optional[QuestionPlanner] = None,
        tool_selector: Optional[ToolSelector] = None,
        source_filter: Optional[SourceFilter] = None,
        synthesizer: Optional[AnswerSynthesizer] = None,
        search_tool=None,
        web_retrieval_tool=None,
    ):
        self.planner = planner or QuestionPlanner()
        self.tool_selector = tool_selector or ToolSelector()
        self.source_filter = source_filter or SourceFilter()
        self.synthesizer = synthesizer or AnswerSynthesizer()
        self.search_tool = search_tool or get_search_tool()
        self.retrieval_tool = web_retrieval_tool or WebRetrievalTool()

    def run(self, request: ResearchRequest) -> ResearchResponse:
        """
        Executes the entire research workflow synchronously and returns
        a fully validated ResearchResponse with an audit execution trace.
        """
        workflow_start = time.time()
        question = request.question.strip()
        logger.info(f"Starting research workflow for question: '{question}'")

        trace: List[ExecutionTraceStep] = []
        warnings: List[str] = []

        def record_trace(stage: str, message: str, duration_ms: Optional[float] = None, status: str = "completed"):
            trace.append(
                ExecutionTraceStep(
                    stage=stage,
                    status=status,
                    message=message,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
                )
            )

        # STAGE 1: Question Analysis & Planning
        stage1_start = time.time()
        record_trace("Analysis & Planning", "Analyzing research question and structuring plan...", status="started")
        try:
            plan = self.planner.plan(question)
            stage1_dur = (time.time() - stage1_start) * 1000
            record_trace(
                "Analysis & Planning",
                f"Generated plan with {len(plan.steps)} steps and {len(plan.subquestions)} subquestions.",
                duration_ms=stage1_dur,
            )
        except Exception as e:
            stage1_dur = (time.time() - stage1_start) * 1000
            logger.error(f"Planning failed: {e}")
            warnings.append(f"Planning encounter warning: {e}")
            record_trace("Analysis & Planning", f"Fallback plan generated: {e}", duration_ms=stage1_dur, status="warning")
            plan = self.planner._heuristic_plan(question)

        # STAGE 2: Tool Selection
        stage2_start = time.time()
        record_trace("Tool Selection", "Formulating optimal search queries and extraction targets...", status="started")
        try:
            decision = self.tool_selector.select_tools(
                question=question,
                plan=plan,
                include_web_scraping=request.include_web_scraping,
            )
            stage2_dur = (time.time() - stage2_start) * 1000
            record_trace(
                "Tool Selection",
                f"Selected {len(decision.search_queries)} search queries. Web scraping enabled: {decision.should_retrieve_webpages}.",
                duration_ms=stage2_dur,
            )
        except Exception as e:
            stage2_dur = (time.time() - stage2_start) * 1000
            logger.error(f"Tool selection failed: {e}")
            decision = self.tool_selector._rule_based_select(question, plan, request.include_web_scraping)
            record_trace("Tool Selection", f"Applied default tool selection: {e}", duration_ms=stage2_dur, status="warning")

        # Mark Step 1 in plan as completed
        if plan.steps:
            plan.steps[0].status = "completed"

        # STAGE 3: Tool Execution - Web Search
        stage3_start = time.time()
        record_trace("Web Search", "Executing queries across external web search engine...", status="started")
        raw_search_results: List[Dict[str, Any]] = []

        for q in decision.search_queries:
            try:
                hits = self.search_tool.search(q, max_results=request.max_sources)
                raw_search_results.extend(hits)
            except Exception as e:
                logger.error(f"Search query '{q}' failed: {e}")
                warnings.append(f"Search query '{q}' encountered an error.")

        stage3_dur = (time.time() - stage3_start) * 1000
        record_trace(
            "Web Search",
            f"Retrieved {len(raw_search_results)} search hits across {len(decision.search_queries)} queries.",
            duration_ms=stage3_dur,
        )

        if len(plan.steps) > 1:
            plan.steps[1].status = "completed"

        # STAGE 4: Tool Execution - Deep Webpage Retrieval
        stage4_start = time.time()
        scraped_pages: Dict[str, Dict[str, Any]] = {}

        if decision.should_retrieve_webpages and raw_search_results:
            record_trace("Web Retrieval", "Scraping full text content from top candidate pages...", status="started")
            # Select unique URLs to scrape
            candidate_urls: List[str] = []
            seen_hosts = set()
            for r in raw_search_results:
                u = r.get("url", "")
                host = urlparse(u).netloc
                if u and host and host not in seen_hosts:
                    candidate_urls.append(u)
                    seen_hosts.add(host)
                if len(candidate_urls) >= decision.max_pages_to_scrape:
                    break

            for u in candidate_urls:
                try:
                    result = self.retrieval_tool.retrieve(u)
                    scraped_pages[u] = result
                except Exception as e:
                    logger.warning(f"Failed scraping {u}: {e}")
                    scraped_pages[u] = {
                        "url": u,
                        "status": "failed",
                        "error": str(e),
                        "extracted_text": "",
                        "title": "",
                    }

            stage4_dur = (time.time() - stage4_start) * 1000
            success_count = sum(1 for p in scraped_pages.values() if p.get("status") == "success")
            record_trace(
                "Web Retrieval",
                f"Successfully parsed {success_count}/{len(candidate_urls)} target webpages.",
                duration_ms=stage4_dur,
            )
        else:
            stage4_dur = (time.time() - stage4_start) * 1000
            record_trace("Web Retrieval", "Web scraping skipped or no candidates available.", duration_ms=stage4_dur)

        # STAGE 5: Source Filtering & Deduplication
        stage5_start = time.time()
        record_trace("Source Filtering", "Normalizing URLs, filtering noise, and ranking evidence...", status="started")
        filtered_sources = self.source_filter.filter_and_rank(
            raw_search_results=raw_search_results,
            scraped_pages=scraped_pages,
            query=question,
            max_sources=request.max_sources,
        )
        stage5_dur = (time.time() - stage5_start) * 1000
        record_trace(
            "Source Filtering",
            f"Retained {len(filtered_sources)} verified sources tagged with citations [S1]..[S{len(filtered_sources)}].",
            duration_ms=stage5_dur,
        )

        if len(plan.steps) > 2:
            plan.steps[2].status = "completed"

        # STAGE 6: Source-Grounded Answer Synthesis
        stage6_start = time.time()
        record_trace("Answer Synthesis", "Generating evidence-grounded analysis and key findings...", status="started")
        response = self.synthesizer.synthesize(
            question=question,
            plan=plan,
            sources=filtered_sources,
            warnings=warnings,
        )
        stage6_dur = (time.time() - stage6_start) * 1000
        record_trace(
            "Answer Synthesis",
            f"Answer synthesized with confidence level '{response.confidence_level.value}'.",
            duration_ms=stage6_dur,
        )

        # Mark all steps completed in plan
        for step in plan.steps:
            if step.status == "pending":
                step.status = "completed"

        # STAGE 7: Schema and Output Validation
        total_time_ms = (time.time() - workflow_start) * 1000
        record_trace(
            "Workflow Complete",
            f"Research workflow concluded successfully in {total_time_ms/1000:.2f} seconds.",
            duration_ms=total_time_ms,
        )

        response.execution_trace = trace
        logger.info(f"Research completed in {total_time_ms/1000:.2f}s. Confidence: {response.confidence_level.value}")
        return response
