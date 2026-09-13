# Requirement Traceability Map (v1.1)
## Intelligent SQL Assistant

Canonical requirement IDs. Every capability is tracked through: **PRD → TRD → Architecture → Backend Schema → App Flow → UI/UX → Tracker → Test/Evaluation evidence**. Nothing in this project is described in only one document; if a doc mentions a capability without an ID below, it is documentation drift and must be fixed.

**Document precedence when two documents conflict:** `RULES > TRD > ARCHITECTURE > PRD > BACKEND SCHEMA > APP FLOW > UI/UX > IMPLEMENTATION PLAN`. Rules wins because it encodes non-negotiable safety/authorization constraints; Implementation Plan is lowest because it is a schedule, not a spec.

| Req ID | Capability | Priority | PRD § | TRD § | Arch § | Schema table(s) | Flow § | UI § | Tracker # | Test/Eval evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| REQ-AUTH-01 | JWT login/refresh | P0 | 5 | 5 | §2 API Gateway | `users`,`sessions` | 2.1 | 3.1 | T-35 | test_auth_and_rbac.py |
| REQ-AUTH-02 | Fail-closed RBAC (no record = no access) | P0 | 5 | 5 | §2 Policy Enforcement | `role_table_access` | 2.1 | 3.1 | T-36 | test_auth_and_rbac.py::test_default_deny |
| REQ-AUTH-03 | Column/row-level data policy | P0 | 5 | 5 | §2 Policy Enforcement | `data_policy`,`row_filters` | 2.6 | 3.3 | T-38 | test_data_policy.py |
| REQ-NLSQL-01 | Schema introspection + sanitized value grounding | P0 | 5 | 2,3 | §2 Schema Retrieval | `schema_snapshot` | — | 3.7 | T-08/09/10 | test_schema_introspector.py |
| REQ-NLSQL-02 | Intent/ambiguity detection before SQL generation | P0 | 5 | 3.0 | §2 Intent/Ambiguity Layer | `query_history.ambiguity_flag` | 2.3(a) new | 3.3 | T-26 | eval_category=ambiguous |
| REQ-NLSQL-03 | Query Router: simple vs compound path | P0 | 5 | 3.0 | §2 Query Router | — | 2.0 | — | T-new | eval_latency_by_path |
| REQ-NLSQL-04 | NL → SQL generation (LLM) | P0 | 5 | 3.1 | §2 SQL Generator | `query_history.initial_sql` | 2.3 | 3.2 | T-11 | eval_execution_accuracy |
| REQ-SAFE-01 | AST statement-type validation (SELECT-only) | P0 | 6 | 5,3.0 | §2 Policy Enforcement | — | 2.3 | 3.2 | T-12 | test_sql_validator.py |
| REQ-SAFE-02 | Schema/column/function authorization (deny-by-default) | P0 (critical) | 6 | 5,3.0 | §2 Policy Enforcement | `data_policy`,`function_allowlist` | 2.3 | 3.2 | T-new | test_policy_enforcement.py |
| REQ-SAFE-03 | Resource/cost limits (timeout, row cap, statement cost estimate) | P0 (critical) | 6 | 5,3.0 | §2 Policy Enforcement | `query_history.execution_ms` | 2.3 | — | T-13 | test_resource_limits.py |
| REQ-SAFE-04 | Read-only DB role (defense in depth) | P0 | 6 | 5 | §2 Execution Sandbox | — | 2.3 | — | T-13 | infra check |
| REQ-SAFE-05 | Prompt-injection resistance: authorization never derived from NL | P0 (critical) | 6 | 5 | §2 Policy Enforcement | — | — | — | T-new | test_prompt_injection_suite.py |
| REQ-CORR-01 | Self-correction loop, capped at 3 retries | P0 | 5 | 3.2 | §2 Self-Correction | `query_history.retry_count` | 2.6 | 3.2 | T-14 | eval_recovery_by_error_class |
| REQ-CORR-02 | Error taxonomy (E1–E7) + diff view | P0 | 5 | 3.2 | §2 Self-Correction | `query_history.error_type` | 2.6 | 3.2 | T-15 | eval_recovery_by_error_class |
| REQ-EXPL-01 | Explain SQL (ad-hoc pasted SQL AND historical query) | P0 | 5 | 3.3 | §2 Result Processor | — | 2.4 | 3.2 | T-16/new | test_sql_explainer.py |
| REQ-VIS-01 | Chart-type heuristic + selectable chart tab | P0 | 5 | 3.4 | §2 Result Processor | `query_history.chart_type` | 2.3 | 3.2 | T-19/21/22 | usability test |
| REQ-OPT-01 | Evidence-based optimization suggestions (EXPLAIN, not EXPLAIN ANALYZE, by default) | P1 | 6 | 3.5 | §2 Optimize | `optimization_suggestions` | 2.7 | 3.2 | T-35 | test_optimizer.py + test_optimize_api.py + OptimizationCard.jsx |
| REQ-OPT-02 | Controlled EXPLAIN ANALYZE mode (opt-in, sandboxed, admin-only) | P1 | 6 | 3.5 | §2 Optimize | `optimization_suggestions.mode` | 2.7 | — | T-36 | test_optimizer_analyze_mode.py + test_optimize_api.py |
| REQ-RPT-01 | PDF/Excel report generation (single query & session) | P1 | 5 | 5 | §2 Reporting | `reports` | 2.9 | 3.6 | T-34 | test_pdf_report.py + test_excel_report.py + test_report_api.py |
| REQ-RPT-02 | Report access = owner-only download (no "shareable" claim in v1) | P1 | 6 | 5 | §2 Reporting | `reports` (no share fields in v1) | 2.9 | 3.6 | T-34 | test_report_api.py::test_pdf_report_export_and_download_api |

