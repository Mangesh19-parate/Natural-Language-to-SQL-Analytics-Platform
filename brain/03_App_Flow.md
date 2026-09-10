# App Flow Document — v1.2
## Intelligent SQL Assistant

**Supersedes v1.1.** Reorganized around the Trust Engine pipeline: **Understand → Prove → Execute → Critique → Explain.**

## 1. High-Level Flow (revised)

```
Login / Auth
   ↓
Role-Based Dashboard
   ↓
User Input (Text; Voice is P2)
   ↓
Intent Analyzer: Answerable / Ambiguous / Unsupported / Unauthorized
   │
   ├─ Unsupported → "Cannot answer from available schema" + required evidence gap shown (2.3b)
   ├─ Unauthorized → "Not permitted for your role" (checked against Semantic Catalog, no SQL attempt)
   ├─ Ambiguous → one targeted clarifying question → resolved question (2.3a)
   └─ Answerable → continue
        ↓
   Semantic Catalog Retrieval (policy-filtered, sensitivity-tagged — never raw schema)
        ↓
   SQL Generation (LLM proposal, not authorization)
        ↓
   Policy Engine (AST + schema/column/function auth + resource limits + row-filter injection)
   │
   ├─ Rejected → "Not authorized" shown immediately, no retry attempted (2.3d)
   └─ Approved → continue
        ↓
   SQL Critic (semantic-smell check) (2.3c)
   │
   ├─ Finding → visible warning + suggested fix; user chooses Proceed / Revise
   └─ Clean → continue
        ↓
   Read-only Execution (timeout + row-limit)
   │
   ├─ Execution error → Self-Correction Loop (E1–E7, max 3 retries; E5 routes back to Policy Engine as
   │                     a rejection, not a retry) (2.6)
   └─ Success → continue
        ↓
   Result Validator (zero-row / cardinality / join-multiplication / NULL-explosion) (2.6b)
        ↓
   Reliability Scorer (5 sub-scores → composite) (2.4b)
        ↓
   Answer Card: Answer + Reliability Score + Chart + Table + Evidence Panel + SQL + Explanation + Optimize + Replay
        ↓
   Optional: Export (PDF/Excel) / Add to Report / Ask Follow-up / Flag Incorrect / Replay
```

## 2. Screen-by-Screen Flow

### 2.1 Login / Access
Unchanged from v1.1: JWT auth, role resolved, role determines visible datasets and features per `data_policy`.

### 2.2 Dashboard Home
Central input box + starter questions. Sidebar adds two new entries vs. v1.1: **Security Attack Lab** (admin-visible) and **Evaluation Lab** (admin-visible, P1).

### 2.3 Ask a Question — Trust Engine stages surfaced to the user

**(a) Ambiguity clarification (new, first-class screen, not a follow-up afterthought):**
```
"Show me top customers by revenue"

⚠ Ambiguity detected
"Revenue" could mean:
  1. Gross order value
  2. Net revenue
  3. Revenue after refunds
Based on your schema, net_revenue is available.

[ Use net revenue ]   [ Choose different metric ]
```
This runs *before* any SQL is generated — fixes v1.1's flow where ambiguity handling was implied but not staged first.

**(b) Unsupported-question screen (new):**
```
Unsupported Question

I cannot answer this from the available database.

Required evidence: employee identity / employee-sales relationship
Available tables: customers, orders, products, sales
```
No SQL is attempted; no table/relationship is invented.

**(c) SQL Critic warning (new):**
```
⚠ Suspicious aggregation detected.
`order_id` is an identifier and is being summed.
Did you mean SUM(order_amount) or COUNT(order_id)?

[ Use suggested fix ]   [ Proceed anyway ]   [ Revise my question ]
```
Shown after Policy Engine approval, before execution.

**(d) Policy rejection (new, distinct from execution failure):**
```
🔒 Not authorized
This question requires access to: employees.salary
Your role (Viewer) does not have this permission.
```
This is never retried by regeneration — it's a policy decision, not a bug.

**(e) Normal success path (as v1.1, extended):** result renders as table + chart + a **Reliability Score** badge (e.g., `87/100`) + Evidence Panel tab.

### 2.4 Answer Card — Evidence Panel (new signature UI element)
```
QUESTION: "Which city had the highest sales last year?"

INTERPRETATION
year = 2025, metric = SUM(sales.amount), grouping = city

SCHEMA EVIDENCE
sales.amount → numeric | sales.city_id → cities.id | sales.created_at → date

SQL   [view]

VALIDATION
✓ Authorized  ✓ Read-only  ✓ Join validated  ✓ Date filter validated

RESULT
Mumbai — ₹8.42 Cr

RELIABILITY  91/100
  Schema grounding       HIGH
  Join confidence        HIGH
  Filter interpretation  MEDIUM  (⚠ "recent" interpreted as last 30 days)
  Execution validation   HIGH
  Result sanity check    HIGH
```
Every sub-score traces to a specific pipeline stage — never a bare LLM-stated number (per `08_Rules.md` R3.3).

### 2.5 Voice Input (P2, unchanged in substance from v1.1) — feeds into 2.3's Intent Analyzer exactly like typed text.

