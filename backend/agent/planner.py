"""
Question Analyzer and Research Planner for ResearchDesk.
Analyzes user intent, identifies subquestions, determines freshness needs,
and produces a step-by-step structured ResearchPlan.
"""

from typing import Dict, List, Optional
from backend.schemas import PlanStep, ResearchPlan
from backend.services.llm_service import get_llm_service
from backend.utils.logging_config import logger


class QuestionPlanner:
    """Deconstructs user research queries and formulates structured plans."""

    def __init__(self, llm_service=None):
        self.llm = llm_service or get_llm_service()

    def plan(self, question: str) -> ResearchPlan:
        """
        Generates a structured research plan.
        Uses LLM when configured, with a solid heuristic fallback.
        """
        logger.info(f"Generating research plan for query: '{question}'")

        if self.llm.is_available:
            try:
                return self._llm_plan(question)
            except Exception as e:
                logger.warning(f"LLM planner failed: {e}. Falling back to heuristic planner.")
                return self._heuristic_plan(question)
        else:
            return self._heuristic_plan(question)

    def _llm_plan(self, question: str) -> ResearchPlan:
        """Calls the LLM to analyze the question and construct the plan."""
        system_prompt = (
            "You are a Senior Research Architect. Analyze the user's research query and formulate an explicit, "
            "practical step-by-step research plan. Return JSON strictly matching this schema:\n"
            "{\n"
            '  "objective": "Concise main research objective",\n'
            '  "subquestions": ["subquestion 1", "subquestion 2", ...],\n'
            '  "steps": [\n'
            '    {\n'
            '      "step_number": 1,\n'
            '      "title": "Short title",\n'
            '      "description": "Specific action to take",\n'
            '      "tool_to_use": "web_search" | "web_retrieval" | "synthesizer",\n'
            '      "status": "pending"\n'
            '    }\n'
            '  ],\n'
            '  "initial_assumptions": ["assumption 1", ...]\n'
            "}\n"
            "Keep the plan realistic and between 3 to 5 steps. Do not claim research has already occurred."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Research query: {question}"},
        ]

        data = self.llm.generate_json(messages, temperature=0.1)

        steps = [
            PlanStep(
                step_number=s.get("step_number", idx + 1),
                title=s.get("title", f"Step {idx+1}"),
                description=s.get("description", ""),
                tool_to_use=s.get("tool_to_use"),
                status="pending",
            )
            for idx, s in enumerate(data.get("steps", []))
        ]

        return ResearchPlan(
            objective=data.get("objective", f"Investigate: {question}"),
            subquestions=data.get("subquestions", []),
            steps=steps,
            initial_assumptions=data.get("initial_assumptions", []),
        )

    def _heuristic_plan(self, question: str) -> ResearchPlan:
        """Deterministic heuristic plan when LLM is unavailable."""
        q_lower = question.lower()
        is_comparison = any(w in q_lower for w in ["compare", "vs", "versus", "difference", "top"])
        is_startup_market = any(w in q_lower for w in ["startup", "company", "companies", "saas", "market"])

        if is_comparison:
            objective = f"Compare and evaluate key options related to: {question}"
            subquestions = [
                "What are the leading alternatives or technologies meeting these criteria?",
                "What are the core technical features, trade-offs, and deployment requirements?",
                "What practical operational limitations or cost trade-offs exist between them?",
            ]
            steps = [
                PlanStep(
                    step_number=1,
                    title="Identify candidate options",
                    description="Execute targeted web search to identify candidate subjects and community consensus.",
                    tool_to_use="web_search",
                ),
                PlanStep(
                    step_number=2,
                    title="Retrieve technical documentation",
                    description="Fetch detailed specifications, architecture documents, and benchmarks.",
                    tool_to_use="web_retrieval",
                ),
                PlanStep(
                    step_number=3,
                    title="Evaluate feature parity & trade-offs",
                    description="Analyze side-by-side capabilities, strengths, and developer ecosystem support.",
                    tool_to_use="synthesizer",
                ),
                PlanStep(
                    step_number=4,
                    title="Formulate grounded recommendations",
                    description="Synthesize comparative matrix and actionable selection criteria.",
                    tool_to_use="synthesizer",
                ),
            ]
        elif is_startup_market:
            objective = f"Conduct market mapping and positioning analysis for: {question}"
            subquestions = [
                "Which active companies operate in this category?",
                "What are their stated value propositions and target market segments?",
                "What common industry patterns or differentiation strategies are observable?",
            ]
            steps = [
                PlanStep(
                    step_number=1,
                    title="Discover market participants",
                    description="Search for ecosystem landscape overviews, startup directories, and industry reporting.",
                    tool_to_use="web_search",
                ),
                PlanStep(
                    step_number=2,
                    title="Examine company offerings",
                    description="Retrieve product positioning and customer segment details from relevant sites.",
                    tool_to_use="web_retrieval",
                ),
                PlanStep(
                    step_number=3,
                    title="Synthesize positioning landscape",
                    description="Consolidate company profiles, strengths, and market context with citation anchors.",
                    tool_to_use="synthesizer",
                ),
            ]
        else:
            objective = f"Perform in-depth technical investigation on: {question}"
            subquestions = [
                "What are the fundamental concepts and state-of-the-art developments?",
                "What empirical evidence or production best practices exist?",
                "What key trade-offs, limitations, and edge cases should be considered?",
            ]
            steps = [
                PlanStep(
                    step_number=1,
                    title="Information discovery",
                    description="Search credible external web resources and technical documentation.",
                    tool_to_use="web_search",
                ),
                PlanStep(
                    step_number=2,
                    title="Deep evidence extraction",
                    description="Retrieve and parse high-signal webpage text from top search results.",
                    tool_to_use="web_retrieval",
                ),
                PlanStep(
                    step_number=3,
                    title="Evidence synthesis & validation",
                    description="Synthesize findings, verify source grounding, and assemble structured report.",
                    tool_to_use="synthesizer",
                ),
            ]

        return ResearchPlan(
            objective=objective,
            subquestions=subquestions,
            steps=steps,
            initial_assumptions=[
                "External sources represent current publicly accessible information.",
                "Assessment prioritizes production readiness and engineering pragmatism.",
            ],
        )
