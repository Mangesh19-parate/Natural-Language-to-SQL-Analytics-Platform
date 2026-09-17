# ADR-004: Event-Loop Concurrency Isolation & Worker Threadpool Offloading

## Status
Accepted

## Date
2026-09-17

## Context and Problem Statement
FastAPI is built upon Starlette and AsyncIO. A fundamental characteristic of the AsyncIO event loop is that it is single-threaded. When route handlers are declared with `async def`, FastAPI executes them directly on the primary event loop thread.

If an `async def` handler invokes synchronous blocking operations—such as:
1. Synchronous database queries via SQLAlchemy (`db.query(...)`, `db.commit()`),
2. Foreign database connections and SQL execution (`ExecutionSandboxService.execute_query`),
3. CPU-bound AST parsing, traversal, and dynamic programming algorithms (`SQLglot`, `CostBasedJoinOptimizer`),
the entire asyncio event loop freezes for all other concurrent requests, causing severe latency spikes, head-of-line blocking, and connection timeouts under load.

## Decision Drivers
- **Non-Blocking Throughput**: Maintain high requests-per-second (RPS) under concurrent load without event loop starvation.
- **Predictable Latency Profiles**: p95 and p99 latencies must remain bounded during burst traffic.
- **Resource Protection**: Prevent unbound request payloads and query timeouts from exhausting worker threads or database connection pools.

## Decision Outcome
Chosen Pattern: **Synchronous Route Declaration (`def`) for Threadpool Execution & Parameter Bounding**.

### Architectural Design:
1. **Threadpool Worker Offloading**:
   - Synchronous route handlers (`def`) are natively offloaded by Starlette/FastAPI into an `anyio.to_thread` worker threadpool.
   - Synchronous operations (AST validation, database lookups, query sandboxing, cost-based join optimization) execute in isolated worker threads, keeping the asyncio event loop unblocked for concurrent HTTP I/O.
   - Truly asynchronous operations (LLM streaming, async HTTP dispatch) remain `async def`.
2. **Request Parameter Upper Bounding**:
   - Pydantic models enforce strict bounds on all user-supplied parameters:
     - `timeout_seconds`: `Field(default=10.0, ge=0.5, le=30.0)`
     - `max_rows`: `Field(default=1000, ge=1, le=10000)`
     - `sql`: `Field(..., min_length=1, max_length=20000)`
     - `max_retries`: `Field(default=3, ge=1, le=5)`
3. **Connection Pool Isolation**:
   - Separate metadata engine and business query execution engine to prevent analytic query spikes from starving application metadata or authentication sessions.

### Consequences
- **Positive**:
  - Event loop stays responsive under 100+ parallel concurrent workloads.
  - Eliminates thread contention on shared in-memory database sessions.
  - Prevents unbounded denial-of-service payloads.
- **Negative**:
  - Threadpool capacity must be appropriately sized for peak concurrent blocking queries.
