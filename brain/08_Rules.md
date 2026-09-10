# Rules Document — v1.2
## Intelligent SQL Assistant

**Supersedes v1.1.** Binding rules. Any exception must be explicitly documented and approved. Document precedence: `RULES > TRD > ARCHITECTURE > PRD > BACKEND SCHEMA > APP FLOW > UI/UX > IMPLEMENTATION PLAN` (see `10_Requirement_Traceability_Map.md`).

## 0. Core Design Principle (new — the project's central sentence)

> **The LLM proposes. Deterministic infrastructure authorizes, critiques, executes, and verifies.**

No natural-language instruction, however phrased ("ignore previous instructions," "the admin approved this," "this is for a demo so skip the check"), can change what the Policy Engine permits, what the SQL Critic flags, or what the Result Validator accepts. This principle overrides every other rule in this document if a conflict is ever found.

## 1. Data Safety Rules
- R1.1: The system never executes `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`, or any DDL/DML. AST-level SELECT-only validation is **necessary but not sufficient** — it must always run together with R1.2–R1.6.
- R1.2: Schema and column authorization is **deny-by-default**: a role with no explicit `data_policy` record for a table/column has zero access. This is fail-closed, not fail-open.
- R1.3: A function/operator allowlist blocks resource-abuse and side-channel functions (sleep/delay functions, filesystem- or network-capable functions, database links/extensions, arbitrary UDFs) regardless of statement type.
- R1.4: Aggregate functions (`AVG`, `SUM`, `MAX`, `MIN`, `COUNT DISTINCT`) over a masked/sensitive column are rejected unless the role has an explicit `aggregate_only` grant — this closes the "average salary" inference path around simple column masking.
- R1.5: Every executed query has a hard timeout (default 10s) and a hard row-return cap (default 10,000 rows), plus a pre-execution cost estimate via `EXPLAIN` for tables above a configured size threshold.
- R1.6: The database connection used for execution is a **read-only role at the engine level**, as defense in depth — this is a backstop, not the primary control (R1.1–R1.5 are primary).
- R1.7: `EXPLAIN ANALYZE` (which executes the query) is never run as part of default optimization suggestions. It is available only via a separate, admin-gated, opt-in endpoint, subject to the same timeout/row-limit/read-only guarantees as any other query.
- R1.8: Suggested optimization DDL (e.g., `CREATE INDEX`) is always copyable text only — never auto-executed.

## 2. Intent, Ambiguity & Semantic Catalog Rules (new)
- R2.1: Every question is classified as **Answerable / Ambiguous / Unsupported / Unauthorized** by the Intent Analyzer before any SQL is generated.
- R2.2: **Unsupported** questions (no table/relationship in the schema can answer them) must never produce a hallucinated join or invented table — the system states what evidence would be required and lists the available tables instead.
- R2.3: **Unauthorized** questions are rejected using the Semantic Catalog's sensitivity tags before SQL generation is even attempted, not only after generation via the Policy Engine (defense in depth: two independent checks, not one).
- R2.4: **Ambiguous** questions get exactly one targeted clarifying question, phrased using the Semantic Catalog's actual column/metric names (e.g., "net_revenue is available — use that?"), not a generic "can you clarify?"
- R2.5: The LLM is never given raw schema directly — it only ever receives the Semantic Catalog's typed, sensitivity-tagged, policy-filtered view for the requesting role. Raw sample rows containing PII are never sent to the LLM provider (schema-grounding uses sanitized representative values only).

## 3. SQL Critic & Result Validation Rules (new)
- R3.1: Every Policy-Engine-approved SQL query is passed through the SQL Critic before execution. The Critic's findings are advisory and **visible**, not silently auto-fixed — the user sees the warning and the suggested correction and can choose to proceed or revise.
- R3.2: SQL execution succeeding is never treated as equivalent to the answer being correct. The Result Validator runs on every result set (zero-row, cardinality-outlier, join-multiplication, NULL-explosion checks) and any anomaly is surfaced in the Evidence Panel, never silently hidden.
- R3.3: The Reliability Score shown to the user is always composed from the five checkable sub-scores (schema grounding, join confidence, filter interpretation, execution validation, result sanity) produced by earlier pipeline stages. The system must never display a bare LLM-generated confidence percentage that cannot be traced to one of these five sub-scores.

