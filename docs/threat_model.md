# Threat Model (STRIDE Framework)

This document details the security threat model for the **Intelligent SQL Assistant (Trust Engine)** platform following Microsoft's STRIDE methodology.

---

## 🛡 System Security Boundaries

```
[ Untrusted Client / Browser ]
             │ (HTTP / TLS)
             ▼
═════════════════════════════════════════════════════════════════════════════════
 TRUST BOUNDARY 1: Edge & Network Security
 - Distributed Rate Limiter (Redis Sliding Window, 120 req/min)
 - JWT Bearer Authentication & Fail-Closed Revocation Lookup
 - Server-Side Role Enforcement (Client role spoofing blocked)
═════════════════════════════════════════════════════════════════════════════════
             │
             ▼
[ FastAPI Stateless Application Tier ]
             │
             ▼
═════════════════════════════════════════════════════════════════════════════════
 TRUST BOUNDARY 2: AI / LLM Generation Isolation
 - Model output is treated as UNTRUSTED CANDIDATE DATA.
 - LLM has ZERO execution or authorization authority (Principle Rule 0).
═════════════════════════════════════════════════════════════════════════════════
             │
             ▼
[ Deterministic AST & Policy Enforcement Engine ]
 - SQLglot Abstract Syntax Tree (AST) validation.
 - Reject 100% of non-SELECT statements (INSERT/UPDATE/DELETE/DROP/ALTER).
 - Table & Column RBAC validation.
 - Forced AST Row-Filter Injection (Tenant / Department boundaries).
 - Disallowed dangerous functions block (`pg_read_file`, `system`, `copy`).
 - Disconnected Cartesian product block.
═════════════════════════════════════════════════════════════════════════════════
             │
             ▼
═════════════════════════════════════════════════════════════════════════════════
 TRUST BOUNDARY 3: Execution Sandbox & Database Isolation
 - Dedicated read-only database credentials.
 - Hard statement timeouts (default 10s, max 30s).
 - Hard row result cap (default 1,000, max 10,000).
 - Result validation & anomaly detection (Zero-row, NULL explosion, Cardinality outlier).
═════════════════════════════════════════════════════════════════════════════════
             │
             ▼
[ Read-Only Business Data Warehouse ]
```

---

## 🔍 STRIDE Threat Analysis Matrix

| Threat Category | Threat Description | Attack Vector / Scenario | Platform Mitigation & Security Control | Verification Test |
| :--- | :--- | :--- | :--- | :--- |
| **Spoofing (S)** | Client claims a higher privilege role (e.g. `role_id=1` admin) in JSON payload while logged in as viewer. | Attacker tampers with request body `role_id` to access executive salary data. | **`get_effective_role_id()`**: Server-side role extraction strictly derives role from cryptographically verified JWT claims, ignoring client payload overrides. | `test_client_cannot_spoof_role_id_to_bypass_policy` |
| **Spoofing (S)** | Replay of stolen or logged-out JWT tokens. | Attacker uses a leaked token after the legitimate user called `/logout`. | **Distributed Token Revocation**: Revokes JTI & token hash in Redis and persistent `RevokedToken` DB table. Fail-closed verification on every request. | `test_concurrent_token_revocation_under_load` |
| **Tampering (T)** | SQL Injection via natural language prompt. | Attacker submits: *"Show sales; DROP TABLE employees; --"* | **Deterministic AST Parsing**: Rejects multiple statements (`MULTIPLE_STATEMENTS`), validates statement type is strictly `SELECT`, rejects DDL/DML. | `test_reject_100_percent_non_select_statements` |
| **Tampering (T)** | Row filter bypass via alias or CTE rewriting. | Attacker writes CTE to query all departments without tenant filter. | **AST Row Filter Injection**: Injects mandatory WHERE predicates directly into table expressions within the AST hierarchy before SQL serialization. | `test_ast_row_filter_injection_with_existing_where` |
| **Repudiation (R)** | User denies executing an expensive or sensitive query. | Compliance audit requires proof of which user ran an analytics query. | **Query History & Replay**: Stores `user_id`, prompt version, schema snapshot ID, final executed SQL, execution latency, and SHA-256 result set hash. | `test_query_replay_exact_reproducibility` |
| **Information Disclosure (I)** | Unauthorized column access (e.g. `salary`, `ssn`, `password_hash`). | User asks for *"employee compensation"* or uses wildcard `SELECT *`. | **Column-Level Policy Engine & Deny Lists**: Validates every column in AST against role policy. Blocks unauthorized columns and masks sensitive fields. | `test_column_deny`, `test_high_sensitivity_column_no_policy_denied` |
| **Information Disclosure (I)** | Direct File System or OS Access via SQL functions. | Attacker queries `pg_read_file('/etc/passwd')` or SQLite `load_extension()`. | **Disallowed Function AST Gate**: Rejects any AST node containing dangerous database built-ins. | `test_dangerous_functions_blocked` |
| **Denial of Service (D)** | Runaway Cartesian product or unindexed joins exhausting database memory. | Attacker crafts a 6-table join without join predicates (`FROM a, b, c, d`). | **Cost-Based Join Optimizer & Cartesian Gate**: Pre-execution graph traversal detects disconnected components and returns `BLOCK_RUNAWAY_CARTESIAN`. | `test_cartesian_product_block_gate` |
| **Denial of Service (D)** | High-concurrency API flooding / event-loop starvation. | Attacker sends 500 parallel heavy optimization requests. | **Distributed Rate Limiting & Threadpool Isolation**: 120 req/min sliding-window limiter; synchronous endpoints execute in `anyio.to_thread` worker pool. | `test_concurrent_sql_validation_burst_100` |
| **Elevation of Privilege (E)** | Non-admin user accessing `EXPLAIN ANALYZE` execution mode. | Viewer calls `POST /api/optimize/analyze`. | **`require_roles(["admin"])`**: Strictly checks server-side role and raises HTTP 403 Forbidden. | `test_non_admin_cannot_access_explain_analyze` |

---

## 🔒 Fail-Closed Security Invariant

The core security thesis of the system is:
$$\text{Safety}(\text{Query}) = \text{PolicyEngine}(\text{AST}(\text{SQL})) \land \text{ExecutionSandbox}(\text{SQL}_{\text{injected}})$$

If any security component (token validation, AST parser, policy database lookup, role authorization) encounters an unexpected state or exception, the system **fails closed**: the request is immediately rejected with HTTP 401/403/400 and query execution is aborted.
