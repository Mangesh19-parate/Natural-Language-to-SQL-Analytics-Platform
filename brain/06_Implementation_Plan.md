# Implementation Plan (Daily & Weekly) — v1.2
## Intelligent SQL Assistant

**Supersedes v1.1.** The audit correctly flagged the original 8-week/56-day plan as unrealistic once security, the Policy Engine, and a real evaluation framework are taken seriously — and the second audit added a full Trust Engine (Semantic Catalog, SQL Critic, Result Validator, Evidence Panel, Query Replay, Security Attack Lab, Evaluation Lab) as the actual P0 scope. This plan is extended to **14 weeks (98 days)** for a solo/small-team pace, with voice and the multi-step agent pushed to the very end as P2 and explicitly the first things cut if time runs out.

## Change Log (v1.1 → v1.2)
1. Extended from 8 weeks to 14 weeks.
2. Re-sequenced around the Trust Engine as the core P0 deliverable (Weeks 1–9), not an afterthought.
3. Voice and multi-agent (P2) moved to Weeks 13–14, explicitly cuttable.
4. Added dedicated weeks for the Policy Enforcement Layer, SQL Critic, Result Validator, Security Attack Lab, and the Evaluation Lab — none of which existed as scheduled work in v1.0/v1.1.
5. Milestones are now evidence-based (tied to `07_Tracker.md` acceptance criteria), not "10/10 sample questions work."

## Week-Level Overview

| Week | Theme | Key Deliverable | Tier |
|---|---|---|---|
| 1 | Foundations & environment | Repo, Docker, seed DB, app metadata schema | P0 |
| 2 | Semantic Catalog + schema introspection | Typed, sensitivity-tagged catalog; sanitized value grounding | P0 |
| 3 | Intent Analyzer + Ambiguity Engine | Answerable/Ambiguous/Unsupported/Unauthorized classification | P0 |
| 4 | SQL Generator + Policy Engine (part 1) | AST validation, schema/column authorization, deny-by-default | P0 (critical) |
| 5 | Policy Engine (part 2) + resource limits | Function allowlist, cost estimate, row-filter injection, aggregate-guard | P0 (critical) |
| 6 | SQL Critic | Semantic-smell detection (aggregate-on-identifier, suspicious GROUP BY, etc.) | P0 |
| 7 | Execution, Self-Correction, Result Validator | Read-only sandbox, E1–E7 taxonomy, result sanity checks | P0 |
| 8 | Reliability Scorer + Evidence Panel | Composite score from 5 sub-scores, Investigation Card UI | P0 |
| 9 | Security Attack Lab + Evaluation Lab (build) | Adversarial suite, 150–300 question benchmark harness | P0 (critical) |
| 10 | Visualization + chart tabs | Chart generation, table view, chart-type switcher | P0 |
| 11 | Reporting + Optimization module | PDF/Excel export, EXPLAIN-based suggestions (ANALYZE gated) | P1 |
| 12 | Auth, RBAC, History, Query Replay | JWT, fail-closed data_policy enforcement UI, replay screen | P1 |
| 13 | Failure Observatory + polish + accessibility | Failure aggregation, UI polish, WCAG pass | P1 |
| 14 | Voice + Multi-Agent (if time allows) + deployment | P2 features, load testing, deploy, docs, demo | P2 + deploy |

---

## Week 1 — Foundations & Environment
- Day 1: Confirm research matrix, PRD/TRD v1.2 sign-off, REQ-ID map reviewed.
- Day 2: Repo structure, Docker Compose skeleton, FastAPI + React hello-world.
- Day 3: Business schema + seed data (Employees/Customers/Orders/Products/Sales).
- Day 4: App metadata schema migrations (users, roles, sessions — Alembic).
- Day 5: `data_policy` table + fail-closed lookup function (deny-by-default, tested first before anything is built on top of it).
- Day 6: LLM provider smoke test (no schema access yet — just connectivity).
- Day 7: Buffer + Week 1 review.

## Week 2 — Semantic Catalog
- Day 8: Design `semantic_catalog` schema; classify seed DB columns by semantic_type/sensitivity.
- Day 9: Build schema introspection service (tables/columns/FKs).
- Day 10: Build sanitized-value grounding (distinct categorical examples only, never raw rows) — unit test that HIGH-sensitivity columns never appear in generated examples.
- Day 11: Build Semantic Catalog retrieval API, policy-filtered per role.
- Day 12: Wire prompt-builder to consume only the Semantic Catalog, never raw schema.
- Day 13: Integration test: verify LLM prompt payload contains zero raw PII for a seeded HIGH-sensitivity column.
- Day 14: Buffer + Week 2 review.

