# Intelligent SQL Assistant (Trust Engine)

A Trustworthy, High-Performance Natural-Language Analytics Platform with Deterministic Policy Enforcement, Cost-Based Join Optimization, Self-Correction, and Evidence-Grounded Verification.

> **Core Principle (Rule 0):** *The LLM proposes. Deterministic infrastructure authorizes, critiques, optimizes, executes, and verifies.*

---

## 🏛 Architecture Overview

```
                      ┌─────────────────────────────────┐
                      │    Natural Language Question    │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │  Role-Scoped Semantic Catalog │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   LLM SQL Proposal Generation │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
             ┌───────────────────────────────────────────────────┐
             │         Deterministic AST Policy Engine           │
             │   (Table/Column RBAC, Row Filters, Sanitization)  │
             └─────────────────────────┬─────────────────────────┘
                                       │ (Approved)
                                       ▼
             ┌───────────────────────────────────────────────────┐
             │       Cost-Based Physical Join Optimizer          │
             │     (Bitmask DP O(3^N) & Greedy PQ Heuristic)     │
             └─────────────────────────┬─────────────────────────┘
                                       │
                                       ▼
             ┌───────────────────────────────────────────────────┐
             │           Read-Only Execution Sandbox             │
             │     (Timeout Gating, Row Bounding, Fail-Closed)   │
             └─────────────────────────┬─────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
        ┌───────────────────────┐             ┌───────────────────────┐
        │   Result Sanity Gate  │             │   E1–E7 Self Repair   │
        │ (Null/Card/Join Check)│             │ (Bounded 3 Retries)   │
        └───────────┬───────────┘             └───────────────────────┘
                    │
                    ▼
        ┌────────────────────────────────────────────────────────┐
        │   Deterministic Reliability Score & Visual Analytics   │
        └────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Technical Pillars

### 1. Algorithmic Rigor & Internal Database Mechanics
- **Bitmask Dynamic Programming Join Optimizer ($O(3^N)$)**: Explores all $2^N$ table subsets using submask bitwise transitions (`s1 = (S - 1) & S`) to find the exact globally optimal physical join tree (Hash Join vs. Sort-Merge vs. Nested Loop) for queries with up to 8 tables.
- **Greedy Priority Queue Fallback ($O(N^2)$)**: Polynomial minimum-selectivity heuristic planner for wide analytical joins ($N > 8$).
- **Selinger / System-R Cost Formulation**: Models sequential scans, B-tree index scans, CPU tuple processing, and page fetch costs.
- **Topological Pipeline Validation ($O(V+E)$)**: Kahn's topological sort with `collections.deque.popleft()` for linear dependency sorting.

### 2. Universal Fail-Closed Security & Concurrency
- **Deterministic AST Policy Gate**: Parses candidate SQL into SQLglot ASTs to enforce table and column RBAC, inject role-specific tenant filters, and reject non-SELECT operations with 0.00% bypass rate.
- **Distributed Token Revocation**: Stateless JWT authorization backed by persistent DB revocation lookups and Redis distributed caches.
- **Asynchronous Background Workers**: Persistent DB-tracked background jobs (`POST /api/lab/evaluation/jobs`) for long-running benchmark evaluations.

### 3. Truthful Empirical Evaluation & Observability
- **165-Query Evaluation Suite**: 100 executable SQL ground-truth queries + 65 adversarial, ambiguous, refusal, and safety boundary cases.
- **Multiset Tuple Equality**: Float-tolerant ($\epsilon = 10^{-4}$) multiset tuple comparison eliminating string-matching biases.
- **Zero Synthetic Telemetry**: All reliability scores, latency measurements, and execution traces are calculated dynamically from actual runtime telemetry.

---

## 📚 Architecture Decision Records (ADRs)

Detailed architectural trade-off evaluations and decisions are documented in [`docs/adr/`](docs/adr/):

1. [**ADR-001: Deterministic Policy Boundary vs. LLM Self-Policing**](docs/adr/001-deterministic-policy-boundary.md)
2. [**ADR-002: Read-Only Business Database Sandbox**](docs/adr/002-read-only-business-database.md)
3. [**ADR-003: Bounded Self-Correction (Max 3 Retries, E5 Hard Gate)**](docs/adr/003-self-correction-limit.md)
4. [**ADR-004: Query Cost & Runaway Join Admission Gate**](docs/adr/004-query-cost-gate.md)
5. [**ADR-005: Redis for Shared State & Token Revocation**](docs/adr/005-redis-for-shared-state.md)
6. [**ADR-006: Worker-Based Long-Running Evaluation Jobs**](docs/adr/006-worker-based-long-running-jobs.md)
7. [**ADR-007: Object Storage Abstraction for Verifiable Reports**](docs/adr/007-object-storage-for-reports.md)
8. [**ADR-008: Versioned Schema Snapshots for Deterministic Query Replay**](docs/adr/008-versioned-query-replay.md)

---

## 🧪 Verification & Automated Test Suite

The platform is covered by **204 automated unit, integration, property, resilience, and load tests**:

```bash
cd backend
pytest tests/ -v
```

### Test Coverage Breakdown:
- **Unit Tests (119 passing)**: AST parser, policy enforcement, join graph extraction, Bitmask DP states, greedy heuristics, priority queue join ordering, reliability scorer, and self-correction taxonomy (E1–E7).
- **Integration Tests (67 passing)**: Full 165-query evaluation benchmark suite, 128-case adversarial security attack lab, RBAC boundaries, and schema introspection.
- **Resilience & Failure Injection Tests (5 passing)**: Corrupted AST tokens, database connection drops, invalid query states, and fail-closed security invariants.
- **Property-Based Tests (6 passing)**: Hypothesis randomized fuzzing for bitmask DP states, AST invariants, and non-SELECT rejection.
- **Load & Concurrency Tests (4 passing)**: 10, 50, and 100 parallel concurrent request bursts measuring p50, p95, and p99 latency SLAs.

---

## 🛠 Quickstart Guide

### 1. Database Initialization & Seeding
```bash
cd backend

# Run metadata migrations
alembic upgrade head

# Seed initial roles, admin user, and catalog data sources
python scripts/init_metadata_db.py

# Seed coherent relational business schema
python scripts/seed_business_db.py
```

### 2. Run FastAPI Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Prometheus Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)

### 3. Run Frontend UI
```bash
cd frontend
npm install
npm run dev
```
- **Web App**: [http://localhost:5173](http://localhost:5173)

### 4. Docker Compose
```bash
docker-compose up --build
```