| REQ-HIST-01 | Query history list + **rerun-by-default** (no result cache in v1) | P1 | 5 | 5 | §2 History/Audit | `query_history` | 2.10 | 3.8 | T-17/45 | test_history_endpoint.py |
| REQ-MEM-01 | Structured conversational context (typed fields, not free text) | P1 | 5 | 3.2 | §2 Intent/Ambiguity Layer | `sessions.context_json` (typed schema) | 2.1 | — | T-21/22 | test_context_resolution.py |
| REQ-VER-01 | Schema snapshot + prompt version + model version recorded per query | P0 | — (new NFR) | 8 | §2 all stages | `query_history.schema_snapshot_id, prompt_version, model_name` | — | — | T-new | reproducibility check |
| REQ-AUDIT-01 | LLM call log via hashes, not raw prompt/response text | P0 (critical) | 6 | 5 | §2 all stages | `llm_call_log` (hashed) | — | — | T-new | privacy review |
| REQ-VOICE-01 | Voice-to-SQL (downgraded to P2) | P2 | 5 | 3.6 | §2 (optional path) | — | 2.5 | 3.5 | T-30/31/44-46 | manual QA |
| REQ-AGENT-01 | Multi-step agent for compound requests only (downgraded to P2, routed) | P2 | 5 | 3.7 | §2 Planner Agent | — | 2.7 | 3.4/49 | T-32-34/47-50 | eval_compound_requests |
| REQ-EVAL-01 | Evaluation benchmark: 150–300 categorized questions + baselines | P0 | — (new NFR) | 7 | — | `evaluation_run`,`evaluation_result` | — | — | T-new | eval report |
| REQ-EVAL-02 | Safety violation rate = 0, unauthorized exposure rate = 0 (hard gates) | P0 (critical) | — | 7 | — | `evaluation_result` | — | — | T-new | eval report |

## Trust Engine Additions (v1.2 — from second audit: "Understand → Prove → Execute → Critique → Explain")

These rows are the pivot from "feature-breadth LLM-to-SQL app" to "trustworthy, auditable analytics engine." They are now P0 — this is the actual research/portfolio contribution, not the reporting/voice/agent features.