## Week 3 — Intent Analyzer + Ambiguity Engine
- Day 15: Design classification taxonomy (Answerable/Ambiguous/Unsupported/Unauthorized).
- Day 16: Implement Unsupported detection (no matching table/relationship in Semantic Catalog).
- Day 17: Implement Unauthorized pre-check against Semantic Catalog sensitivity tags (before SQL generation).
- Day 18: Implement Ambiguity Engine (metric/timeframe ambiguity detection using real column names).
- Day 19: Build clarification-question UI flow (radio-button style, per `04_UI_UX_Design.md` §3.2).
- Day 20: Test set: 30 questions across all 4 classifications; tune detection.
- Day 21: Buffer + Week 3 review.

## Week 4 — SQL Generator + Policy Engine (Part 1)
- Day 22: SQL Generator: LLM call producing `{sql, rationale}` as a proposal only.
- Day 23: AST statement-type validator (SELECT-only).
- Day 24: Schema authorization check against `data_policy` (deny-by-default; write the "no row = no access" test *first*).
- Day 25: Column authorization check (per-column, not just per-table).
- Day 26: Aggregate-function guard (block AVG/SUM/MAX/MIN on sensitive columns unless `aggregate_allowed`).
- Day 27: Integration test: attempt to query a HIGH-sensitivity column with no policy row — must be denied.
- Day 28: Buffer + Week 4 review.

## Week 5 — Policy Engine (Part 2) + Resource Limits (critical week — do not compress)
- Day 29: Function/operator allowlist (block sleep/filesystem/network functions, DB links, arbitrary UDFs).
- Day 30: Resource/cost estimate via lightweight `EXPLAIN` pre-check for large tables.
- Day 31: Row-filter injection (apply `row_filter_sql` from `data_policy` automatically).
- Day 32: Read-only DB role configuration (defense in depth, engine-level).
- Day 33: Timeout + row-limit enforcement on the execution sandbox.
- Day 34: Full Policy Engine integration test suite (this becomes the seed for the Security Attack Lab in Week 9).
- Day 35: Buffer + Week 5 review — **do not proceed to Week 6 until the Week 4–5 Policy Engine tests are green; this is the project's core safety boundary.**

## Week 6 — SQL Critic
- Day 36: Define semantic-smell rule set (aggregate-on-identifier, suspicious GROUP BY, type-mismatched filters, redundant joins).
- Day 37: Implement Critic as a post-Policy-Engine, pre-execution stage.
- Day 38: `sql_critic_findings` persistence + suggested-fix generation.
- Day 39: Critic UI (warning chip + "use suggested fix / proceed anyway / revise").
- Day 40: Test set: 20 deliberately semantically-wrong-but-executable queries; measure Critic catch rate.
- Day 41: Tune false-positive rate (Critic should not flag legitimate aggregations).
- Day 42: Buffer + Week 6 review.

## Week 7 — Execution, Self-Correction, Result Validator
- Day 43: Wire execution sandbox end-to-end (Policy Engine → Critic → Execute).
- Day 44: Self-correction loop: capture DB errors, classify into E1–E7.
- Day 45: E5 (authorization) routing: never retried, routed back as a policy rejection.
- Day 46: E1–E4/E6 retry loop (max 3), re-validated through full Policy Engine + Critic each retry.
- Day 47: Result Validator: zero-row, cardinality-outlier, join-multiplication, NULL-explosion checks.
- Day 48: `result_validation` persistence + anomaly flagging in the (not-yet-built) Evidence Panel.
- Day 49: Buffer + Week 7 review; run the ~50-question CI regression suite for the first time end-to-end.

## Week 8 — Reliability Scorer + Evidence Panel
- Day 50: Design 5 sub-score composition (schema grounding, join confidence, filter interpretation, execution validation, result sanity).
- Day 51: Implement scorer as a deterministic function over earlier-stage pass/fail/partial signals (never an LLM-invented number).
- Day 52: Persist `reliability_breakdown` on `query_history`.
- Day 53: Build Investigation Card UI (Answer + Reliability badge + Evidence column + tabs).
- Day 54: Wire SQL/Explanation/Validation tabs to real backend data.
- Day 55: Usability pass: do 2–3 test users correctly read the Reliability Score as evidence-based?
- Day 56: Buffer + Week 8 review — **Milestone M1 gate (see Milestones table).**

## Week 9 — Security Attack Lab + Evaluation Lab (build)
- Day 57: Compile the 128-attack structural suite (DROP/DELETE/UPDATE/UNION-escalation/unauthorized-table/unauthorized-column/Cartesian-join/dangerous-function) from Week 5's Policy Engine tests.
- Day 58: Compile the prompt-injection subset (10–20 adversarial NL phrasings).
- Day 59: Build `security_attack_log` + CI hard-gate wiring (per `08_Rules.md` R6.6).
- Day 60: Build Security Attack Lab UI screen (§3.6 of UI/UX doc).
- Day 61: Design the 150–300 question Evaluation Lab benchmark, categorized (simple/temporal/join/nested/ambiguous/adversarial/invalid/unauthorized/optimization).
- Day 62: Implement baseline variants A (plain LLM), B (schema-aware), C (+correction), D (proposed) as swappable pipeline configs.
- Day 63: Buffer + Week 9 review — **Milestone M2 gate.**

