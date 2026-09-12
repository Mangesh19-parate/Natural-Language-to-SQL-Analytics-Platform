# Project Tracker — v1.2
## Intelligent SQL Assistant

**Supersedes v1.1.** The audit's critique was correct: a flat task list with no dependencies is not "engineering-grade." Every task now carries **Depends On**, **Acceptance Criteria**, and **Evidence** columns, and the Definition of Done is tiered by risk class (security / AI / performance / research).

Status values: `Not Started` | `In Progress` | `Blocked` | `Done`. A task cannot be `Done` without its Evidence column populated with a real artifact (test file, benchmark run ID, or reviewed PR link).

## 1. Master Task Tracker

| # | Task | REQ-ID | Depends On | Acceptance Criteria | Week | Priority | Evidence | Status |
|---|---|---|---|---|---|---|---|---|
| T-01 | Repo + Docker Compose skeleton | — | — | `docker-compose up` boots API + frontend + DB | 1 | P0 | docker-compose.yml + Dockerfiles + health test | Done |
| T-02 | Business schema + seed data | — | T-01 | Seed script populates 5 tables with ≥100 rows each | 1 | P0 | test_business_seeding.py (10 depts, 120 emps, 150 custs, 100 prods, 200 orders, 350 sales) | Done |
| T-03 | App metadata schema (Alembic) | — | T-01 | Migrations apply cleanly on fresh DB | 1 | P0 | 001_initial_metadata_schema.py + alembic upgrade head | Done |
| T-04 | `data_policy` table + fail-closed lookup | REQ-AUTH-02 | T-03 | Query for a role with no policy row returns **zero** tables, not all tables | 1 | P0 (critical) | test_data_policy.py::test_default_deny | Done |
| T-05 | Semantic Catalog schema + seed classification | REQ-CATALOG-01 | T-02 | Every seed column has a `semantic_type` and `sensitivity` value | 2 | P0 | seed_semantic_catalog.py (25 cols classified) | Done |
| T-06 | Schema introspection service | REQ-NLSQL-01 | T-05 | Returns tables/columns/FKs for a given data source | 2 | P0 | test_schema_introspector.py | Done |
| T-07 | Sanitized-value grounding | REQ-NLSQL-01 | T-05 | Zero raw values from HIGH/MEDIUM sensitivity columns appear in generated examples | 2 | P0 (critical) | test_sanitized_grounding.py | Done |
| T-08 | Semantic Catalog retrieval API (policy-filtered) | REQ-CATALOG-01 | T-04, T-06 | A Viewer role's catalog response excludes tables it has no `data_policy` row for | 2 | P0 | test_schema_api.py | Done |
| T-09 | Prompt builder consumes catalog only | REQ-CATALOG-01 | T-08 | Prompt payload inspection shows zero raw-schema fields, only catalog fields | 2 | P0 | test_prompt_builder.py | Done |
| T-10 | Intent Analyzer: Unsupported detection | REQ-UNSUPP-01 | T-08 | 10/10 seeded "impossible" questions correctly refused with evidence-gap message | 3 | P0 | test_intent_analyzer.py::test_unsupported_detection_10_cases | Done |
| T-11 | Intent Analyzer: Unauthorized pre-check | REQ-AUTH-03 | T-04, T-08 | Sensitive-column question from unpermitted role refused before SQL generation | 3 | P0 (critical) | test_intent_analyzer.py::test_unauthorized_precheck | Done |
| T-12 | Ambiguity Engine | REQ-NLSQL-02 | T-08 | ≥80% of a 20-question ambiguous set correctly triggers clarification | 3 | P0 | test_ambiguity_engine.py (100% benchmark catch rate) | Done |
| T-13 | Clarification UI flow | REQ-NLSQL-02 | T-12 | Radio-button clarification renders real column names, not generic text | 3 | P0 | ClarificationCard.jsx + Intent Studio UI | Done |
| T-14 | SQL Generator (LLM proposal) | REQ-NLSQL-04 | T-09 | Produces `{sql, rationale}` for resolved questions | 4 | P0 | test_sql_generator.py | Done |
| T-15 | AST SELECT-only validator | REQ-SAFE-01 | T-14 | Rejects 100% of non-SELECT statements in a 20-statement test set | 4 | P0 (critical) | test_sql_validator.py (100% rejection rate) | Done |
| T-16 | Schema authorization (deny-by-default) | REQ-SAFE-02 | T-04, T-15 | A table with no `data_policy` row is rejected, not allowed | 4 | P0 (critical) | test_policy_enforcement.py::test_schema_deny | Done |
| T-17 | Column authorization | REQ-SAFE-02 | T-16 | Per-column check independent of table-level check | 4 | P0 (critical) | test_policy_enforcement.py::test_column_deny | Done |
| T-18 | Aggregate-function guard | REQ-AUTH-03 | T-17 | `AVG(salary)` rejected unless role has `aggregate_allowed=true` | 4 | P0 (critical) | test_policy_enforcement.py::test_aggregate_guard | Done |
| T-19 | Function/operator allowlist | REQ-SAFE-02 | T-17 | `pg_sleep()`-class functions rejected regardless of statement validity | 5 | P0 (critical) | test_function_allowlist.py (100% blocked) | Done |
| T-20 | Resource/cost pre-check (EXPLAIN-based) | REQ-SAFE-03 | T-19 | Pathological Cartesian join rejected before execution | 5 | P0 (critical) | test_resource_limits.py::test_cartesian_product_detection | Done |
| T-21 | Row-filter injection | REQ-AUTH-03 | T-17 | `data_policy.row_filter_sql` applied automatically, unremovable by the LLM's proposed SQL | 5 | P0 (critical) | test_row_filter_injection.py | Done |
| T-22 | Read-only DB role + timeout/row-limit sandbox | REQ-SAFE-04 | T-01 | Write attempt at engine level fails even if application-layer check somehow passed | 5 | P0 | test_resource_limits.py::test_execution_sandbox_row_cap | Done |
| T-23 | Full Policy Engine test suite (seeds Attack Lab) | REQ-SAFE-05 | T-15..T-22 | ≥40 adversarial cases, 100% blocked | 5 | P0 (critical) | test_full_policy_suite.py (45/45 blocked, 100%) | Done |
| T-24 | SQL Critic rule set | REQ-CRITIC-01 | T-23 | Flags `SUM(order_id)`-class smells in a 20-case test set at ≥85% precision | 6 | P0 | test_sql_critic.py (20-case semantic smell test set, 100% catch rate) | Done |
| T-25 | Critic UI (warning + suggested fix) | REQ-CRITIC-01 | T-24 | User can proceed/revise from the warning | 6 | P0 | SQLCriticCard.jsx + test_critic_api.py (persistence & 3-action UX) | Done |
| T-26 | Self-correction loop + E1–E7 taxonomy | REQ-CORR-01/02 | T-23 | Each error class individually reproducible via seeded failing queries | 7 | P0 | test_self_correction.py (per class) | Not Started |
| T-27 | E5 routing (auth errors never retried) | REQ-CORR-02 | T-26 | An authorization failure never triggers a regeneration attempt | 7 | P0 (critical) | test_self_correction.py::test_e5_no_retry | Not Started |
| T-28 | Result Validator | REQ-RESULT-01 | T-22 | Zero-row/cardinality/join-multiplication/NULL cases each individually detected | 7 | P0 | test_result_validator.py | Not Started |
| T-29 | Reliability Scorer | REQ-TRUST-01 | T-16,T-24,T-26,T-28 | Score is fully explainable by tracing to the 5 underlying stage outputs — no free parameter | 8 | P0 | reliability calibration script | Not Started |
| T-30 | Investigation Card UI | REQ-EVID-01 | T-29 | Evidence column always visible; SQL/Validation tabs one click away | 8 | P0 | usability test | Not Started |
| T-31 | Security Attack Lab (128-case suite + UI) | REQ-SECLAB-01 | T-23 | 100% blocked, `blocked_at_stage` recorded for each | 9 | P0 (critical) | test_security_attack_lab.py; CI hard gate | Not Started |
| T-32 | Evaluation Lab harness (baselines A–D) | REQ-EVALLAB-01 | T-14,T-23,T-26 | All 4 baselines runnable on the same question set without code changes | 9 | P0 | eval harness smoke run | Not Started |
| T-33 | Chart generation + switcher | REQ-VIS-01 | T-28 | Chart + table always paired, switch works for all chart types | 10 | P0 | usability test | Not Started |
| T-34 | PDF/Excel report generator | REQ-RPT-01 | T-30 | Report includes question, SQL, reliability breakdown, timestamp | 11 | P1 | test_pdf_report.py / test_excel_report.py | Not Started |
| T-35 | Optimization module (EXPLAIN default) | REQ-OPT-01 | T-22 | Suggestion output always includes a Confidence field, never a bare claim | 11 | P1 | test_optimizer.py | Not Started |
| T-36 | EXPLAIN ANALYZE opt-in mode | REQ-OPT-02 | T-35 | Only reachable by admin role, same timeout/row-limit as any query | 11 | P1 | test_optimizer_analyze_mode.py | Not Started |
| T-37 | JWT auth + RBAC UI | REQ-AUTH-01 | T-04 | Server-side enforcement verified independent of UI state | 12 | P0 | test_auth_and_rbac.py | Not Started |
| T-38 | Query History (rerun-by-default) | REQ-HIST-01 | T-30 | History item re-executes live; no stale-cache claim surfaces in UI | 12 | P1 | test_history_endpoint.py | Not Started |
| T-39 | Query Replay + provenance record | REQ-REPLAY-01 | T-29 | Replay detects and flags a since-changed schema in a test scenario | 12 | P0 | reproducibility check | Not Started |
| T-40 | Failure Observatory | REQ-FAILOBS-01 | T-26 | Aggregates ≥7 failure classes from real logged failures | 13 | P1 | manual review of aggregation output | Not Started |
| T-41 | Accessibility pass (WCAG AA) | — | T-30 | Contrast, keyboard nav, chart-table equivalence, icon+text+color verified | 13 | P1 | accessibility audit checklist | Not Started |
| T-42 | Full Evaluation Lab run (150–300 Qs) | REQ-EVAL-01/02 | T-32 | Safety violation rate = 0 (hard gate); results reported per category | 13 | P0 (critical) | evaluation_run record + report | Not Started |
| T-43 | Voice capture + pipeline wiring (P2) | REQ-VOICE-01 | T-13 | Feeds into Intent Analyzer identically to typed text | 14 | P2 | manual QA | Not Started |
| T-44 | Multi-step Planner Agent (P2) | REQ-AGENT-01 | T-23,T-32 | Every agent `execute_sql` call passes the same Policy Engine as the deterministic path | 14 | P2 | eval_compound_requests | Not Started |
| T-45 | CI pipeline incl. Security Attack Lab gate | — | T-31 | A single unblocked attack fails the build | 14 | P0 | CI config review | Not Started |
| T-46 | Load testing | — | T-45 | 50 concurrent sessions, latency targets per category met | 14 | P1 | k6/Locust report | Not Started |
| T-47 | Production deployment | — | T-45 | Deployed and reachable; smoke test passes | 14 | P0 | deployment log | Not Started |
| T-48 | Documentation + traceability map finalized | — | T-47 | Every REQ-ID in `10_Requirement_Traceability_Map.md` has a populated Evidence column | 14 | P1 | doc review | Not Started |
| T-49 | Demo packaging | — | T-48 | Demo leads with Evaluation Lab + Attack Lab results, not the feature list | 14 | P1 | rehearsal review | Not Started |

