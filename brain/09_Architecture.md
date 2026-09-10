# Architecture Document — v1.2
## Intelligent SQL Assistant — "A Trustworthy Natural-Language Analytics Engine with Verification, Self-Correction and Evidence-Grounded Query Execution"

**Supersedes v1.1.** This revision incorporates the second audit's core thesis: **the LLM is not the protagonist — the verification system is.** The differentiator is not feature breadth (voice, multi-agent, multi-DB); it is a demonstrable, auditable trust pipeline: **Understand → Prove → Execute → Critique → Explain.**

## Change Log (v1.1 → v1.2)
1. Replaced the linear "generate → policy → execute" pipeline with the full Trust Engine: Intent Analyzer → Ambiguity Engine → Semantic Catalog → SQL Generator → Policy Engine → SQL Critic → Read-only DB → Result Validator → Evidence Panel → Reproducible Run.
2. Added a **Semantic Catalog** (typed, sensitivity-tagged schema representation) as the only thing the LLM ever sees — never raw schema.
3. Added a **SQL Critic** stage that semantically attacks generated SQL before execution (e.g., flags `SUM(order_id)`).
4. Added a **Result Validator** stage — SQL executing successfully is explicitly not treated as equivalent to the answer being correct.
5. Added an **Evidence Panel** and a formal, non-fabricated **Reliability Score** built from five checkable sub-scores, not a bare LLM-stated confidence percentage.
6. Added **Query Replay** as a first-class reproducibility artifact per query run.
7. Added a **Security Attack Lab** as a standing, visible adversarial test suite rather than only a documented claim.
8. Retained the v1.1 Policy Enforcement Layer and fail-closed authorization unchanged — this remains the non-negotiable safety boundary; the Trust Engine sits around it, not instead of it.

## 1. Architecture Style
Layered pipeline with a hard, deterministic authorization boundary in the middle. **Core principle: the LLM proposes; deterministic infrastructure authorizes, critiques, executes, and verifies.** No stage after the Policy Engine can be overridden by natural-language content.

## 2. High-Level Component Diagram

```
                              USER
                                │
                     ┌──────────▼──────────┐
                     │   API Gateway        │
                     │ Auth / RBAC / Rate   │
                     └──────────┬──────────┘
                                │
                     ┌──────────▼──────────┐
                     │  Intent Analyzer     │  classifies: Answerable / Ambiguous /
                     │                      │  Unsupported / Unauthorized (REQ-UNSUPP-01)
                     └──────────┬──────────┘
                                │
                     ┌──────────▼──────────┐
                     │  Ambiguity Engine    │  "revenue" -> gross/net/post-refund?
                     │                      │  "recently" -> 7/30/90 days?
                     └──────────┬──────────┘
                          resolved question
                                │
                     ┌──────────▼──────────┐
                     │  Semantic Catalog    │  typed, sensitivity-tagged schema
                     │  (Data Contract)     │  (REQ-CATALOG-01) — the ONLY schema
                     └──────────┬──────────┘  representation the LLM ever receives
                                │
                     ┌──────────▼──────────┐
                     │  SQL Generator (LLM) │  produces {sql, rationale} — a
                     │                      │  PROPOSAL, not an authorization
                     └──────────┬──────────┘
                                │
                     ┌──────────▼──────────┐
                     │   POLICY ENGINE      │  AST + schema/column/function auth +
                     │  (deny-by-default)   │  resource limits + row-filter injection
                     └──────────┬──────────┘  (unchanged from v1.1 §3.2 — this is
                                │              the actual authorization boundary)
                          authorized SQL
                                │
                     ┌──────────▼──────────┐
                     │    SQL CRITIC        │  attacks the query for semantic
                     │  (REQ-CRITIC-01)     │  smells: SUM(id-like column), suspect
                     └──────────┬──────────┘  GROUP BY, type-mismatched comparisons
                                │
                     ┌──────────▼──────────┐
                     │  Read-only Sandbox   │  timeout + row-limit, engine-level
                     │  (Execution)         │  read-only role (defense in depth)
                     └──────────┬──────────┘
                          error │  success
                    ┌───────────┴───────────┐
                    ▼                       ▼
          ┌──────────────────┐   ┌─────────────────────┐
          │ Self-Correction   │   │  Result Validator    │
          │ (E1-E7 taxonomy,  │   │  (REQ-RESULT-01):    │
          │  max 3 retries,   │   │  zero-row, cardinality│
          │  E5=auth never    │   │  explosion, join       │
          │  retried)         │   │  multiplication, NULLs │
          └─────────┬─────────┘   └──────────┬───────────┘
                    │ retry loops back to Policy Engine, never around it
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │   Reliability Scorer     │  5 sub-scores -> composite score
                    │   (REQ-TRUST-01)         │  (never a bare LLM % claim)
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        Visualization        Insights          Evidence Panel
              │                  │              (REQ-EVID-01)
              └──────────────────┼──────────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │   Reproducible Run        │  full provenance record
                    │   (REQ-REPLAY-01)         │  (schema snapshot, prompt
                    └────────────┬────────────┘  version, model, params,
                                 │                validation, plan, latency,
                                 ▼                result hash, correction history)
                          History / Audit
```

