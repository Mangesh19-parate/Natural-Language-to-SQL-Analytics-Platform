# ADR-003: Bounded Self-Correction Loop with Structured Error Taxonomy (E1–E7)

## Status
Accepted

## Date
2026-09-17

## Context
When an LLM-generated SQL query produces an execution error (e.g., column syntax error, type mismatch), automated self-correction can recover the query. However, unbounded retry loops cause runaway latency, token exhaustion, and potential security boundary probing.

## Problem
How do we structure query self-correction to maximize repair rate while guaranteeing bounded execution and preventing unauthorized retries?

## Options Considered
1. **Option 1: Unbounded LLM Retry Loop**: Repeatedly feed error messages back to the LLM until the query succeeds or times out.
2. **Option 2: Bounded 3-Retry Loop with Structured Error Taxonomy (E1–E7) and Policy Hard-Stop**:
   - Classify errors into E1 (Syntax), E2 (Schema Ref), E3 (Type Mismatch), E4 (Semantic Logic), E5 (Authorization), E6 (Timeout/Resource), E7 (Empty Result).
   - Enforce Rule R4.2: E5 Authorization rejections are NEVER retried.
   - Hard upper bound of 3 repair attempts.

## Decision
We chose **Option 2: Bounded 3-Retry Loop with Structured Error Taxonomy**.

## Trade-offs & Consequences
- **Positive**:
  - Predictable maximum latency profile ($3 \times \text{timeout}$).
  - Full auditability: Each retry records candidate SQL, diff summary, error classification, and validation results.
  - Zero authorization probe attacks: Policy rejections are blocked immediately.
- **Negative**:
  - Highly obscure or complex logical errors requiring $>3$ steps may fail and require user clarification.
