# ADR-008: Versioned Deterministic Query Replay & Schema Snapshots

## Status
Accepted

## Date
2026-09-17

## Context
When an NL→SQL system is asked "Why did the system generate a different SQL query for the same question today compared to last month?", answering requires reconstructing the exact semantic state at the time of execution. Without versioning of prompts, catalog schemas, and policies, past queries cannot be replayed or debugged reproducibly.

## Problem
How do we ensure query generation and execution history is 100% reproducible and verifiable over time?

## Options Considered
1. **Option 1: Log SQL Strings Only**: Record the generated query string without historical context.
2. **Option 2: Comprehensive Immutable Version Snapshots & Result Hashing**:
   - Record `prompt_version`, `model_name`, `model_params` (temperature, max tokens), `schema_snapshot_id`, `policy_version`, and SHA-256 `result_hash`.
   - Provide a replay endpoint `POST /api/replay/{query_id}` that can re-evaluate or execute the exact past query against historical schema snapshots.

## Decision
We chose **Option 2: Comprehensive Immutable Version Snapshots & Result Hashing**.

## Trade-offs & Consequences
- **Positive**:
  - Full temporal auditability for enterprise compliance.
  - Enables regression testing across LLM prompt updates and model upgrades.
  - Deterministic verification using SHA-256 result set hashing.
- **Negative**:
  - Requires storing schema snapshot references in the database.