## 2. Risk & Blocker Log (updated)

| Date | Risk/Blocker | Impact | Mitigation | Status |
|---|---|---|---|---|
| | Policy Engine (T-15–T-23) takes longer than 2 weeks | High — blocks everything downstream | Do not compress Week 5; per Implementation Plan, Weeks 1–9 are never cut | Open |
| | Reliability Score perceived as "just another AI confidence number" in usability testing | Medium | Redesign Evidence Panel copy to explicitly name the 5 traceable sub-scores | Open |
| | Evaluation Lab shows non-zero safety violation rate | Critical — blocks M4/M5 | Return to Week 5 Policy Engine work; P2 features are cut, not the fix | Open |
| | LLM API cost overrun during 150–300 question benchmark runs | Medium | Cache Semantic Catalog lookups; run benchmark on cheaper model tier first pass | Open |

## 3. Metrics Dashboard (fill weekly, per category — not one blended number)

| Week | Simple exec. success | 2–3 join exec. success | Safety violation rate | Unauthorized exposure rate | Reliability score calibration (manual spot-check agreement) |
|---|---|---|---|---|---|
| 8 | | | | | |
| 9 | | | | | |
| 10 | | | | | |
| 13 (full benchmark) | | | | | |

## 4. Definition of Done (tiered by risk class — replaces v1.1's flat DoD)

