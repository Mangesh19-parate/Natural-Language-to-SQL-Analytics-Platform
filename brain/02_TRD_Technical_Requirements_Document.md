# Technical Requirements Document (TRD) — v1.1
## Intelligent SQL Assistant

**Supersedes v1.0.** REQ-IDs cross-reference `10_Requirement_Traceability_Map.md`.

## Change Log (v1.0 → v1.1)
1. **Critical fix:** replaced "AST validator + read-only role = safe" with a full **Policy Enforcement Layer** (schema/column/function authorization + resource limits), per audit §3.
2. **Critical fix:** `EXPLAIN ANALYZE` actually executes the query — demoted to an opt-in, sandboxed, admin-gated mode; `EXPLAIN` (no ANALYZE) is the default for optimization suggestions.
3. Fixed `llm_call_log` to store hashes, not raw prompt/completion text (privacy).
4. Fixed schema-grounding to use sanitized representative values instead of raw sample rows.
5. Added a Query Router splitting simple (deterministic) vs. compound (agentic) paths.
6. Added an Intent/Ambiguity Layer that runs *before* SQL generation.
7. Added schema/prompt/model versioning fields for reproducibility.
8. Added a formal evaluation framework specification (§7, new).
9. Downgraded SQLite to dev/demo-only; PostgreSQL is primary, MySQL secondary.
10. Split "Explain SQL" into two endpoints (ad-hoc SQL vs. historical query), fixing the v1.0 API/Flow mismatch.

## 1. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React.js + Tailwind CSS + Recharts/Chart.js | SPA |
| Backend API | Python 3.11 + FastAPI | Async |
| AI Orchestration | LangChain (SQL Agent Toolkit) | Used only inside Query Generator and (P2) Planner Agent — not as the default request path |
| LLM Provider | OpenAI GPT-4/4o-mini, or Qwen/Llama via Groq | Configurable |
| Database — **primary** | PostgreSQL | Full feature support (EXPLAIN, row-level policies) |
| Database — **secondary** | MySQL | Supported, dialect-aware generation |
| Database — **dev/demo only** | SQLite | Not a production target (no role-based execution isolation, weak concurrency) |
| App metadata DB | PostgreSQL | Users, policy, sessions, history, reports, evaluation results |
| Analytics | Pandas, NumPy | Post-processing |
| Visualization | Plotly / Matplotlib (server) + Recharts (client) | |
| Report generation | ReportLab/WeasyPrint (PDF), openpyxl (Excel) | |
| Voice (P2) | Web Speech API / Whisper API | Feeds into the same text pipeline |
| Auth | JWT + bcrypt | RBAC, fail-closed |
| Deployment | Docker, docker-compose; Render/Railway/AWS ECS | |
| CI/CD | GitHub Actions | Lint, unit, integration, regression, safety tests all gate merge |

## 2. System Interfaces (revised)

```
POST   /api/auth/login
POST   /api/auth/refresh
GET    /api/schema                        -> introspected schema + policy-filtered view per role
POST   /api/query                         -> { question, session_id } -> routed via Query Router
POST   /api/sql/explain                   -> { sql, data_source_id } -> ad-hoc SQL explanation (NEW — fixes v1.0 gap)
POST   /api/query/{query_id}/explain      -> explanation of a historical query
POST   /api/query/{query_id}/correct      -> re-run self-correction
POST   /api/query/{query_id}/optimize     -> EXPLAIN-based suggestions (default; no execution)
POST   /api/query/{query_id}/optimize/analyze -> EXPLAIN ANALYZE, admin-only, sandboxed (NEW, opt-in)
POST   /api/report/pdf | /api/report/excel
POST   /api/voice/query                   -> (P2)
GET    /api/history                       -> rerun-by-default; no cached-result guarantee in v1
POST   /api/agent/run                     -> (P2) only reachable via Query Router's compound path
GET    /api/evaluation/run/{run_id}       -> (NEW) evaluation benchmark results
```