### 2.6 Self-Correction Flow (revised)
1. Execution fails → error classified into E1–E7.
2. If E5 (authorization) → routes to 2.3(d), never retried.
3. Otherwise → shown as:
```
ATTEMPT 1
SQL generated
Error: column `revenue_total` does not exist
      ↓
REASONING
Schema lookup found: `total_revenue`
      ↓
ATTEMPT 2
Corrected SQL
✓ Executed successfully
```
4. Capped at 3 retries; on persistent failure, a specific message + "Report this" (captures question + SQL + error class for the Failure Observatory).

### 2.6(b) Result Validation Flow (new)
```
SQL executed successfully
      ↓
Result Validator
      ↓
⚠ The query returned 1,284,231 rows for a question asking for "top 10 customers."
      ↓
Flagged in Evidence Panel — not silently accepted as correct.
```

### 2.7 Multi-Step Agent Flow (P2, unchanged in substance, reached only via Query Router for compound requests) — every `execute_sql` step inside still passes through 2.3's Policy Engine + Critic + Result Validator.

### 2.8 Query Optimization Flow (revised — EXPLAIN ANALYZE fix)
1. "Optimize" tab shows EXPLAIN-based (plan-only) evidence by default.
2. Output format includes a `Confidence: Low/Medium/High` field — never a bare "missing index" claim.
3. `EXPLAIN ANALYZE` (which executes) is available only via a separate admin-gated control, explicitly labeled as "this will run the query."

### 2.9 Report Generation Flow (revised — "shareable" claim removed)
Report is generated and downloadable by the owning user only. No share-link, recipient, or expiration-to-others flow exists in v1 (fixes v1.1's unimplemented "shareable" claim).

### 2.10 Query History Flow (revised — rerun-by-default, no cache claim)
Clicking a history item **re-runs the query live** by default (no result-cache guarantee in v1, fixing the v1.1 flow/schema mismatch).

### 2.11 Query Replay Flow (new)
```
QUERY RUN #1842
Question | SQL | Dialect | Schema snapshot | Prompt version | Model | Params
Validation result | Execution plan | Latency | Result hash | Correction history

[ Replay Query ]
```
Replaying reconstructs the full run using the recorded `schema_snapshot_id` and `prompt_version` — if the underlying schema has since changed, this is explicitly flagged ("schema has changed since this run") rather than silently re-executed against a different structure.

### 2.12 Security Attack Lab Flow (new, admin-visible)
```
SQL SECURITY LAB
Attack                          Result
────────────────────────────────────────
DROP TABLE users                BLOCKED (ast)
DELETE FROM orders              BLOCKED (ast)
UNION privilege escalation      BLOCKED (column_auth)
Unauthorized table access       BLOCKED (schema_auth)
Sensitive column extraction     BLOCKED (column_auth)
Heavy Cartesian join            BLOCKED (resource_limit)
Dangerous function (pg_sleep)   BLOCKED (function_allowlist)
Prompt injection (salary ask)   BLOCKED (policy_engine, not NL-derived)
────────────────────────────────────────
128 attacks · 128 blocked · Violation rate 0.00%
```
Run on-demand or viewed from the latest CI run (per `08_Rules.md` R6.6, this suite gates every build).

### 2.13 Failure Observatory Flow (P1, new)
```
FAILURE OBSERVATORY
Schema hallucination      31   Join error              22
Ambiguous intent          18   Type mismatch            11
Authorization rejection    9   Timeout                   6
Semantic mismatch         14

Most common failure: Ambiguous business terminology
Top problematic phrase: "active customer"
Recommended intervention: extend Semantic Catalog + clarification rule
```

### 2.14 Evaluation Lab Flow (P1, new)
```
EVALUATION LAB
Benchmark: 240 questions, 10 categories
Baselines: A (plain LLM) · B (schema-aware) · C (+ self-correction) · D (proposed)

Category         A      B      C      D (proposed)
Simple          71%    88%    89%    93%
Joins (3+)       34%    52%    61%    77%
Ambiguous        —      —      —     81% clarification accuracy
Adversarial      —      —      —     0% violation rate
```

## 3. Error & Edge-Case Flows (updated)
- Ambiguous question → clarification (2.3a), before generation, not after.
- Unsupported question → explicit refusal with evidence gap (2.3b), never a hallucinated join.
- Policy rejection → explicit "not authorized" (2.3d), distinct from execution failure, never retried.
- Session timeout: unchanged from v1.1 (silent refresh, draft preserved).
- LLM/provider outage: unchanged from v1.1 (graceful degradation, retry button).

## 4. State Diagram (Query Lifecycle, revised)

```
[Idle] → [Classifying Intent]
            ├─ Unsupported → [Refused: Evidence Gap] → [Idle]
            ├─ Unauthorized → [Refused: Policy] → [Idle]
            ├─ Ambiguous → [Clarifying] → [Classifying Intent] (resolved)
            └─ Answerable
                  ↓
            [Retrieving Semantic Catalog] → [Generating SQL] → [Policy Engine]
                                                                    │
                                                    rejected ───────┘→ [Refused: Policy] → [Idle]
                                                                    │
                                                            approved ┘
                                                                    ↓
                                                            [SQL Critic]
                                                                    ↓
                                                            [Executing]
                                                  │                        │
                                          error ──┘                        └── success
                                             ↓                                    ↓
                                    [Self-Correcting]                  [Validating Result]
                                    (E1-E4,E6; E5→Refused:Policy)                 ↓
                                    max 3, else [Failed]                [Scoring Reliability]
                                                                                    ↓
                                                                        [Rendering Evidence Panel]
                                                                                    ↓
                                                                        [Idle] (awaiting next question)
```
