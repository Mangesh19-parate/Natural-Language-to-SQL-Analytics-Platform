# Intelligent SQL Assistant (Trust Engine)

A Trustworthy Natural-Language Analytics Engine with Verification, Self-Correction, and Evidence-Grounded Query Execution.

> **Core Principle (Rule 0):** *The LLM proposes. Deterministic infrastructure authorizes, critiques, executes, and verifies.*

---

## Week 1: Foundations & Environment Status

| Task ID | Component | Status | Evidence |
|---|---|---|---|
| **T-01** | Repo + Docker Compose Skeleton | **Done** | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| **T-02** | Business Schema + Seed Data ($\ge 100$ rows) | **Done** | `backend/scripts/seed_business_db.py`, `tests/integration/test_business_seeding.py` |
| **T-03** | App Metadata Schema & Alembic Migrations | **Done** | `backend/alembic/versions/001_initial_metadata_schema.py` |
| **T-04** | `data_policy` Table & Fail-Closed Lookup | **Done** | `backend/app/services/policy_engine.py`, `tests/unit/test_data_policy.py` |
| **Smoke**| LLM Provider Smoke Test with Hashed Auditing | **Done** | `backend/app/services/llm_provider.py`, `tests/unit/test_llm_provider.py` |

---

## Quickstart Guide

### 1. Run Automated Test Suite
```bash
cd backend
python -m pytest -v
```

### 2. Run Database Initialization & Seeding
```bash
cd backend
# Apply metadata migrations
alembic upgrade head

# Seed initial roles, admin user, and data sources
python scripts/init_metadata_db.py

# Seed coherent relational business schema (10 depts, 120 employees, 150 customers, 100 products, 200 orders, 350 sales)
python scripts/seed_business_db.py
```

### 3. Run FastAPI Backend Locally
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Healthcheck: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 4. Run Docker Compose
```bash
docker-compose up --build
```
- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)
