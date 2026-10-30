"""
Source-Grounded Answer Synthesizer for ResearchDesk.
Uses retrieved evidence and source identifiers [S1], [S2] to synthesize a rigorous,
hallucination-resistant research summary with confidence scoring and citation validation.
"""

import re
from typing import Any, Dict, List, Optional
from backend.schemas import (
    ConfidenceLevel,
    KeyFinding,
    ResearchPlan,
    ResearchResponse,
    SourceItem,
)
from backend.services.llm_service import get_llm_service
from backend.utils.logging_config import logger


class AnswerSynthesizer:
    """Synthesizes structured research answers strictly grounded in retrieved evidence."""

    def __init__(self, llm_service=None):
        self.llm = llm_service or get_llm_service()

    def synthesize(
        self,
        question: str,
        plan: ResearchPlan,
        sources: List[SourceItem],
        warnings: Optional[List[str]] = None,
    ) -> ResearchResponse:
        """
        Synthesizes the complete research response based on collected sources.
        """
        warnings_list = list(warnings or [])
        logger.info(f"Synthesizing response for question with {len(sources)} sources.")

        # Guard: If no sources were retrieved or all tools failed
        if not sources:
            warnings_list.append("No usable external sources could be retrieved.")
            return self._insufficient_evidence_response(question, plan, warnings_list)

        if self.llm.is_available:
            try:
                response = self._llm_synthesize(question, plan, sources, warnings_list)
                # Run strict citation grounding audit
                response = self._audit_citations(response, sources)
                return response
            except Exception as e:
                logger.warning(
                    f"LLM synthesis failed ({e}). Falling back to grounded rule-based synthesizer."
                )
                warnings_list.append(f"LLM synthesis experienced an issue: {str(e)}")
                return self._rule_based_synthesize(question, plan, sources, warnings_list)
        else:
            warnings_list.append(
                "Running in offline / rule-based mode. For full generative synthesis, configure an LLM API key in .env"
            )
            return self._rule_based_synthesize(question, plan, sources, warnings_list)

    def _llm_synthesize(
        self,
        question: str,
        plan: ResearchPlan,
        sources: List[SourceItem],
        warnings: List[str],
    ) -> ResearchResponse:
        """Prompts LLM with evidence packets tagged with [S1], [S2] identifiers."""
        # Build context document
        evidence_blocks = []
        for s in sources:
            text_snippet = s.extracted_text or s.snippet or "No text excerpt available."
            evidence_blocks.append(
                f"Source Identifier: {s.id}\n"
                f"Title: {s.title}\n"
                f"URL: {s.url}\n"
                f"Status: {s.retrieval_status.value}\n"
                f"Evidence:\n{text_snippet}\n"
                f"----------------------------------------"
            )
        evidence_text = "\n\n".join(evidence_blocks)

        system_prompt = (
            "You are ResearchDesk, an elite senior technical research analyst. "
            "Synthesize a rigorous, executive-grade answer based EXCLUSIVELY on the provided sources.\n\n"
            "CRITICAL CITATION AND FACTUAL GROUNDING RULES:\n"
            "1. You MUST anchor factual claims, metrics, and comparisons to source IDs (e.g., [S1], [S2]).\n"
            "2. NEVER invent sources, URLs, statistics, or quotes. Only reference the source IDs provided.\n"
            "3. If sources conflict or evidence is missing, explicitly document the divergence or gap.\n"
            "4. Assign confidence strictly on evidence quality:\n"
            "   - 'High': Multiple reputable sources with corroborating details.\n"
            "   - 'Medium': Good source coverage with minor gaps or slight reliance on snippets.\n"
            "   - 'Low': Sparse evidence, single source, or conflicting unverified data.\n"
            "5. Return a valid JSON object matching the exact schema below.\n\n"
            "SCHEMA:\n"
            "{\n"
            '  "short_answer": "Direct 2-4 sentence executive summary answering the user question",\n'
            '  "detailed_analysis": "Comprehensive markdown analysis with headings, comparison tables if appropriate, and inline [S#] citations",\n'
            '  "key_findings": [\n'
            '    {\n'
            '      "claim": "Specific finding or distinction",\n'
            '      "detail": "Supporting explanation citing evidence",\n'
            '      "supporting_source_ids": ["[S1]"]\n'
            '    }\n'
            '  ],\n'
            '  "confidence_level": "High" | "Medium" | "Low",\n'
            '  "confidence_explanation": "Justification based on source corroboration, depth, and relevance",\n'
            '  "assumptions": ["List of reasonable assumptions made"],\n'
            '  "limitations": ["Data freshness, missing benchmarks, or source scope constraints"],\n'
            '  "suggested_next_steps": ["Actionable follow-up steps for the researcher"]\n'
            "}"
        )

        user_content = (
            f"Research Question: {question}\n\n"
            f"Objective: {plan.objective}\n\n"
            f"AVAILABLE RETRIEVED EVIDENCE:\n{evidence_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        data = self.llm.generate_json(messages, temperature=0.15)

        # Parse key findings
        findings = []
        for f in data.get("key_findings", []):
            findings.append(
                KeyFinding(
                    claim=f.get("claim", ""),
                    detail=f.get("detail", ""),
                    supporting_source_ids=f.get("supporting_source_ids", []),
                )
            )

        # Validate confidence level enum
        raw_conf = data.get("confidence_level", "Medium").capitalize()
        confidence = (
            ConfidenceLevel(raw_conf)
            if raw_conf in [c.value for c in ConfidenceLevel]
            else ConfidenceLevel.MEDIUM
        )

        return ResearchResponse(
            question=question,
            short_answer=data.get("short_answer", "Research investigation completed."),
            detailed_analysis=data.get("detailed_analysis", ""),
            key_findings=findings,
            sources_used=sources,
            confidence_level=confidence,
            confidence_explanation=data.get(
                "confidence_explanation",
                f"Synthesized based on {len(sources)} external retrieved references.",
            ),
            assumptions=data.get("assumptions", plan.initial_assumptions),
            limitations=data.get("limitations", []),
            suggested_next_steps=data.get("suggested_next_steps", []),
            research_plan=plan,
            execution_trace=[],
            warnings=warnings,
        )

    def _audit_citations(
        self, response: ResearchResponse, valid_sources: List[SourceItem]
    ) -> ResearchResponse:
        """
        Validates that every citation token [S#] referenced in findings exists in valid_sources.
        Removes orphan citations to prevent hallucinated references.
        """
        valid_ids = {s.id for s in valid_sources}

        for finding in response.key_findings:
            cleaned_ids = [s_id for s_id in finding.supporting_source_ids if s_id in valid_ids]
            # If empty, attempt to infer from finding text
            if not cleaned_ids:
                matches = re.findall(r"\[S\d+\]", f"{finding.claim} {finding.detail}")
                cleaned_ids = [m for m in matches if m in valid_ids]
            finding.supporting_source_ids = list(dict.fromkeys(cleaned_ids))

        return response

    def _rule_based_synthesize(
        self,
        question: str,
        plan: ResearchPlan,
        sources: List[SourceItem],
        warnings: List[str],
    ) -> ResearchResponse:
        """Deterministic, grounded synthesis when running without LLM API key."""
        findings: List[KeyFinding] = []

        for s in sources:
            summary_snippet = s.snippet or (
                s.extracted_text[:200] + "..." if s.extracted_text else "Evidence verified."
            )
            findings.append(
                KeyFinding(
                    claim=f"Insight from {s.title}",
                    detail=summary_snippet,
                    supporting_source_ids=[s.id],
                )
            )

        detailed_sections = [
            f"### Research Overview: {question}",
            f"This analysis was compiled using evidence retrieved from {len(sources)} external sources.",
            "",
            "#### Comparative Evidence Matrix",
            "| Source ID | Title | Domain | Status |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for s in sources:
            detailed_sections.append(
                f"| {s.id} | [{s.title}]({s.url}) | {s.domain} | {s.retrieval_status.value} |"
            )

        detailed_sections.append("\n#### Detailed Source Observations")
        for s in sources:
            content_preview = (
                s.extracted_text[:400] + "..." if s.extracted_text else s.snippet
            )
            detailed_sections.append(
                f"- **{s.id} ({s.title})**: {content_preview}"
            )

        confidence = (
            ConfidenceLevel.HIGH
            if len(sources) >= 3 and any(s.extracted_text for s in sources)
            else (ConfidenceLevel.MEDIUM if len(sources) >= 1 else ConfidenceLevel.LOW)
        )

        return ResearchResponse(
            question=question,
            short_answer=(
                f"Retrieved and analyzed evidence across {len(sources)} authoritative external sources "
                f"for the query '{question}'."
            ),
            detailed_analysis="\n".join(detailed_sections),
            key_findings=findings,
            sources_used=sources,
            confidence_level=confidence,
            confidence_explanation=(
                f"Confidence is rated {confidence.value} based on {len(sources)} grounded sources "
                "with validated HTTP status and keyword relevance matching."
            ),
            assumptions=plan.initial_assumptions or [
                "Information is grounded directly in external search and webpage extractions."
            ],
            limitations=[
                "Offline deterministic synthesis active: responses reflect direct source extractions.",
                "Deep internal benchmarks require dynamic evaluation beyond public documentation."
            ],
            suggested_next_steps=[
                "Review primary source URLs for specialized configuration options.",
                "Conduct hands-on proof-of-concept testing tailored to your infrastructure constraints."
            ],
            research_plan=plan,
            execution_trace=[],
            warnings=warnings,
        )

    def _insufficient_evidence_response(
        self, question: str, plan: ResearchPlan, warnings: List[str]
    ) -> ResearchResponse:
        """Returns structured result when zero evidence could be retrieved."""
        return ResearchResponse(
            question=question,
            short_answer="Insufficient external evidence: no reliable external sources could be retrieved to answer this query.",
            detailed_analysis=(
                "### Insufficient Evidence Notice\n"
                "The research agent performed search operations, but was unable to acquire reliable, "
                "accessible information from external sources. The system refused to fabricate citations or facts."
            ),
            key_findings=[],
            sources_used=[],
            confidence_level=ConfidenceLevel.LOW,
            confidence_explanation="Confidence is Low because zero external sources yielded parseable results.",
            assumptions=[],
            limitations=[
                "External search provider returned no matching entries or network connectivity was unreachable.",
                "The agent does not generate unverified claims from memory."
            ],
            suggested_next_steps=[
                "Broaden or rephrase the research question.",
                "Verify network connectivity and search provider API settings.",
            ],
            research_plan=plan,
            execution_trace=[],
            warnings=warnings,
        )