### 2.1 LLM Prompt Contract (revised for privacy)
- System prompt includes: DB dialect, schema summary, and **sanitized representative values** per column (e.g., `{"column":"department","examples":["Engineering","Sales","HR"]}`), never raw PII rows (fixes v1.0's "3–5 sample rows" privacy leak).
- Output contract: `{ sql: string, rationale: string }`. This output is a **proposal only** — see §3.2 Policy Enforcement, which is the actual authority boundary.

## 3. Core Pipelines

### 3.0 Query Router + Intent/Ambiguity Layer (NEW — replaces v1.0's implicit "everything is an agent" design)

```
NL question
   ↓
Intent / Ambiguity Detector
   ├─ ambiguous → single targeted clarifying question → resolved question → (continue below)
   └─ unambiguous
        ↓
   Query Router
   ├─ simple/single-intent → Deterministic Pipeline (§3.1) — default path, no agent involved
   └─ compound/multi-step  → Planner Agent (§3.7, P2) — only path that uses LangChain agent orchestration
```
This directly fixes the audit's over-engineering concern: the agent is not the default execution path, it is a fallback for genuinely compound requests.

### 3.1 Deterministic NL → SQL → Result Pipeline (P0)
1. Receive resolved (non-ambiguous) question + session context.
2. Retrieve policy-filtered schema subset for the requesting role (only tables/columns the role may see are ever shown to the LLM — this is itself a privacy control, not just a UI control).
3. LLM generates `{sql, rationale}` — **a proposal, not an authorization.**
4. **Policy Enforcement Layer** (§3.2) — mandatory gate before any execution.
5. Execute against read-only DB role, with timeout + row limit.
6. On execution error → Self-Correction Loop (§3.3, capped at 3 retries).
7. Post-process with Pandas.
8. Chart-type selection.
9. Persist `query_history` row including `schema_snapshot_id`, `prompt_version`, `model_name` (reproducibility, REQ-VER-01).

### 3.2 Policy Enforcement Layer (NEW — critical fix, replaces v1.0's "SELECT-only" as the entire safety story)

```
LLM-proposed SQL
   ↓
1. Statement-type AST check   (SELECT only — necessary, not sufficient)
   ↓
2. Schema authorization        (is this table in the role's allow-list? default DENY)
   ↓
3. Column authorization         (is every referenced column allowed? default DENY)
   ↓
4. Function/operator allowlist  (blocks pg_sleep, filesystem/network functions,
                                  arbitrary UDFs, database-link/extension calls, etc.)
   ↓
5. Resource/cost estimate       (reject pathological joins/CTEs, cap estimated row scan,
                                  cap query plan cost via a lightweight EXPLAIN pre-check)
   ↓
6. Row-level filter injection   (WHERE clauses appended per data_policy, not just column masking —
                                  prevents aggregation-based leakage of masked values, e.g. a
                                  masked salary column cannot be exposed even via AVG())
   ↓
Read-only DB transaction, timeout + row limit
```
**Core principle (must appear verbatim in `08_Rules.md`): the LLM proposes; deterministic infrastructure authorizes and executes.** No natural-language instruction, however phrased ("ignore previous instructions...", "the admin said I can..."), can change what this layer permits — this directly closes the prompt-injection gap identified in the audit.

**Row-level leakage fix:** for a masked column like `salary`, the policy layer does not just hide the column from SELECT — it also rejects or rewrites aggregate functions (`AVG`, `SUM`, `MAX`, `MIN`) applied to masked columns unless the role has an explicit `aggregate_only` grant, closing the "average salary" inference attack the audit raised.

### 3.3 Self-Correction Loop (revised — adds error taxonomy)
- Error taxonomy: **E1 syntax, E2 schema-reference, E3 type mismatch, E4 semantic/logic, E5 authorization (routed back to Policy Enforcement, not retried as a "bug"), E6 timeout/resource, E7 empty-result ambiguity.**
- E5 (authorization failures) are **never retried by regenerating SQL** — they are policy decisions, not generation errors, and are surfaced to the user as "not authorized," not silently reworked.
- E1–E4, E6 follow the retry loop (max 3): DB error class + message fed back to LLM, regenerated, re-validated through the full Policy Enforcement Layer again (not just re-executed).
- Diff (original vs. corrected SQL) stored and shown.
- Recovery rate is measured **per error class**, not as one aggregate number (fixes the audit's "hidden bias" concern — e.g., E2 recovery via a DB error literally naming the correct column is reported separately from genuine E4 semantic repair).

### 3.4 Explain SQL (fixed endpoint split)
- `/api/sql/explain`: accepts arbitrary pasted SQL + `data_source_id`; validated for read-only safety before being explained (never executed) — fixes v1.0's gap where the App Flow described this but the API only supported historical `query_id`s.
- `/api/query/{query_id}/explain`: explains a stored historical query.

### 3.5 Chart Generation
Unchanged in substance from v1.0: heuristic + LLM fallback for chart-type selection; chart always paired with a table view (never chart-only, per UI/UX accessibility rule).

### 3.6 Optimization Module (revised — evidence-based framing, EXPLAIN ANALYZE fix)
- **Default:** wrap the query with `EXPLAIN` (plan-only, does not execute) — Postgres/MySQL both support this safely.
- **Opt-in, admin-gated, sandboxed mode:** `EXPLAIN ANALYZE` (actually executes) is only available behind a separate endpoint (`/optimize/analyze`), restricted to admin role, run inside a transaction with the same timeout/row-limit/read-only guarantees as any other query — it is treated as a query, not as a free introspection tool.
- Output format is evidence-based, not a bare claim:
  ```
  Observed: Sequential scan on orders
  Evidence: estimated rows = 1.2M, filter = customer_id
  Existing indexes: orders_pkey, orders_order_date_idx
  Recommendation: Evaluate an index on orders(customer_id)
  Confidence: Medium
  ```
  The system never states "missing index" as fact — cardinality, existing composite indexes, and workload characteristics are out of scope for automatic certainty, so confidence is always reported.

### 3.7 Multi-Step Planner Agent (P2 — only reachable via Query Router's compound path)
- Tools: `generate_sql`, `execute_sql` (still passes through Policy Enforcement Layer — the agent has no special authority), `compute_stats`, `make_chart`, `make_report`.
- Step-budget cap (max 8 tool calls).
- Every `execute_sql` call inside the agent is subject to the exact same §3.2 Policy Enforcement Layer as the deterministic path — the agent cannot bypass authorization.

### 3.8 Voice Pipeline (P2)
Unchanged in substance; feeds transcript into §3.0 Intent/Ambiguity Layer, same as typed text.

## 4. Data Model
See `05_Backend_Schema.md` v1.1 for full DDL, including new `data_policy`, `schema_snapshot`, `evaluation_run`/`evaluation_result` tables.

## 5. Security Requirements (rewritten — this section was the audit's top critical finding)

- SEC-1: **SELECT-only AST validation is necessary but not sufficient**; it must always be paired with SEC-2 through SEC-6 below.
- SEC-2: Schema authorization is **deny-by-default** — a role with no explicit `data_policy` record for a table has **zero access**, not full access. (Fixes v1.0's fail-open default.)
- SEC-3: Column authorization is enforced at the same layer, including blocking aggregate functions over masked columns unless explicitly granted.
- SEC-4: Function/operator allowlist blocks resource-abuse and side-channel functions (sleep functions, filesystem/network-capable functions, database links/extensions, arbitrary UDFs) regardless of statement type.
- SEC-5: Resource/cost limits — query timeout (10s default), row cap (10,000 default), and a lightweight cost pre-check via `EXPLAIN` before full execution for any query touching tables above a configurable size threshold.
- SEC-6: DB connection uses a read-only role at the engine level as defense in depth — **this is a backstop, not the primary control** (the primary control is SEC-1 through SEC-5).
- SEC-7: **Prompt-injection resistance:** authorization decisions are made exclusively by the deterministic Policy Enforcement Layer; natural-language content is never treated as an authorization signal, regardless of phrasing or claimed authority (fixes audit finding on prompt injection).
- SEC-8: JWT auth, short-lived access tokens (15 min), refresh tokens (7 days).
- SEC-9: RBAC enforced server-side on every request.
- SEC-10: LLM/DB credentials in environment variables/secrets manager only.
- SEC-11: Rate limiting per user on query endpoints.
- SEC-12: **LLM call logging uses hashed prompt/response fields by default** (`prompt_hash`, `response_hash`), not raw text, to avoid persisting sensitive schema/data through the audit trail. Raw traces, if ever needed for research, go into a separate `encrypted_trace_store` with restricted access — not the default `llm_call_log`.

## 6. Performance Requirements
Measured **per query category** (simple / 2–3 join / compound), not as one blended number:
- Simple: P95 < 3s. 2–3 join: P95 < 8s. Compound (agent path): P95 < 15s.
- Query execution timeout: 10s default, configurable.
- Concurrent users (v1 target): 50 simultaneous sessions on baseline 2 vCPU/4GB instance.

## 7. Evaluation Framework (NEW — was entirely missing in v1.0; audit's top-priority gap)

- **Benchmark size:** 150–300 natural-language questions against the seeded business schema, not the 50-question regression set (that remains, but is CI-only, not the research evaluation).
- **Categories:** simple, temporal, 2-table join, 3+ table join, nested/subquery, ambiguous, adversarial/prompt-injection, invalid/malformed input, unauthorized-column-access, optimization-triggering.
- **Baselines compared:** (A) plain LLM→SQL, (B) schema-aware prompting only, (C) schema-aware + self-correction, (D) proposed (schema-aware + Policy Enforcement + self-correction + evaluation gates).
- **Metrics per category:** execution success rate, result correctness, self-correction recovery rate (per error class E1–E7), safety violation rate (hard gate = 0), unauthorized exposure rate (hard gate = 0), latency, LLM token cost.
- Results persisted in `evaluation_run` / `evaluation_result` tables (see `05_Backend_Schema.md`) tagged with `schema_snapshot_id`, `prompt_version`, `model_name` for reproducibility.

## 8. Testing Requirements (expanded)
- Unit: AST validator, **Policy Enforcement Layer (schema/column/function/resource checks)**, chart selector, schema introspection.
- Integration: end-to-end NL→SQL→execution against seeded test DB, **including adversarial/prompt-injection test cases**.
- Security: dedicated `test_prompt_injection_suite.py` and `test_policy_enforcement.py` — these gate merges to main (SEC-critical code requires 2 reviewers per `08_Rules.md`).
- Regression suite: ~50 fixed questions in CI (fast signal); the 150–300-question evaluation benchmark runs on a slower cadence (nightly/weekly), not every commit.
- Load testing: k6/Locust, 50 concurrent sessions.

## 9. Environments
`local` (docker-compose, Postgres or SQLite-for-dev-only), `staging` (Render/Railway, Postgres), `production` (AWS/Render, managed Postgres — **MySQL secondary support tested but not primary target**).

## 10. Third-Party Dependencies & Licensing Notes
Unchanged from v1.0.