| Req ID | Capability | Priority | PRD § | TRD § | Arch § | Schema table(s) | Flow § | UI § | Tracker # | Test/Eval evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| REQ-CATALOG-01 | Semantic Data Catalog (typed, sensitivity-tagged schema representation fed to LLM instead of raw schema) | P0 | 5 | 3.0 | §2 Semantic Catalog | `semantic_catalog` | 2.2 | 3.2 | T-new | test_semantic_catalog.py |
| REQ-UNSUPP-01 | Unsupported-question detection (refuses to hallucinate missing tables/relationships) | P0 | 5 | 3.0 | §2 Intent Analyzer | `query_history.classification` | 2.3(b) | 3.3 | T-new | eval_category=unsupported |
| REQ-CRITIC-01 | SQL Critic — semantic sanity pass on generated SQL before execution (e.g. `SUM(order_id)`) | P0 | 5 | 3.2b | §2 SQL Critic | `sql_critic_findings` | 2.3(c) | 3.4 | T-new | eval_category=semantic_smell |
| REQ-RESULT-01 | Result Sanity Checker (zero-row, cardinality explosion, join multiplication, NULL explosion) | P0 | 5 | 3.2c | §2 Result Validator | `result_validation` | 2.6b | 3.4 | T-new | test_result_validator.py |
| REQ-TRUST-01 | Evidence-backed Reliability Score (schema grounding, join confidence, filter interpretation, execution validation, sanity check — never a bare LLM-stated %) | P0 | 5 | 3.2d | §2 Evidence Panel | `query_history.reliability_breakdown` | 2.4b | 3.1/3.4 | T-new | reliability calibration study |
| REQ-EVID-01 | Evidence Panel (question → interpretation → schema evidence → SQL → validation → result, one auditable trail) | P0 | 5 | 3.4 | §2 Evidence Panel | `query_history.*` (composed view) | 2.4b | 3.4 | T-new | usability test |
| REQ-REPLAY-01 | Query Replay (full reproducibility package per run: schema snapshot, prompt version, model, params, validation, plan, latency, result hash, correction history) | P0 | — (NFR) | 3.2e | §2 Reproducible Run | `query_history` (extended) | 2.11 | 3.7 | T-new | reproducibility check |
| REQ-SECLAB-01 | Security Attack Lab — a fixed adversarial suite (DROP/DELETE/UPDATE/UNION-escalation/unauthorized-table/sensitive-column/Cartesian-join/dangerous-function/prompt-injection) run and displayed as blocked/not-blocked | P0 | 6 | 7 | §2 Policy Engine | `security_attack_log` | — | 3.6 | T-new | test_security_attack_lab.py — target 0% violation |
| REQ-FAILOBS-01 | Failure Observatory (classifies every failure: schema hallucination, join error, ambiguous intent, type mismatch, authorization rejection, timeout, semantic mismatch; surfaces top problematic phrases) | P1 | — (NFR) | 7 | §2 Result Validator/Eval | `failure_log` | — | 3.8 | T-new | eval report |
| REQ-EVALLAB-01 | Evaluation Lab UI (benchmark run against baselines A/B/C/D, per-category breakdown, visible not just internal) | P1 | — (NFR) | 7 | — | `evaluation_run`,`evaluation_result` | — | 3.9 | T-new | eval report |

**Positioning change:** REQ-CATALOG-01, REQ-CRITIC-01, REQ-RESULT-01, REQ-TRUST-01, REQ-EVID-01, REQ-REPLAY-01, REQ-SECLAB-01 are now the project's **primary thesis** — "can execution feedback and deterministic policy enforcement improve reliability/safety of LLM-generated SQL versus conventional schema-prompted generation." Voice (REQ-VOICE-01) and the multi-step agent (REQ-AGENT-01) remain P2 and are explicitly *not* the differentiator.

**Rule:** a task in the Tracker cannot move to `Done` unless its Req ID row above has a linked test/evaluation artifact, per the Definition of Done in `08_Rules.md` §4.
