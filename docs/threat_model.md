# TrustSQL / Intelligent SQL Assistant — Threat Model & Security Architecture

This document formalizes the assets, actors, trust boundaries, threat scenarios, and deterministic security mitigations implemented in TrustSQL (Principle R0 & Rule R1.1–R1.6).

---

## 1. System Assets

| Asset ID | Asset Name | Description | Sensitivity |
| :--- | :--- | :--- | :--- |
| **A1** | **Customer / Business Data** | Relational tables in underlying business data sources | High (Restricted by Role) |
| **A2** | **Semantic Schema & Catalog** | Metadata describing table/column semantics, types, descriptions | Internal / Governed |
| **A3** | **Security & Access Policies** | Table, column, row filter, and aggregate permissions | Critical (Integrity-Sensitive) |
| **A4** | **Execution Provenance & Replay** | Query history, AST hashes, schema snapshots, result SHA-256 | Internal (Audit Trail) |
| **A5** | **Authentication Credentials** | JWT signing keys, user password hashes, database connection secrets | Critical (Confidential) |

---

## 2. Actors & Roles

| Actor | Role ID | Capabilities & Trust Level |
| :--- | :--- | :--- |
| **Admin** | `1` | Full administrative, governance, attack simulation, benchmark execution, policy configuration. |
| **Analyst** | `2` | Natural language to SQL query generation, ad-hoc execution against authorized tables/columns. |
| **Viewer** | `3` | Read-only access to pre-approved aggregated views and self-owned query history. |
| **Untrusted LLM** | N/A | External generative AI provider. **Zero trust**: output is treated as unvalidated candidate text. |
| **Anonymous Caller** | N/A | Unauthenticated internet actor. Restricted exclusively to `/api/auth/login`, `/api/auth/refresh`, `/api/health`. |

---

## 3. Trust Boundaries & Invariants

```text
               [ Untrusted Internet Client ]
                             │  (HTTP / Bearer JWT)
   ══════════════════════════╪═════════════════════════════════════  [Trust Boundary 1: API Ingress]
                             ▼
                    [ FastAPI Auth Middleware ]
                      - JWT Signature & Expiry
                      - Revocation Cache / DB Gate
                      - Effective Role Resolution (Server-Side)
                             │
   ══════════════════════════╪═════════════════════════════════════  [Trust Boundary 2: Generator & LLM]
                             ▼
                    [ SQL Generator Service ]
                      - Authorized Catalog Injection Only
                      - Prompt Hardening & Anti-Injection
                      - Raw SQL Candidate Output
                             │
   ══════════════════════════╪═════════════════════════════════════  [Trust Boundary 3: Deterministic Policy]
                             ▼
                    [ Policy Engine & AST Parser ]
                      - SELECT-Only Statement Whitelist
                      - Table & Column Allowlist Verification
                      - High Sensitivity Column Blocking
                      - Deterministic Row Filter Injection (RLS)
                      - SQL Critic Smell Analysis
                             │
   ══════════════════════════╪═════════════════════════════════════  [Trust Boundary 4: Database Execution]
                             ▼
                    [ Read-Only Sandbox Pool ]
                      - Least Privilege DB Credentials (business_readonly)
                      - Strict Statement Timeout (5–10s)
                      - Hard Result Row Cap (10,000 rows)
                      - Isolated Multi-Tenant DataSource Routing
```

---

## 4. Threat Matrix & Mitigations (STRIDE Analysis)

| Threat ID | Category | Threat Scenario | Mitigation / Control | Status |
| :--- | :--- | :--- | :--- | :--- |
| **T01** | **Spoofing** | Client sends tampered JWT or claims simulated role in request body. | Server-side role resolution (`get_effective_role_id`). Non-admins cannot elevate or simulate roles. | **ENFORCED** |
| **T02** | **Tampering** | LLM generates `DROP`, `INSERT`, `UPDATE`, `ALTER`, or `EXEC`. | AST parser enforces strict single-statement `SELECT` grammar. All DDL/DML rejected before sandbox. | **ENFORCED** |
| **T03** | **Information Disclosure** | User queries a table or column restricted for their role or high sensitivity. | Fail-closed `DataPolicy` check. Unauthorized table/column references blocked deterministically. | **ENFORCED** |
| **T04** | **Elevation of Privilege** | Replay or execution executes against a different, higher-privilege datasource. | Strict `data_source_id` binding on `QueryHistory`, `DataSourceManager` isolation, no global fallback. | **ENFORCED** |
| **T05** | **Denial of Service** | Runaway Cartesian product or expensive nested subqueries. | Optimizer admission gate (`BLOCK_RUNAWAY_CARTESIAN`), statement timeout, sandbox row caps. | **ENFORCED** |
| **T06** | **Information Disclosure (IDOR)** | User accesses or reruns another user's historical queries or evaluation jobs. | `authorize_query_access` & `authorize_job_access` enforce resource owner verification. | **ENFORCED** |
| **T07** | **Repudiation** | Query results diverge or cannot be audited against schema state. | Immutable `schema_snapshot`, prompt versions, model parameters, and SHA-256 result fingerprints. | **ENFORCED** |
| **T08** | **Bypass of Row Security** | Query omits tenant/department filter. | Policy Engine injects deterministic SQL AST `WHERE` predicates into AST before sandbox dispatch. | **ENFORCED** |

---

## 5. Security Invariant Assertions

1. **Universal Guardrail Invariance**: Every SQL query executed against any database MUST pass deterministic Policy Engine validation.
2. **Fail-Closed Isolation**: If a datasource, token revocation cache, or policy record is missing or unreachable, the system denies access by default.
3. **No LLM in Security Path**: Authorization decisions are computed 100% deterministically in Python/AST, never delegated to an LLM evaluator.
4. **Least-Privilege Database Sandbox**: Runtime application connections to business databases use dedicated read-only credentials (`business_readonly`), making data-modifying exploits physically impossible at the DBMS level.
