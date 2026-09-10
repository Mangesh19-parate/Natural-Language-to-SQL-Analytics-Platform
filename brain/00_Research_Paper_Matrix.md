# Research Paper Matrix (v1.1)
## Intelligent SQL Assistant — Natural Language to SQL Analytics Platform

**Changes from v1.0 (per external audit):**
- Removed the unsupported "no existing system does this" framing from the problem statement.
- Replaced single unexplained "match %" numbers with an explicit, reproducible **overlap-dimension table** plus a percentage computed only as `(dimensions matched / 8 total dimensions)`. This is a coarse proxy, not a formal similarity metric — stated explicitly so it cannot be misread as one.
- Relabeled every "advantage" as a **designed contribution** (intended at spec time) vs. **demonstrated contribution** (only claimable after the evaluation in `07_Tracker.md` / `10_Requirement_Traceability_Map.md` passes). Nothing below is claimed as demonstrated yet — this project has not been implemented.

---

## Overlap Dimensions (used for all match calculations below)

| # | Dimension | Description |
|---|---|---|
| D1 | NL → SQL generation | Converts natural language to executable SQL |
| D2 | Execution against a live DB | Actually runs the query, not just generates text |
| D3 | Self-correction | Detects execution/syntax errors and retries |
| D4 | Multi-turn conversational memory | Maintains context across follow-up questions |
| D5 | Visualization | Auto-generates charts from results |
| D6 | Query optimization guidance | Index/EXPLAIN-based suggestions |
| D7 | Business reporting (PDF/Excel export) | Generates downloadable reports |
| D8 | Voice input | Speech-to-SQL path |

Match % = (number of dimensions the paper addresses, even partially) / 8. **This is a topical-overlap heuristic for literature positioning, not a validated similarity score.**

---

## BASE PAPER

**[BP] Conversational BI: Natural Language Interface to Business Dashboards**
G. Naren Shailesh, Pavithran M, Rahul Hari Venkat A, P. Kaliappan — IJERT, Vol. 14, Issue 12, Dec 2025.

| D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | Match |
|---|---|---|---|---|---|---|---|---|
| ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | 5/8 (63%) |

**Corrected positioning:** This paper already implements D1–D5. **Our project's contribution is not "combining these five capabilities" — the base paper does that.** Our defensible, narrower contribution is:
1. Extending the same core loop with D6 (evidence-based optimization) and D7 (reporting), which the base paper's own future-work section identifies as gaps.
2. Replacing the base paper's execution-safety model (implicit) with an explicit, deny-by-default **policy enforcement layer** (schema/column/function authorization + resource limits), addressing accuracy-on-complex-queries and ambiguity-resolution weaknesses the paper names as open problems.
3. Adding a formal, categorized evaluation methodology (150–300 questions, baseline comparison, safety-violation-rate as a hard metric) where the base paper evaluates only on sample datasets in a controlled setting.

None of these are claimed as achieved — they are the *design target* this project is being built against (see `10_Requirement_Traceability_Map.md`).

---

## REFERENCE PAPERS

| ID | Paper | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | Match | Gap this project targets (designed, not yet demonstrated) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | AI Enhanced Database Query Assistant Using LLM (MSSQL), IJSDR 2025 | ✓ | ✓ | partial | ✗ | ✗ | ✗ | ✗ | ✗ | 3/8 (38%*) | Single-vendor DB lock-in; no visualization/reporting layer |
| R2 | Evaluating Open-Source LLM Agents for SQL Generation, ScienceDirect 2026 | ✓ | ✓ | partial | ✗ | ✗ | ✗ | ✗ | ✗ | 3/8 (38%*) | Backend-agent benchmark only, no end-user product |
| R3 | TwinBI: Agentic Digital Twin for BI Dashboards, arXiv 2606.13731 | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | 3/8 (38%*) | Requires pre-built dashboard infra; no NL→SQL from scratch |
| R4 | Fact-Consistency Evaluation of Text-to-SQL for BI (Exaone 3.5), arXiv 2505.00060 | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | 2/8 (25%*) | Evaluation framework only, no deployable interface |
| R5 | SiriusBI: Comprehensive LLM-Powered Solution for BI, arXiv 2411.06102 | ✓ | ✓ | ✓ | ✓ | ✓ | partial | ✗ | ✗ | 5.5/8 (69%*) | Enterprise-infra heavy; no voice; optimization not evidence-based |
| R6 | ChatBI: NL to Complex BI SQL, arXiv 2405.00527 (Baidu) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | 2/8 (25%*) | Proprietary platform coupling; not portable |
| R7 | A Survey of NL2SQL with LLMs, arXiv 2408.05109 | ✓(survey) | — | — | — | — | — | — | — | n/a | Survey only, catalogs gaps rather than closing them |
| R8 | ChartGPT: LLMs to Generate Charts from Abstract NL, arXiv 2311.01920 | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | 1/8 (13%*) | Chart-only; no DB connectivity |
| R9 | Chat2VIS: Data Visualisations via NL using ChatGPT/Codex/GPT-3, IEEE Access 2023 | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | 1/8 (13%*) | Assumes pre-loaded dataframe, not a live DB |
| R10 | Automated Data Viz from NL via LLMs (NL2Vis), SIGMOD 2024 | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | 1/8 (13%*) | Exploratory prompting study, not deployed |
| R11 | Speech-to-SQL, VLDB Journal 2024 / arXiv 2201.01209 | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | 3/8 (38%*) | Academic benchmark only; no viz/reporting integration |
| R12 | VoiceQuerySystem: Voice-Driven DB Querying, SIGMOD 2022 | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | 3/8 (38%*) | Cascaded ASR error compounding; execution-only, no insights |
| R13 | DIN-SQL: Decomposed In-Context Learning with Self-Correction, NeurIPS 2023 | ✓ | partial (benchmark) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | 2.5/8 (31%*) | Benchmark-only correction (Spider), not live-DB error feedback |
| R14 | Understanding/Detecting/Repairing Text-to-SQL Errors, arXiv 2501.09310 | ✓ | partial | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | 2.5/8 (31%*) | Error taxonomy research only, not packaged as a product feature |
| R15 | C3: Zero-Shot Text-to-SQL with ChatGPT, EMNLP 2023 | ✓ | partial (benchmark) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | 1.5/8 (19%*) | Benchmark accuracy only; no application layer |

\* Percentages below ~45% are retained here for completeness of the literature review but are **below the project's own 45% inclusion bar** stated in the assignment; R7–R10, R13–R15 are included as conceptually necessary (self-correction, visualization, survey-of-gaps) even where raw dimension overlap is lower, and this is disclosed rather than inflated.

---

## Net Positioning (revised, defensible framing)

**Do not claim:** "No existing system combines NL querying, self-correction, visualization, reporting, and optimization."

**Claim instead:**

> Within the reviewed literature, no single system jointly treats (a) execution-grounded self-correction against live database errors, (b) a deny-by-default authorization layer sitting between SQL generation and execution, and (c) evidence-based optimization and reporting, as one deployable pipeline with a formal categorized evaluation. Individual capabilities (D1–D8) are each addressed by at least one paper above; the *combination with an explicit policy-enforcement boundary and reproducible evaluation methodology* is what this project targets and must demonstrate empirically, not assert.

This framing survives a viva question of "how is this different from the base paper" because it names a specific architectural addition (policy enforcement + evaluation rigor), not a vague feature bundle.
