# ADR-002: Read-Only Business Database Execution Sandbox & Separate Connection Pools

## Status
Accepted

## Date
2026-09-17

## Context
NL→SQL platforms execute analytical queries generated from user prompts against organizational data warehouses. If these queries execute against the primary application metadata database or use high-privilege read-write connection credentials, runaway analytical queries can corrupt application state or exhaust metadata connection pools.

## Problem
How do we isolate analytical query execution to prevent write mutations and connection starvation of application metadata?

## Options Considered
1. **Option 1: Single Database & Shared Connection Pool**: Execute metadata and analytics against the same database engine.
2. **Option 2: Dual Connection Pools with Strict Engine Isolation & Read-Only Credentials**:
   - `metadata_engine`: Manages user accounts, JWT revocation, data policies, query history, and audit logs.
   - `business_engine`: Dedicated read-only execution sandbox engine with hard statement timeouts, row caps, and isolated connection pool sizing.

## Decision
We chose **Option 2: Dual Connection Pools with Strict Engine Isolation & Read-Only Credentials**.

## Trade-offs & Consequences
- **Positive**:
  - Eliminates blast radius: Heavy analytical queries cannot starve metadata/auth connections.
  - Fail-closed write protection: Sandboxed database user lacks `INSERT`, `UPDATE`, `DELETE`, and `DROP` privileges.
  - Explicit connection pool tuning: `pool_size`, `max_overflow`, `pool_timeout`, and `pool_recycle` are tuned independently.
- **Negative**:
  - Requires maintaining two database connection configurations.