Reporting (PDF/Excel, P1) and the Optimization module (P1, EXPLAIN-based, EXPLAIN ANALYZE gated) attach after Visualization/Insights, unchanged in substance from v1.1. The P2 Planner Agent (voice, multi-step) is reached only via a Query Router branch for genuinely compound requests — every `execute_sql` call it makes still passes through the same Policy Engine + Critic + Result Validator; the agent has no special authority.

## 3. New Component Responsibilities (v1.2 additions)

| Component | Responsibility | Why it matters more than another feature |
|---|---|---|
| **Intent Analyzer** | Classifies every question as Answerable / Ambiguous / Unsupported / Unauthorized before any SQL is generated | Prevents hallucinated joins against tables/relationships that don't exist (REQ-UNSUPP-01) |
| **Semantic Catalog** | A typed, sensitivity-tagged representation of the schema (`amount: monetary, sensitive: NO`; `email: identifier, sensitive: HIGH`) — the only schema view the LLM ever receives | Moves sensitivity decisions out of ad-hoc prompt text and into a structured, auditable artifact the Policy Engine can also consult |
| **SQL Critic** | Runs a fixed set of semantic-smell checks on Policy-Engine-approved SQL before execution (e.g., aggregating an identifier column, suspicious GROUP BY, type-mismatched WHERE clauses) | Catches "technically executable, semantically wrong" queries that pure syntax/authorization checks cannot — this is the audit's strongest "wow factor" and directly targets result quality, not just safety |
| **Result Validator** | Runs statistical/structural sanity checks on the result set itself: zero rows, cardinality far outside expectation, join-multiplication artifacts, NULL explosion | Encodes "SQL success ≠ answer correctness" as an explicit pipeline stage rather than an assumption |
| **Reliability Scorer** | Composes a Reliability Score from five *checkable* sub-scores: schema grounding, join confidence, filter interpretation, execution validation, result sanity — each is a pass/fail/partial from an earlier stage, not a model-invented number | Gives "confidence" actual evidentiary backing instead of an LLM restating a percentage it cannot justify |
| **Evidence Panel** | Composes one auditable trail per answer: question → interpretation → schema evidence → SQL → validation results → result → reliability breakdown | This is the UI's signature surface (see `04_UI_UX_Design.md` §3) |
| **Query Replay** | Persists a full reproducibility package per run and can reconstruct/re-render it on demand | Turns the system from a chatbot into an experimentally reproducible platform — required for the Evaluation Lab (§7 below) to mean anything |
| **Security Attack Lab** | A fixed, versioned suite of adversarial inputs (structural: DROP/DELETE/UPDATE/UNION-escalation/unauthorized-table/unauthorized-column/Cartesian-join/dangerous-function; prompt-based: injection attempts) run against the live Policy Engine, with pass/fail displayed, not just asserted in docs | Converts "we have a security model" from a documentation claim into a running, re-runnable demonstration (target: 0% violation rate, exactly as `01_PRD.md` §7 requires as a hard gate) |
| **Failure Observatory** (P1) | Aggregates every failure by class (schema hallucination, join error, ambiguous intent, type mismatch, authorization rejection, timeout, semantic mismatch) and surfaces the most common problematic phrases | Shows the system "learning from failure" honestly — via classification and reporting, not a false "self-learning" claim |

