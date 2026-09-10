# Backend Schema Document — v1.2
## Intelligent SQL Assistant

**Supersedes v1.1.** New tables implement the Trust Engine (semantic catalog, critic findings, result validation, evaluation lab, security attack lab, failure observatory) and fix the fail-open RBAC default and privacy issues raised by both audits.

## Change Log (v1.1 → v1.2)
1. **Critical fix:** `dataset_access` (v1.0's fail-open table) replaced by `data_policy`, explicitly deny-by-default.
2. Added `semantic_catalog` — the typed, sensitivity-tagged schema representation (the only thing the LLM ever sees).
3. Added `sql_critic_findings`, `result_validation` — Trust Engine stages.
4. Added `evaluation_run` / `evaluation_result` — Evaluation Lab persistence.
5. Added `security_attack_log` — Security Attack Lab results.
6. Added `failure_log` — Failure Observatory aggregation source.
7. Added `schema_snapshot`, and versioning columns on `query_history` (`schema_snapshot_id`, `prompt_version`, `model_name`) for reproducibility/Query Replay.
8. Fixed `llm_call_log` to store hashes, not raw prompt/response text.
9. Removed `masked_columns` array approach (too weak against aggregation leakage) in favor of `data_policy` with explicit `aggregate_allowed` flag.
10. Removed report "sharing" fields — v1 is owner-only download (kept `reports` minimal, added `status`/`expires_at`/`content_hash` per audit).

---

## 1. App Metadata Schema (PostgreSQL)

```sql
-- USERS & ROLES
CREATE TABLE roles (
    role_id      SERIAL PRIMARY KEY,
    role_name    VARCHAR(50) UNIQUE NOT NULL   -- 'admin', 'analyst', 'viewer'
);

CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    full_name     VARCHAR(150) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id       INT REFERENCES roles(role_id),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- DATA SOURCE CONNECTIONS
CREATE TABLE data_sources (
    data_source_id SERIAL PRIMARY KEY,
    name           VARCHAR(150) NOT NULL,
    db_type        VARCHAR(20) NOT NULL,        -- 'postgresql' | 'mysql' | 'sqlite' (dev/demo only)
    host           VARCHAR(255),
    port           INT,
    database_name  VARCHAR(150),
    connection_role VARCHAR(100) DEFAULT 'readonly_app_user',
    secret_ref     VARCHAR(255) NOT NULL,
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- ===========================================================================
-- DATA POLICY — fail-closed replacement for v1.1's dataset_access
-- No row for a given (role, table) = ZERO ACCESS. This is enforced in code,
-- not just documented: the Policy Engine query is `SELECT ... WHERE EXISTS`,
-- never a `WHERE NOT excluded` pattern.
-- ===========================================================================
CREATE TABLE data_policy (
    policy_id        SERIAL PRIMARY KEY,
    role_id          INT REFERENCES roles(role_id),
    data_source_id   INT REFERENCES data_sources(data_source_id),
    table_name       VARCHAR(150) NOT NULL,
    column_name      VARCHAR(150),                -- NULL = applies to all columns of the table
    access_level     VARCHAR(20) NOT NULL DEFAULT 'denied', -- 'denied' | 'read' | 'read_aggregate_only'
    aggregate_allowed BOOLEAN DEFAULT FALSE,        -- explicit grant required to AVG/SUM/MAX/MIN a sensitive column
    row_filter_sql   TEXT,                          -- optional WHERE-clause fragment injected by Policy Engine
    UNIQUE (role_id, data_source_id, table_name, column_name)
);
CREATE INDEX idx_data_policy_lookup ON data_policy(role_id, data_source_id, table_name);

-- ===========================================================================
-- SEMANTIC CATALOG — typed, sensitivity-tagged schema representation.
-- This is the ONLY schema view ever sent to the LLM (REQ-CATALOG-01).
-- ===========================================================================
CREATE TABLE semantic_catalog (
    catalog_id      SERIAL PRIMARY KEY,
    data_source_id  INT REFERENCES data_sources(data_source_id),
    table_name      VARCHAR(150) NOT NULL,
    column_name     VARCHAR(150) NOT NULL,
    data_type       VARCHAR(50),
    semantic_type   VARCHAR(50),                    -- 'monetary' | 'identifier' | 'categorical' | 'temporal' | 'metric' | 'text'
    sensitivity     VARCHAR(20) DEFAULT 'NONE',      -- 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'
    default_aggregation VARCHAR(20),                 -- 'SUM' | 'AVG' | 'COUNT' | NULL
    sanitized_examples JSONB,                        -- distinct categorical examples only, never raw PII rows
    description     TEXT,
    UNIQUE (data_source_id, table_name, column_name)
);

-- SCHEMA SNAPSHOTS — reproducibility (REQ-VER-01 / REQ-REPLAY-01)
CREATE TABLE schema_snapshot (
    schema_snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_source_id      INT REFERENCES data_sources(data_source_id),
    captured_at          TIMESTAMP DEFAULT NOW(),
    schema_json          JSONB NOT NULL              -- full introspected structure at capture time
);

-- SESSIONS — structured conversational context (REQ-MEM-01), not free text
CREATE TABLE sessions (
    session_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INT REFERENCES users(user_id),
    data_source_id  INT REFERENCES data_sources(data_source_id),
    started_at      TIMESTAMP DEFAULT NOW(),
    last_active_at  TIMESTAMP DEFAULT NOW(),
    active_dataset  VARCHAR(150),
    active_filters  JSONB,
    time_context    JSONB,
    entities        JSONB,
    conversation_summary TEXT,
    turn_count      INT DEFAULT 0,
    context_version INT DEFAULT 1,
    expires_at      TIMESTAMP
);

-- ===========================================================================
-- QUERY HISTORY — extended for Trust Engine + reproducibility (Query Replay)
-- ===========================================================================
CREATE TABLE query_history (
    query_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID REFERENCES sessions(session_id),
    user_id             INT REFERENCES users(user_id),
    nl_question         TEXT NOT NULL,
    classification       VARCHAR(20),                -- 'answerable' | 'ambiguous' | 'unsupported' | 'unauthorized'
    ambiguity_flag       BOOLEAN DEFAULT FALSE,
    clarification_asked  TEXT,
    initial_sql          TEXT,
    final_sql             TEXT,
    dialect               VARCHAR(20),
    correction_count      INT DEFAULT 0,
    error_type            VARCHAR(10),                -- E1..E7
    status                VARCHAR(20) NOT NULL,        -- 'success' | 'auto_corrected' | 'failed' | 'rejected_policy' | 'rejected_unsupported'
    error_message         TEXT,
    execution_ms          INT,
    row_count             INT,
    chart_type             VARCHAR(20),
    explanation             TEXT,
    result_hash              VARCHAR(64),
    -- reproducibility (Query Replay)
    schema_snapshot_id        UUID REFERENCES schema_snapshot(schema_snapshot_id),
    prompt_version             VARCHAR(20),
    model_name                  VARCHAR(100),
    model_params                 JSONB,
    -- reliability scoring (5 checkable sub-scores, not a bare LLM %)
    reliability_breakdown         JSONB,               -- {schema_grounding, join_confidence, filter_interpretation, execution_validation, result_sanity, composite}
    created_at                     TIMESTAMP DEFAULT NOW()
);

-- SQL CRITIC FINDINGS — semantic-smell checks before execution (REQ-CRITIC-01)
CREATE TABLE sql_critic_findings (
    finding_id     SERIAL PRIMARY KEY,
    query_id       UUID REFERENCES query_history(query_id),
    finding_type   VARCHAR(50),          -- 'aggregate_on_identifier' | 'suspicious_group_by' | 'type_mismatch_filter' | 'redundant_join'
    detail         TEXT,
    suggested_fix  TEXT,
    user_action    VARCHAR(20),          -- 'proceeded' | 'revised' | 'ignored'
    created_at     TIMESTAMP DEFAULT NOW()
);

-- RESULT VALIDATION — sanity checks on the result set itself (REQ-RESULT-01)
CREATE TABLE result_validation (
    validation_id   SERIAL PRIMARY KEY,
    query_id        UUID REFERENCES query_history(query_id),
    check_type      VARCHAR(50),          -- 'zero_row' | 'cardinality_outlier' | 'join_multiplication' | 'null_explosion'
    expected_range  VARCHAR(100),
    observed_value  VARCHAR(100),
    severity        VARCHAR(10),          -- 'info' | 'warning' | 'critical'
    created_at      TIMESTAMP DEFAULT NOW()
);

-- OPTIMIZATION SUGGESTIONS (evidence-based; EXPLAIN by default, ANALYZE opt-in)
CREATE TABLE optimization_suggestions (
    suggestion_id SERIAL PRIMARY KEY,
    query_id      UUID REFERENCES query_history(query_id),
    mode          VARCHAR(10) DEFAULT 'explain',   -- 'explain' | 'explain_analyze' (admin-gated)
    issue_type    VARCHAR(50),
    detail        TEXT,
    evidence_json JSONB,                            -- estimated rows, existing indexes, plan cost
    confidence    VARCHAR(10),                      -- 'low' | 'medium' | 'high'
    suggested_ddl TEXT,                              -- copyable only, never auto-executed
    created_at    TIMESTAMP DEFAULT NOW()
);

-- REPORTS — owner-only download in v1 (no sharing fields, per audit)
CREATE TABLE reports (
    report_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       INT REFERENCES users(user_id),
    session_id    UUID REFERENCES sessions(session_id),
    title         VARCHAR(255),
    format        VARCHAR(10),                       -- 'pdf' | 'xlsx'
    file_path     TEXT NOT NULL,
    scope         VARCHAR(20),                        -- 'single_query' | 'session'
    status        VARCHAR(20) DEFAULT 'ready',
    content_hash  VARCHAR(64),
    expires_at    TIMESTAMP,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- FEEDBACK
CREATE TABLE feedback (
    feedback_id       SERIAL PRIMARY KEY,
    query_id          UUID REFERENCES query_history(query_id),
    user_id           INT REFERENCES users(user_id),
    rating            VARCHAR(10),                     -- 'correct' | 'incorrect'
    feedback_type     VARCHAR(30),                      -- 'wrong_sql' | 'wrong_chart' | 'wrong_interpretation' | 'other'
    expected_behavior TEXT,
    comment           TEXT,
    created_at        TIMESTAMP DEFAULT NOW()
);

-- LLM CALL LOG — hashed, privacy-safe by default
CREATE TABLE llm_call_log (
    call_id           SERIAL PRIMARY KEY,
    query_id          UUID REFERENCES query_history(query_id),
    model_name        VARCHAR(100),
    purpose           VARCHAR(30),                        -- 'sql_generation' | 'self_correction' | 'explanation' | 'ambiguity_check'
    retry_number      INT DEFAULT 0,
    prompt_hash       VARCHAR(64),
    response_hash     VARCHAR(64),
    prompt_tokens     INT,
    completion_tokens INT,
    latency_ms        INT,
    cost_estimate     NUMERIC(10,4),
    created_at        TIMESTAMP DEFAULT NOW()
);

-- Separate, access-restricted store for raw traces if ever needed for research (R5.3)
CREATE TABLE encrypted_trace_store (
    trace_id    SERIAL PRIMARY KEY,
    call_id     INT REFERENCES llm_call_log(call_id),
    prompt_enc  BYTEA,      -- encrypted at rest
    response_enc BYTEA,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ===========================================================================
-- SECURITY ATTACK LAB — standing adversarial test results (REQ-SECLAB-01)
-- ===========================================================================
CREATE TABLE security_attack_log (
    attack_id     SERIAL PRIMARY KEY,
    run_id        UUID,                    -- groups one full attack-suite run
    attack_name   VARCHAR(150),             -- 'drop_table', 'union_privilege_escalation', 'prompt_injection_ssn', ...
    attack_class  VARCHAR(30),              -- 'structural' | 'prompt_injection'
    input_payload TEXT,
    blocked       BOOLEAN NOT NULL,
    blocked_at_stage VARCHAR(30),           -- 'ast' | 'schema_auth' | 'column_auth' | 'function_allowlist' | 'resource_limit'
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ===========================================================================
-- FAILURE OBSERVATORY — aggregation source (REQ-FAILOBS-01, P1)
-- ===========================================================================
CREATE TABLE failure_log (
    failure_id     SERIAL PRIMARY KEY,
    query_id       UUID REFERENCES query_history(query_id),
    failure_class  VARCHAR(30),   -- 'schema_hallucination' | 'join_error' | 'ambiguous_intent' | 'type_mismatch'
                                    -- | 'authorization_rejection' | 'timeout' | 'semantic_mismatch'
    problematic_phrase TEXT,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- ===========================================================================
-- EVALUATION LAB — benchmark persistence (REQ-EVALLAB-01)
-- ===========================================================================
CREATE TABLE evaluation_run (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    baseline_variant VARCHAR(20),    -- 'A_plain_llm' | 'B_schema_aware' | 'C_schema_and_correction' | 'D_proposed'
    schema_snapshot_id UUID REFERENCES schema_snapshot(schema_snapshot_id),
    prompt_version    VARCHAR(20),
    model_name        VARCHAR(100),
    started_at        TIMESTAMP DEFAULT NOW(),
    completed_at      TIMESTAMP
);

CREATE TABLE evaluation_result (
    result_id         SERIAL PRIMARY KEY,
    run_id            UUID REFERENCES evaluation_run(run_id),
    question_id       VARCHAR(20),
    category          VARCHAR(30),     -- simple/temporal/join/nested/ambiguous/adversarial/invalid/unauthorized/optimization
    execution_success BOOLEAN,
    result_correct    BOOLEAN,
    error_type        VARCHAR(10),     -- E1..E7 if failed
    safety_violation  BOOLEAN DEFAULT FALSE,
    unauthorized_exposure BOOLEAN DEFAULT FALSE,
    latency_ms        INT,
    token_cost        NUMERIC(10,4),
    created_at        TIMESTAMP DEFAULT NOW()
);
```

### 1.1 Indexes
```sql
CREATE INDEX idx_query_history_user      ON query_history(user_id);
CREATE INDEX idx_query_history_session   ON query_history(session_id);
CREATE INDEX idx_query_history_status    ON query_history(status);
CREATE INDEX idx_security_attack_run     ON security_attack_log(run_id);
CREATE INDEX idx_eval_result_run         ON evaluation_result(run_id);
CREATE INDEX idx_eval_result_category    ON evaluation_result(category);
CREATE INDEX idx_failure_log_class       ON failure_log(failure_class);
```

### 1.2 Entity Relationship Summary
```
roles 1---* data_policy *---1 data_sources          roles 1---* users
data_sources 1---* semantic_catalog                 data_sources 1---* schema_snapshot
users 1---* sessions 1---* query_history
query_history 1---* sql_critic_findings
query_history 1---* result_validation
query_history 1---* optimization_suggestions
query_history 1---* feedback
query_history 1---* llm_call_log 1---* encrypted_trace_store
query_history 1---* failure_log
evaluation_run 1---* evaluation_result
security_attack_log grouped by run_id (no FK — independent standing suite)
```

## 2. Business Data Schema (sample domain — unchanged from v1.1)
```sql
CREATE TABLE departments (department_id SERIAL PRIMARY KEY, department_name VARCHAR(100) NOT NULL);
CREATE TABLE employees (employee_id SERIAL PRIMARY KEY, first_name VARCHAR(100), last_name VARCHAR(100),
                         department_id INT REFERENCES departments(department_id), salary NUMERIC(12,2), hire_date DATE);
CREATE TABLE customers (customer_id SERIAL PRIMARY KEY, customer_name VARCHAR(150), city VARCHAR(100), total_spent NUMERIC(12,2) DEFAULT 0);
CREATE TABLE products (product_id SERIAL PRIMARY KEY, product_name VARCHAR(150), category VARCHAR(100), price NUMERIC(12,2));
CREATE TABLE orders (order_id SERIAL PRIMARY KEY, customer_id INT REFERENCES customers(customer_id), order_date DATE, total_amount NUMERIC(12,2));
CREATE TABLE sales (sale_id SERIAL PRIMARY KEY, order_id INT REFERENCES orders(order_id), product_id INT REFERENCES products(product_id),
                     quantity INT, revenue NUMERIC(12,2));
```

### 2.1 Example `semantic_catalog` seed rows (what the LLM actually sees)
```json
[
  {"table_name": "employees", "column_name": "salary", "semantic_type": "monetary", "sensitivity": "HIGH", "default_aggregation": "AVG", "sanitized_examples": null},
  {"table_name": "employees", "column_name": "department_id", "semantic_type": "categorical", "sensitivity": "NONE", "sanitized_examples": ["Engineering", "Sales", "HR"]},
  {"table_name": "orders", "column_name": "total_amount", "semantic_type": "monetary", "sensitivity": "NONE", "default_aggregation": "SUM"},
  {"table_name": "customers", "column_name": "customer_name", "semantic_type": "identifier", "sensitivity": "MEDIUM", "sanitized_examples": null}
]
```
Note: no raw customer/employee rows are ever included — only distinct categorical examples for low-sensitivity columns.

## 3. Data Retention & Privacy
- `llm_call_log` stores hashes by default (fixes v1.1's remaining inconsistency between Rules and schema).
- `semantic_catalog.sanitized_examples` never contains values from `sensitivity IN ('MEDIUM','HIGH')` columns.
- `reports.file_path` stored in object storage with signed URLs; no public/shareable state in v1.
