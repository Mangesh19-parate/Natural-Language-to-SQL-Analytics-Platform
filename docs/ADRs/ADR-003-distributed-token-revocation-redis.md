# ADR-003: Distributed Token Revocation via Redis Key-Value Store and Fail-Closed Database Fallback

## Status
Accepted

## Date
2026-09-17

## Context and Problem Statement
In stateless JWT authentication architectures, tokens remain cryptographically valid until their expiry timestamp (`exp`). This presents severe security vulnerabilities:
1. **Immediate Revocation**: Users cannot immediately invalidate compromised tokens or session keys upon explicit logout, password change, or permission downgrade.
2. **Horizontal Scalability**: In multi-instance or containerized deployments, local in-memory blacklists (`set()` or `dict`) are not shared across nodes, allowing revoked tokens on Node A to remain valid on Node B.
3. **Fail-Closed Guarantee**: In the event of caching layer partition or restart, token validation must strictly deny access to revoked credentials without failing open.

## Decision Drivers
- **Distributed Invalidation**: Sub-millisecond revocation lookups across all horizontally scaled backend replicas.
- **Fail-Closed Security**: Reject authentication if cryptographic token hash or `jti` is found in the revocation index.
- **Automatic Expiry & Memory Bounding**: Revocation entries must expire automatically from cache when `exp` passes (TTL = `token_exp - now`), preventing unbounded memory growth.
- **Persistent Auditability**: Revocation events must be permanently recorded for compliance and security audit trails.

## Considered Options
1. **Option 1: In-Memory Python Set**: Fast local lookup, but fails across multiple backend workers or processes and loses state on restart.
2. **Option 2: Database-Only Table (SQL)**: Persistent and shared across replicas, but adds sequential database query overhead (~2-10ms) to every authenticated HTTP request.
3. **Option 3: Hybrid Redis Key-Value Cache with Fail-Closed SQL Persistence**: Sub-millisecond distributed lookups in Redis (`revoked:{jti}` with TTL) backed by a relational `revoked_tokens` table.

## Decision Outcome
Chosen Option: **Option 3: Hybrid Redis Key-Value Cache with Fail-Closed SQL Persistence**.

### Architectural Design:
1. **Token Issuance**: Every access and refresh token receives a cryptographically unique `jti` (UUID4) and SHA-256 hash payload.
2. **Revocation Flow (`/api/auth/logout`, `/api/auth/revoke`)**:
   - Computes remaining token lifetime: $\Delta t = \text{exp} - \text{now}$.
   - Sets Redis key `revoked_token:{jti}` with TTL $\Delta t$.
   - Inserts record into `RevokedToken` relational table (`jti`, `token_hash`, `revoked_at`, `expires_at`).
3. **Verification Flow (`get_current_user`, `decode_token`)**:
   - Check Redis cache for `revoked_token:{jti}` ($O(1)$ < 0.5ms).
   - If Redis is unavailable or unconfigured, execute indexed lookup on `RevokedToken` table in relational DB.
   - If present in either store $\rightarrow$ Raise HTTP 401 Unauthorized (`"Token has been revoked"`).

### Consequences
- **Positive**:
  - Immediate, synchronized token revocation across all backend instances.
  - Zero memory leaks due to native Redis key TTL eviction matching token expiration.
  - Fail-closed security posture preventing token reuse after logout.
- **Negative**:
  - Introduces Redis dependency for optimal distributed performance (with graceful relational fallback).