## 4. Data Flow — Single Query (revised sequence)

```
User → Intent Analyzer: classify(question)
  case Unsupported -> return "cannot answer from available schema" + required evidence gap (no SQL attempt)
  case Unauthorized -> return "not permitted for your role" (checked against Semantic Catalog sensitivity tags, no SQL attempt)
  case Ambiguous -> Ambiguity Engine -> single targeted clarifying question -> resolved question
  case Answerable -> continue

Orchestrator → Semantic Catalog: fetch typed, sensitivity-tagged, policy-filtered schema view for this role
Orchestrator → LLM (SQL Generator): prompt(resolved question + catalog view) -> {sql, rationale}   [PROPOSAL ONLY]

Orchestrator → Policy Engine: AST check -> schema auth -> column auth -> function allowlist ->
                                resource/cost estimate -> row-filter injection
  case rejected -> "not authorized" (never silently reworked; not sent to Self-Correction)
  case approved -> continue

Orchestrator → SQL Critic: semantic-smell checks on approved SQL
  case smell detected -> annotate with a visible warning + suggested fix, still user-approvable to proceed or revise
  case clean -> continue

Orchestrator → Sandbox: execute (read-only, timeout, row-limit)
  case execution error -> Self-Correction Loop (E1-E7 taxonomy; E5=auth routes back to Policy Engine
                            as a rejection, not a retry; E1-E4/E6 retry through Policy Engine + Critic again, max 3)
  case success -> continue

Orchestrator → Result Validator: zero-row / cardinality / join-multiplication / NULL-explosion checks
  case anomaly -> flag in Evidence Panel, do not silently accept

Orchestrator → Reliability Scorer: compose 5 sub-scores -> composite score
Orchestrator → Evidence Panel + Visualization + Insights: assemble response
Orchestrator → Query Replay record: persist full provenance (schema_snapshot_id, prompt_version,
                                     model_name, params, validation_result, plan, latency, result_hash,
                                     correction_history)
Orchestrator → API Gateway → Client: render Answer Card with Reliability Score + Evidence tabs
```

## 5. Deployment Architecture
Unchanged from v1.1 §6 (load balancer, containerized FastAPI instances, managed Postgres for app metadata, customer business DB, object storage for reports).

## 6. Cross-Cutting Concerns
Unchanged from v1.1 §7, plus: the **Security Attack Lab** suite runs on every CI build against a seeded test database (not production) as a hard gate — a single unblocked attack fails the build, per `08_Rules.md` §7 (updated).

## 7. Why This Architecture Is the Actual Research Contribution

Restating the second audit's framing directly, because it should be the project's thesis statement, not a marketing line:

> **Research question:** Can execution feedback and deterministic policy enforcement improve the reliability and safety of LLM-generated SQL compared with conventional schema-prompted generation?

The Trust Engine components (Semantic Catalog, Policy Engine, SQL Critic, Result Validator, Reliability Scorer, Query Replay, Security Attack Lab) are the apparatus that lets this question be answered with the Evaluation Lab (`10_Requirement_Traceability_Map.md` REQ-EVALLAB-01, `02_TRD.md` §7) rather than asserted. Voice input and the multi-step agent remain P2 precisely because they do not bear on this question at all.
