# ADR-005: Redis for Distributed State, Token Revocation, and Sliding-Window Rate Limiting

## Status
Accepted

## Date
2026-09-17

## Context
In horizontally scaled deployments with multiple FastAPI application replicas, process-local memory state (e.g. `set()` of revoked tokens, in-memory rate counters) is not shared. A token revoked on Replica A remains valid on Replica B, and rate limiting quotas are multiplied by the number of instances.

## Problem
How do we maintain sub-millisecond, distributed state synchronization across stateless API replicas?

## Options Considered
1. **Option 1: In-Memory Local Python State**: Fast, but non-shared and lost on restart.
2. **Option 2: Relational Database Lookups**: Persistent, but adds query overhead to every authenticated request.
3. **Option 3: Centralized Redis Key-Value Store with Fail-Closed DB Persistence**:
   - Token revocation: `revoked:jti:{jti}` with TTL matching token expiration.
   - Rate limiting: Sliding-window Sorted Sets (`ZADD` / `ZREMRANGEBYSCORE`).
   - Catalog cache: Keyed by `catalog:{data_source_id}:role:{role_id}`.

## Decision
We chose **Option 3: Centralized Redis Key-Value Store with Fail-Closed DB Persistence**.

## Trade-offs & Consequences
- **Positive**:
  - Immediate, synchronized revocation and rate limiting across all nodes.
  - Automatic TTL-based eviction prevents unbounded memory growth.
  - Sub-millisecond latency ($O(1)$).
- **Negative**:
  - Adds Redis infrastructure dependency (with graceful fallback to DB/in-memory mode if disconnected).
