# ResearchDesk: Evaluation Report

## 1. Evaluation Methodology

The ResearchDesk evaluation suite assesses agent behavior across five core dimensions:
1. **Technical Comparison**: Evaluating feature parity, architectural trade-offs, and structured markdown synthesis.
2. **Market & Company Research**: Mapping business entities, value propositions, and positioning anchors.
3. **Explanatory Architecture**: Dissecting system trade-offs with source grounding.
4. **Sparse / Conflicting Evidence**: Testing agent calibration and uncertainty reporting when public literature is speculative.
5. **Tool Failure / Empty Input**: Testing defense against hallucinations, verifying that zero search results degrade to Low confidence without inventing citations.

Evaluations were performed using the live deterministic fallback and tool execution pipeline.

---

## 2. Test Results & Case-by-Case Analysis

| Test ID | Category | Query Summary | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EVAL-01** | Technical Comparison | Top 3 Open-Source Vector DBs for RAG | Identifies candidate vector DBs (Qdrant, Chroma, Milvus), extracts docs, compiles comparison matrix. | Successfully retrieved documentation and articles; generated comparative markdown matrix with source tokens `[S1]`..`[S4]`. | **PASS** |
| **EVAL-02** | Market Research | Indian B2B SaaS Startups in HR Tech | Discovers active Indian HR startups (Darwinbox, Keka, etc.) and summaries positioning. | Discovered prominent players from live web searches, extracted company descriptions, and anchored claims to source domains. | **PASS** |
| **EVAL-03** | Explanatory Architecture | Multi-Agent Architecture for Support | Analyzes pros (specialization, safety) vs cons (latency, token costs, coordination drift). | Deconstructed architectural trade-offs into structured key findings and comparative pros/cons list. | **PASS** |
| **EVAL-04** | Sparse / Conflicting Evidence | Photonic Quantum Vector Embeddings | Acknowledges speculative nature, sets Medium/Low confidence, avoids fabricating benchmarks. | Correctly flagged limited empirical benchmarks in public literature; reported conservative confidence with explicit limitations. | **PASS** |
| **EVAL-05** | Empty / Tool Failure Fallback | Random Token Empty Search Query | Zero search hits triggers graceful insufficient-evidence response without hallucinated URLs. | Returned explicit "Insufficient external evidence" response with `Confidence: Low` and zero false citations. | **PASS** |

**Summary**: 5 / 5 Test Cases Passed (100% adherence to safety and schema contracts).

---

## 3. Key Engineering Observations

1. **Hallucination Suppression via Source Auditing**:
   By enforcing that all synthesized findings anchor strictly to `[S#]` tokens present in the current retrieved pool, the system eliminates fabricated citations.
2. **Defensive Web Retrieval**:
   Directly parsing HTML with script and style elimination prevents prompt injection payloads embedded in third-party webpages from executing or hijacking the model's instructions.
3. **Resilience to Single-Point Tool Outages**:
   When individual websites fail with 403, 404, or timeouts, the orchestrator isolates the failure and completes synthesis with surviving sources.

---

## 4. Known Limitations & Potential Improvements

- **JavaScript-Rendered SPAs**:
  Single Page Applications requiring client-side JS rendering (e.g. React/Vue without SSR) yield minimal text with basic `httpx` GET. In a production cloud deployment, adding a headless browser service (e.g., Playwright or a managed browser rendering worker) would expand coverage.
- **Dynamic Parallel Crawling**:
  Currently, candidate webpage extraction runs sequentially to avoid triggering rate limits on target domains. For high-throughput requirements, an `asyncio.gather` pool with per-host concurrency limits would reduce end-to-end latency.
- **Confidence Calibration**:
  Confidence is currently scored via deterministic heuristics (source count, deep page extraction success, query keyword overlap). A calibrated statistical confidence model or multi-rater consensus could further refine uncertainty quantification.
