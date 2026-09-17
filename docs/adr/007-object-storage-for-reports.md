# ADR-007: Object Storage Service Abstraction (S3 / MinIO / Local Disk) for Generated Artifacts

## Status
Accepted

## Date
2026-09-17

## Context
The platform generates binary and structured artifacts, including multi-page PDF executive summaries, Excel workbooks with embedded charts, and historical evaluation benchmark JSON dumps. Storing binary blobs directly in the relational PostgreSQL/SQLite database causes database bloat, backup slowness, and high memory consumption during serialization.

## Problem
How do we store and serve generated file artifacts reliably across multi-instance cloud deployments?

## Options Considered
1. **Option 1: Database BLOB Columns**: Store bytes directly in `BYTEA`/`BLOB` table columns.
2. **Option 2: Local Ephemeral Server Disk**: Save files to local `/tmp` or server filesystem.
3. **Option 3: Unified Object Storage Service Abstraction (S3 / MinIO / Local Disk Fallback)**:
   - Interface `store_artifact(content, filename, content_type)` returns a deterministic URI and metadata (`file_key`, `size_bytes`, `storage_backend`).
   - Supports local disk for development, MinIO for on-premise deployments, and AWS S3 for cloud environments.

## Decision
We chose **Option 3: Unified Object Storage Service Abstraction**.

## Trade-offs & Consequences
- **Positive**:
  - Keeps relational database lean and performant.
  - Horizontally scalable: Any API replica can generate and retrieve artifacts from shared object storage.
  - Zero-change deployment: Works transparently on local developer machines or AWS S3.
- **Negative**:
  - Requires S3 bucket provisioning and credentials in production environments.