## Week 10 — Visualization
- Day 64: Chart-type selection heuristic.
- Day 65: Chart-spec generation (Plotly) + LLM fallback for ambiguous shapes.
- Day 66: Chart/Table tabs wired into Investigation Card.
- Day 67: Chart-type switcher UI.
- Day 68: Table view polish (pagination, sort, CSV copy).
- Day 69: Run the Evaluation Lab benchmark end-to-end for the first time (Baseline D only, sanity check).
- Day 70: Buffer + Week 10 review.

## Week 11 — Reporting + Optimization Module
- Day 71: PDF report generator (single query scope).
- Day 72: Excel report generator.
- Day 73: Session-scope report composer.
- Day 74: EXPLAIN-based optimization suggestions (default mode, evidence-formatted with Confidence field).
- Day 75: EXPLAIN ANALYZE opt-in mode (admin-gated, sandboxed, same timeout/row-limit as any query).
- Day 76: Optimize tab UI + admin-only ANALYZE control.
- Day 77: Buffer + Week 11 review.

## Week 12 — Auth, RBAC, History, Query Replay
- Day 78: JWT auth (login/refresh).
- Day 79: Role management UI + `data_policy` admin editor (with fail-closed default visible/enforced in the UI itself).
- Day 80: Query History UI (rerun-by-default).
- Day 81: Query Replay screen + provenance record wiring (`schema_snapshot_id`, `prompt_version`, `model_name`, `model_params`).
- Day 82: Replay-against-changed-schema warning logic.
- Day 83: Full RBAC integration test (including the aggregate-guard from Week 4).
- Day 84: Buffer + Week 12 review — **Milestone M3 gate.**

## Week 13 — Failure Observatory, Polish, Accessibility
- Day 85: `failure_log` aggregation + Failure Observatory UI (P1).
- Day 86: UI/UX polish pass (empty states, refusal-state styling, loading states).
- Day 87: Accessibility pass (WCAG AA — contrast, keyboard nav, chart-table equivalence, icon+text+color status).
- Day 88: Run full 150–300 question Evaluation Lab across all 4 baselines; record results.
- Day 89: Analyze results, write up findings (safety violation rate must be 0 — if not, this blocks Week 14 P2 work and forces a return to Week 5).
- Day 90: Buffer + Week 13 review — **Milestone M4 gate (evaluation results in hand).**

## Week 14 — P2 Features (if time allows) + Deployment
- Day 91: Voice capture integration (Web Speech API) — **first to cut if behind schedule.**
- Day 92: Voice → existing Intent Analyzer pipeline wiring.
- Day 93: Multi-step Planner Agent (compound requests only, routed via Query Router) — **second to cut if behind schedule.**
- Day 94: CI pipeline finalization (lint, unit, integration, regression, Security Attack Lab gate).
- Day 95: Load testing (k6/Locust, 50 concurrent sessions).
- Day 96: Docker production config + deploy (Render/Railway/AWS).
- Day 97: Documentation (README, API docs export, requirement traceability map finalized).
- Day 98: Demo rehearsal, record walkthrough, submit/present — **lead with the Evaluation Lab results and Security Attack Lab, not the feature list.**

---

## Milestones Summary (evidence-based, per audit's critique of v1.1's weak milestones)

| Milestone | Target Day | Exit Criteria (must have evidence, not just "it runs") |
|---|---|---|
| M1: Trust Engine core works | Day 56 | Investigation Card renders a real Reliability Score composed from 5 traceable sub-scores; Policy Engine deny-by-default test suite green; 0 raw PII observed in any LLM prompt payload (sampled) |
| M2: Security & Evaluation harness built | Day 63 | Security Attack Lab: 100% of compiled attacks blocked, logged with `blocked_at_stage`; Evaluation Lab can run all 4 baseline variants end-to-end on ≥20 pilot questions |
| M3: Full-featured P0/P1 platform | Day 84 | Auth/RBAC/History/Replay functional; a replayed query correctly detects a since-changed schema in a test case |
| M4: Evaluation results in hand | Day 90 | Full 150–300 question benchmark run across A/B/C/D baselines; safety violation rate = 0; results documented per category |
| M5: Production-ready (P2 optional) | Day 98 | Deployed, load-tested, documented; voice/agent included only if M1–M4 were on schedule |

**Hard rule carried over from the audit:** if the project is behind schedule at any milestone gate, the cut order is strictly **P2 first (voice, multi-agent), then P1 (reporting, optimization, failure observatory) — the Trust Engine (Weeks 1–9) and Evaluation Lab results are never cut**, since they are the actual research/portfolio contribution.