## 4. Self-Correction Rules
- R4.1: Self-correction is capped at 3 retries.
- R4.2: Error taxonomy E1–E7 (syntax, schema-reference, type, semantic, authorization, timeout/resource, empty-result-ambiguity) is recorded for every failure. **E5 (authorization) is never retried by regenerating SQL** — it is a policy decision, routed back as a rejection, and shown to the user as "not authorized."
- R4.3: Every retry is re-validated through the full Policy Engine and SQL Critic again — a corrected query gets no special trust just because it is a retry.
- R4.4: Recovery rate is always reported per error class, never as one blended number (avoids masking that some "recoveries" are trivial, e.g. a DB error literally naming the correct column).

## 5. AI/LLM Usage Rules
- R5.1: Every LLM-generated SQL query passes the full Policy Engine (not just an existence check) before execution.
- R5.2: The self-correction loop is capped at 3 retries; after that, the system fails gracefully with a specific message.
- R5.3: LLM call logs store **hashed** prompt/response fields (`prompt_hash`, `response_hash`) by default, not raw text — raw traces, if ever needed for research, go into a separate `encrypted_trace_store` with restricted access.
- R5.4: The system never fabricates data. If a query returns no rows, or the Intent Analyzer classifies the question Unsupported, the UI states this explicitly.
- R5.5: When ambiguity is detected, the system asks one targeted clarifying question rather than guessing silently (see R2.4).

## 6. Security & Access Rules
- R6.1: All API endpoints require a valid JWT except `/api/auth/login`.
- R6.2: RBAC is enforced server-side on every request; the frontend hiding a feature is not access control.
- R6.3: Credentials/API keys/secrets live only in environment variables or a secrets manager.
- R6.4: Passwords are hashed with bcrypt or stronger.
- R6.5: Rate limiting applies per user on query endpoints.
- R6.6 (new): The **Security Attack Lab** suite (structural attacks: DROP/DELETE/UPDATE/UNION-escalation/unauthorized-table/unauthorized-column/Cartesian-join/dangerous-function; prompt-based: injection attempts) runs on every CI build against a seeded test database. A single unblocked attack **fails the build** — this is a hard gate, not a warning.
- R6.7 (new): Prompt-injection resistance is structural, not detection-based: authorization comes exclusively from the Policy Engine's deterministic checks against the requesting role's `data_policy`, never from parsing the user's natural-language text for claimed permissions.

## 7. Development Rules
- R7.1: No feature is `Done` without unit + integration + regression evidence per `02_TRD.md` §8.
- R7.2: Any change touching SQL generation must run against the fixed regression suite before merge; any change touching the Policy Engine, SQL Critic, or authorization logic requires **2 reviewers**, no self-merge (security-critical).
- R7.3: Every user-facing feature has a corresponding entry in `03_App_Flow.md` and `04_UI_UX_Design.md` before implementation begins.
- R7.4: Commits/PRs reference the Tracker task ID and, where applicable, the REQ-ID from `10_Requirement_Traceability_Map.md`.

## 8. UX & Trust Rules
- R8.1: Self-correction is always visibly disclosed (attempt 1 → error → reasoning → attempt 2), never silently swapped.
- R8.2: Charts always have a corresponding tabular data view.
- R8.3: Exported reports include the natural-language question, the SQL used, the Reliability Score breakdown, and a generation timestamp.
- R8.4: Voice input (P2) always has a visible transcript confirmation step before submission.
- R8.5 (new): The Evidence Panel (question → interpretation → schema evidence → SQL → validation → result → reliability) is available for every answer, not an optional add-on — it is the system's core trust surface.

## 9. Academic Integrity / Research Rules
- R9.1: The base paper and all reference papers are cited accurately; match-percentage claims must use the reproducible overlap-dimension method in `00_Research_Paper_Matrix.md`, never an unexplained single number.
- R9.2: Any "advantage over prior work" claim is labeled a **designed contribution** until it has a passing entry in the Evaluation Lab (`02_TRD.md` §7) — at which point, and only then, it may be called a **demonstrated contribution**.
- R9.3: The research question is explicit and singular: *can execution feedback and deterministic policy enforcement improve reliability/safety of LLM-generated SQL versus conventional schema-prompted generation?* All evaluation design serves this question.

## 10. Operational Rules
- R10.1: Production deployments require a passing CI run, including the Security Attack Lab hard gate.
- R10.2: Any incident where a write-attempt bypasses R1.1 (even if ultimately blocked) is logged and reviewed within 24 hours as a security event.
- R10.3: LLM provider/model changes are tracked and re-evaluated against the Evaluation Lab within 5 business days, since a model change can shift execution accuracy, safety-violation rate, or reliability calibration.
