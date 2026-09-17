"""
Reproducible Concurrency Scalability Experiment Runner.
Executes automated concurrency sweeps across 10, 25, 50, 100, and 250 simulated concurrent users.
Measures and prints p50, p90, p95, p99 latencies, requests per second (RPS), and error rates.
"""

import asyncio
import time
import statistics
import httpx
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.db.session import SessionLocal, get_db
from app.models.policy import DataSource, DataPolicy
from app.models.auth import Role, User
from app.services.auth_service import AuthService


def compute_metrics(latencies: list[float], total_duration_s: float, error_count: int) -> dict:
    if not latencies:
        return {"count": 0, "rps": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "errors": error_count}
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    rps = round(n / total_duration_s, 2) if total_duration_s > 0 else 0.0
    return {
        "count": n,
        "rps": rps,
        "p50": round(statistics.median(sorted_lats) * 1000, 2),
        "p90": round(sorted_lats[int(n * 0.90) if int(n * 0.90) < n else n - 1] * 1000, 2),
        "p95": round(sorted_lats[int(n * 0.95) if int(n * 0.95) < n else n - 1] * 1000, 2),
        "p99": round(sorted_lats[int(n * 0.99) if int(n * 0.99) < n else n - 1] * 1000, 2),
        "errors": error_count,
    }


async def run_benchmark_for_concurrency(concurrency: int) -> dict:
    transport = httpx.ASGITransport(app=app)
    timeout = httpx.Timeout(60.0)

    token = AuthService.create_access_token({
        "sub": "1",
        "user_id": 1,
        "email": "admin@trustengine.ai",
        "role_name": "admin",
        "role_id": 1,
    })
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "sql": "SELECT * FROM employees e JOIN departments d ON e.department_id = d.department_id JOIN sales s ON e.employee_id = s.employee_id",
        "data_source_id": 1,
        "max_allowed_cost": 500000.0,
    }

    latencies = []
    errors = 0

    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=timeout) as client:
        async def send_single():
            nonlocal errors
            t0 = time.perf_counter()
            try:
                resp = await client.post("/api/optimize/join-plan", json=payload, headers=headers)
                t1 = time.perf_counter()
                if resp.status_code == 200:
                    latencies.append(t1 - t0)
                else:
                    errors += 1
            except Exception:
                errors += 1

        t_start = time.perf_counter()
        await asyncio.gather(*(send_single() for _ in range(concurrency)))
        t_end = time.perf_counter()

    return compute_metrics(latencies, t_end - t_start, errors)


async def main():
    print("\n" + "=" * 80)
    print("  REPRODUCIBLE CONCURRENCY SCALABILITY EXPERIMENT (Trust Engine API)")
    print("=" * 80)

    concurrency_levels = [10, 25, 50, 100, 250]
    results = []

    for c in concurrency_levels:
        print(f"Executing concurrency sweep with {c} parallel users...")
        m = await run_benchmark_for_concurrency(c)
        results.append((c, m))
        await asyncio.sleep(0.5)

    print("\n### Scalability Benchmark Results Table\n")
    print("| Concurrent Users | Total Requests | RPS (Throughput) | p50 Latency (ms) | p95 Latency (ms) | p99 Latency (ms) | Errors |")
    print("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for c, m in results:
        print(f"| {c} | {m['count']} | {m['rps']} req/s | {m['p50']} ms | {m['p95']} ms | {m['p99']} ms | {m['errors']} |")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
