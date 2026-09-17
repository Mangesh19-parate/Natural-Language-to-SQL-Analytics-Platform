# ADR-006: Worker-Based Offloading for Long-Running Evaluation & Report Jobs

## Status
Accepted

## Date
2026-09-17

## Context
Certain analytical and administrative workflows—such as executing the 165-query Evaluation Lab benchmark, 128-case adversarial security attack suite, or rendering multi-page PDF/Excel analytical reports—take between 5 and 90 seconds of compute time. Executing these synchronously on HTTP request threads risks HTTP gateway timeouts and resource starvation.

## Problem
How do we execute heavy computational tasks without blocking API request threads?

## Options Considered
1. **Option 1: Synchronous In-Band Execution**: Run the job directly within the HTTP handler.
2. **Option 2: Async Background Worker Queue Architecture**:
   - `POST /jobs` creates a job record in the database/Redis queue and returns a `job_id` with HTTP 202 Accepted.
   - Background worker processes dequeue and execute long-running tasks.
   - Status & results are polled via `GET /jobs/{job_id}` or notified via WebSockets/SSE.

## Decision
We chose **Option 2: Async Background Worker Queue Architecture**.

## Trade-offs & Consequences
- **Positive**:
  - API HTTP handlers return immediately in $< 20\text{ms}$.
  - Resilient to network disconnects: Clients can reconnect and retrieve job results anytime.
  - Workers can be scaled independently of API frontends based on queue depth.
- **Negative**:
  - Requires polling or event streaming for client notification.