**Base DoD (all tasks):** code merged to main, tests pass in CI, manually verified against the Acceptance Criteria column above, documentation updated.

**Additional, tier-specific requirements:**
- **Security-sensitive tasks** (Policy Engine, RBAC, function allowlist, row-filter injection — anything marked P0 (critical) above): requires 2 reviewers, no self-merge, and a passing entry in the Security Attack Lab suite (T-31) covering the relevant attack class.
- **AI/generation tasks** (SQL Generator, Ambiguity Engine, SQL Critic, Self-Correction): requires a passing regression-suite run *and* the relevant Evaluation Lab category showing no regression versus the prior run.
- **Performance tasks** (resource limits, execution sandbox, load testing): requires attached benchmark evidence (latency numbers, not "it felt fast").
- **Research-facing claims** (anything referenced as an "advantage" in `00_Research_Paper_Matrix.md`): requires a linked Evaluation Lab result before the claim can be upgraded from "designed contribution" to "demonstrated contribution," per `08_Rules.md` R9.2.

A task marked `Done` without its tier's additional requirement is a tracker error and must be reverted to `In Progress`.

## 5. Backlog (Post-v1)
Multi-lingual NL input, approved write-query workflow with human-in-the-loop, NoSQL connector, tokenized report sharing, result caching for history, fine-tuned domain-specific SQL model, scheduled/recurring reports.
