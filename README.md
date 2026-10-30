# ResearchDesk: Production-Oriented AI Research Agent

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/Tests-13%20Passed%20(100%25)-brightgreen.svg)]()
[![Evaluation](https://img.shields.io/badge/Evaluation-5%2F5%20Passed-success.svg)]()

> **ResearchDesk** is a tool-using AI research agent designed for technical analysts, founders, and engineers. It accepts research questions, formulates an explicit plan, invokes specialized external research tools, extracts and deduplicates evidence, and synthesizes structured, source-grounded answers with verifiable citation anchors, confidence metrics, and limitation boundaries.

---

## 1. Project Overview & Problem Statement

### The Problem with Basic LLM Chatbots
Standard conversational LLMs suffer from severe limitations when used for real technical or market research:
- **Knowledge Cutoffs**: Inability to reflect recent software releases, pricing shifts, or emerging companies.
- **Hallucinated Citations**: Fabricating plausible-sounding URLs, papers, benchmarks, and quotations from memory.
- **Hidden Reasoning**: Black-box single-step prompting without visible planning, verifiable tool traces, or uncertainty quantification.
- **Prompt Injection Vulnerability**: Ingesting untrusted third-party web content that can hijack system prompts.

### The Solution: An Agentic Research Workflow
**ResearchDesk** addresses these challenges through an explicit, modular pipeline. Instead of relying on parametric LLM memory, it treats the LLM primarily as a reasoning, extraction, and synthesis engine over actual web documents retrieved in real time.

```
User (Browser)
      │
      ▼
Streamlit Frontend (ResearchDesk)
      │  HTTP POST /api/research
      ▼
FastAPI Backend (REST API)
      │
      ▼
Research Orchestrator
      ├── 1. Question Analysis & Planning (agent/planner.py)
      ├── 2. Tool Selection & Query Generation (agent/tool_selector.py)
      ├── 3. Tool Execution:
      │       ├── Web Search Tool (tools/web_search.py)
      │       └── Webpage Retrieval & Text Cleaning Tool (tools/web_retrieval.py)
      ├── 4. Source Filtering & Normalization (agent/source_filter.py)
      ├── 5. Grounded Answer Synthesis & Citation Audit (agent/synthesizer.py)
      └── 6. Pydantic Output Validation & Trace Timing (schemas.py)
      │
      ▼
Structured ResearchResponse (Markdown, Findings, [S#] Citations, Trace)
```

---

## 2. Technology Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) with asynchronous ASGI lifespans and CORS middleware.
- **Server**: [Uvicorn](https://www.uvicorn.org/) high-performance server.
- **Schema & Validation**: [Pydantic V2](https://docs.pydantic.dev/) and `pydantic-settings` for robust contract enforcement.
- **LLM Provider SDK**: Official [OpenAI](https://github.com/openai/openai-python) SDK (supports OpenAI `gpt-4o-mini`, Groq `llama-3.3-70b`, Gemini OpenAI endpoint, and local vLLM/Ollama).
- **Search Tooling**: [DuckDuckGo Search](https://github.com/deedy5/duckduckgo_search) (zero-cost, no API key required out of the box) with pluggable support for [Tavily](https://tavily.com/).
- **HTML Extraction & Parsing**: [HTTPX](https://www.python-httpx.org/) client with [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) for DOM sanitization and content extraction.
- **Frontend**: [Streamlit](https://streamlit.io/) with custom restrained CSS surfaces and responsive tabs.
- **Testing & Quality Assurance**: [pytest](https://docs.pytest.org/) and `pytest-asyncio` with 100% mocked external API test isolation.

---

## 3. Detailed Agent Workflow & Architecture

### A. Question Analyzer & Research Planner (`agent/planner.py`)
- Analyzes the input to extract core objectives, subquestions, temporal freshness needs, and initial assumptions.
- Formulates a discrete 3 to 5 step `ResearchPlan` (e.g. identify candidates → retrieve technical documentation → evaluate trade-offs → synthesize grounded report).
- Runs with LLM assistance when configured, falling back to an intelligent deterministic heuristic planner if offline.

### B. Tool Selector (`agent/tool_selector.py`)
- Deconstructs the plan into 1–3 high-precision search queries.
- Dynamically determines whether full webpage body extraction (`web_retrieval`) is required (e.g. for deep technical or architecture comparisons) or if search snippets are sufficient.
- Selects top candidate URLs avoiding duplicates or low-signal domains.

### C. External Research Tools
1. **Tool 1: Web Search (`tools/web_search.py`)**
   - Interacts with DuckDuckGo (or Tavily if configured).
   - Returns normalized dictionaries: `title`, `url`, `snippet`, and `source_provider`.
   - Incorporates retry limits and connection timeout guards.
2. **Tool 2: Webpage Retrieval (`tools/web_retrieval.py`)**
   - Safely retrieves HTML via HTTPX with user-agent headers.
   - Rejects non-HTTP(S) schemes (blocks `file://`, `ftp://`, etc.) and non-text MIME types.
   - Decomposes noisy DOM elements (`<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>`, `<iframe>`, `<form>`).
   - Implements **Prompt Injection Neutralization**: untrusted webpage text is scanned and stripped of instruction-override markers (`IGNORE PREVIOUS INSTRUCTIONS`, `<|im_start|>`, etc.).
   - Truncates individual pages to configurable limits (`page_char_limit = 6000`) to prevent context overflow.

### D. Source Filtering & Evidence Deduplication (`agent/source_filter.py`)
- Strips URL marketing trackers (`utm_source`, `ref`, `fbclid`, fragment `#hash`).
- Deduplicates canonical URLs.
- Evaluates keyword alignment between search query terms and title/snippet content.
- Assigns persistent source reference tokens: `[S1]`, `[S2]`, ..., `[Sn]`.

### E. Source-Grounded Synthesizer & Citation Audit (`agent/synthesizer.py`)
- Injects source packets labeled strictly with `[S1]`, `[S2]` into the LLM synthesis context.
- System prompt mandates that every factual claim in `key_findings` and `detailed_analysis` must anchor to a valid source ID.
- **Citation Post-Audit**: Any hallucinated citation token not in the retrieved sources pool is automatically pruned.
- **Zero-Evidence Safety**: If search returns 0 results or tools fail, the system explicitly returns an insufficient-evidence response with Low confidence and zero fabricated citations.

---

## 4. Key Assignment Questions Answered

### 1. Why is an agentic approach appropriate?
A single static prompt to an LLM cannot verify whether information has changed, cannot fetch live API documentation, and cannot ground claims in authoritative third-party URLs. An agentic workflow decouples planning from retrieval and synthesis: it formulates what it needs to find, exercises external search and retrieval tools, assesses the quality of evidence, and only then compiles the response.

### 2. Which tools were chosen, and why?
- **DuckDuckGo Web Search**: Chosen because it provides zero-barrier, zero-cost search out of the box without requiring paid API keys or corporate credit cards, with seamless fallback to Tavily for enterprise grade accuracy.
- **HTTPX + BeautifulSoup4 Webpage Scraper**: Chosen because search snippets alone are often incomplete or marketing fluff. Full HTML retrieval allows the agent to inspect deep technical documentation, architecture specs, and comparison tables while maintaining complete control over timeouts, memory limits, and prompt injection filtering.

### 3. How does the system handle bad tool results?
- **Per-Page Error Isolation**: If one webpage returns HTTP 403, 404, or times out after 15s, the orchestrator records the failure and proceeds with surviving sources.
- **Empty Search Fallback**: If the search engine yields no results, the synthesizer declines to fabricate facts, returning an explicit "Insufficient external evidence" response with `Confidence: Low`.
- **Malformed URL Rejection**: Invalid protocols or local file schemes are discarded before network requests are initiated.

### 4. How does the system reduce hallucinations?
- **Strict Grounding Contract**: The LLM is instructed to answer solely using the evidence blocks provided in the prompt.
- **Citation Token Validation**: Claims must reference `[S1]`, `[S2]`. The synthesizer's audit routine compares referenced IDs against the verified sources list, stripping ungrounded citations.
- **Explicit Uncertainty Scoring**: Rather than generating confident fiction, the system scores confidence as Low when evidence is sparse or contradictory.

### 5. How would the system be made production-ready?
- **Async Concurrency**: Parallelize candidate page retrieval across an `asyncio` task pool with per-domain rate limiting.
- **Headless Browser Sidecar**: Deploy a Playwright or Chromium container for client-side JavaScript SPAs that fail standard HTML parsing.
- **Semantic Caching**: Cache common research queries in Redis using embedding vector similarity (e.g., pgvector) with a 24-hour TTL.
- **Distributed Queues**: Move long-running multi-source research tasks to Celery or Temporal with WebSocket progress streaming.

### 6. What would be monitored in production?
- **Latency by Stage**: Milliseconds spent in Planning vs Search vs Scraping vs Synthesis.
- **Source Yield Rate**: Ratio of search hits to successfully parsed, retained webpages.
- **Tool Error Rates**: Frequency of 403 Forbidden, 429 Rate Limits, or timeouts by domain.
- **Citation Grounding Score**: Percentage of claims with validated `[S#]` tags.
- **Token Costs**: Prompt and completion token consumption per research query.

### 7. What were the key engineering trade-offs?
- **Single Sequential Orchestrator vs Multi-Agent Swarm**: Chose a clean, explicit single-agent pipeline. Multi-agent swarms introduce compounding token costs, nondeterministic conversational loops, and hard-to-debug failures without proportional accuracy gains for single-task research.
- **Zero-Dependency Heuristic Fallback**: Included an offline deterministic synthesis fallback so developers can run, test, and evaluate the full application even before configuring an LLM API key.

---

## 5. Windows Setup & Quickstart Guide

This application is fully tested on Windows using PowerShell and VS Code.

### Step 1: Open Terminal in Project Directory
```powershell
cd "c:\Users\MAHEK PAHUJA\Desktop\Smart Cart Price\ai-research-agent"
```

### Step 2: Create and Activate Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate in PowerShell
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell displays an execution policy restriction, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### Step 3: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy the example file to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` in VS Code or Notepad and add your LLM API key:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
SEARCH_PROVIDER=duckduckgo
```
*(Note: If you do not have an OpenAI API key, ResearchDesk runs in offline deterministic mode with full search and scraping capabilities!)*

### Step 5: Start the FastAPI Backend
In your first PowerShell terminal:
```powershell
uvicorn backend.main:app --reload --port 8000
```
Verify backend health in browser or PowerShell:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```
Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "llm_configured": true,
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "search_provider": "duckduckgo"
}
```

### Step 6: Start the Streamlit Frontend
Open a **second** PowerShell terminal, activate the venv, and run:
```powershell
cd "c:\Users\MAHEK PAHUJA\Desktop\Smart Cart Price\ai-research-agent"
.\.venv\Scripts\Activate.ps1
streamlit run frontend\app.py --server.port 8501
```
The ResearchDesk interface will automatically open at `http://localhost:8501`.

---

## 6. Running Tests & Evaluations

### Run Automated Unit & Integration Tests (13 Tests)
Mocked tests run completely offline and require no API credits:
```powershell
pytest -v
```

### Run the Research Quality Evaluation Framework (5 Scenarios)
Executes the evaluation dataset across technical comparison, market research, architecture analysis, and empty-result handling:
```powershell
python evaluation\run_evaluation.py
```
Output results and audit logs are saved to `evaluation/evaluation_results.json` and documented in `evaluation/evaluation_report.md`.

---

## 7. Example Research Questions Supported

1. *Compare the top three open-source vector databases for a startup building RAG products.*
2. *Find five Indian B2B SaaS startups in HR technology and summarize their positioning.*
3. *Explain the advantages and disadvantages of multi-agent architecture for customer support automation.*
4. *Compare different approaches to implementing memory in an AI support agent.*
5. *Research the trade-offs of microservices vs modular monoliths for early-stage fintech platforms.*

---

## 8. Project Directory Structure

```
ai-research-agent/
│
├── backend/
│   ├── __init__.py
│   ├── config.py              # Pydantic BaseSettings, environment variable loader
│   ├── schemas.py             # Pydantic request, response, and entity schemas
│   ├── orchestrator.py        # Master research pipeline coordinator & trace logger
│   ├── main.py                # FastAPI endpoints, CORS, request middleware
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── planner.py         # Question analyzer and structured plan generator
│   │   ├── tool_selector.py   # Search query synthesizer and tool selector
│   │   ├── source_filter.py   # URL normalizer, deduplicator, and source ranker
│   │   └── synthesizer.py     # Source-grounded answer synthesizer & citation auditor
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── web_search.py      # DuckDuckGo and Tavily web search integrations
│   │   └── web_retrieval.py   # Safe HTML scraper & prompt injection filter
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── llm_service.py     # OpenAI SDK wrapper with retry and JSON mode
│   │
│   └── utils/
│       ├── __init__.py
│       └── logging_config.py  # Structured logger with secret token redaction
│
├── frontend/
│   └── app.py                 # Streamlit UI (ResearchDesk) with tabs and custom CSS
│
├── tests/
│   ├── __init__.py
│   ├── test_api.py            # FastAPI endpoints and validation unit tests
│   ├── test_tools.py          # Search and web retrieval unit tests
│   ├── test_orchestrator.py   # Pipeline transitions and deduplication tests
│   └── test_failures.py       # Empty search, unreachable URLs, and resilience tests
│
├── evaluation/
│   ├── test_queries.json      # 5 evaluation test inquiries covering diverse scenarios
│   ├── run_evaluation.py      # Automated evaluation suite runner
│   ├── evaluation_results.json# Raw evaluation output logs
│   └── evaluation_report.md   # Evaluation methodology, observations, and limits
│
├── sample_outputs/
│   ├── example_1.md           # Sample 1: Technical Comparison (Vector DBs)
│   ├── example_2.md           # Sample 2: Market Research (Indian HR SaaS)
│   └── example_3.md           # Sample 3: Incomplete / Conflicting Evidence
│
├── .env.example               # Environment variables configuration template
├── .env                       # Local environment configuration
├── .gitignore                 # Standard Python/IDE/secrets gitignore
├── requirements.txt           # Verified dependencies
└── README.md                  # Comprehensive documentation
```

---

## 9. Security & Safety Considerations

- **Untrusted External Data**: All retrieved webpages and search snippets are treated as untrusted input. The scraper strips script tags, CSS, frames, and sanitizes known prompt-injection delimiter strings.
- **Secret Redaction**: The custom logging formatter inspects log records and automatically replaces API keys matching `sk-*` or `gsk_*` with `[REDACTED_API_KEY]`.
- **Frontend Isolation**: The Streamlit frontend contains zero secrets or API keys; all sensitive calls and credentials remain isolated on the FastAPI backend.
- **Protocol Restriction**: The scraper only accepts `http` and `https` schemes, rejecting requests targeting local system files or unexpected network protocols.
