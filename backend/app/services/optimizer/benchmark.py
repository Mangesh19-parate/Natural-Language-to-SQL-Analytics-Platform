import time
import statistics
from typing import List, Tuple, Any
from sqlalchemy import Engine, text
from app.schemas.optimize import ExecutionBenchmarkResult


def benchmark_execution(
    original_sql: str,
    optimized_sql: str,
    engine: Engine,
    max_rows: int = 1000,
    warmup_trials: int = 2,
    timed_trials: int = 5,
) -> ExecutionBenchmarkResult:
    """
    Executes original and rewritten SQL queries against the database engine with multi-trial profiling.
    Features:
    - 2 warmup iterations to prime engine caches
    - 5 measured iterations to compute median, min, max, and p95 latency
    - Strict row streaming limit to prevent memory exhaustion
    - Exact multiset result set equivalence verification
    """
    def run_single(conn, query_str: str) -> Tuple[List[Any], float]:
        t0 = time.perf_counter()
        result = conn.execute(text(query_str))
        rows = result.fetchmany(max_rows)
        t1 = time.perf_counter()
        return rows, (t1 - t0) * 1000.0

    try:
        with engine.connect() as conn:
            # 1. Warmup trials to avoid cold-cache distortion
            for _ in range(warmup_trials):
                conn.execute(text(original_sql)).fetchmany(10)
                conn.execute(text(optimized_sql)).fetchmany(10)

            # 2. Timed trials for original query
            orig_times: List[float] = []
            orig_rows: List[Any] = []
            for _ in range(timed_trials):
                rows, dur = run_single(conn, original_sql)
                orig_times.append(dur)
                if not orig_rows:
                    orig_rows = rows

            # 3. Timed trials for optimized query
            opt_times: List[float] = []
            opt_rows: List[Any] = []
            for _ in range(timed_trials):
                rows, dur = run_single(conn, optimized_sql)
                opt_times.append(dur)
                if not opt_rows:
                    opt_rows = rows

        orig_median = round(statistics.median(orig_times), 3)
        opt_median = round(statistics.median(opt_times), 3)
        orig_min = round(min(orig_times), 3)
        opt_min = round(min(opt_times), 3)
        
        # Approximate p95
        sorted_orig = sorted(orig_times)
        sorted_opt = sorted(opt_times)
        orig_p95 = round(sorted_orig[int(0.95 * len(sorted_orig))], 3) if sorted_orig else orig_median
        opt_p95 = round(sorted_opt[int(0.95 * len(sorted_opt))], 3) if sorted_opt else opt_median

        orig_count = len(orig_rows)
        
        # Exact tuple equivalence check
        orig_serialized = sorted([str(tuple(r)) for r in orig_rows])
        opt_serialized = sorted([str(tuple(r)) for r in opt_rows])
        results_match = (orig_serialized == opt_serialized)

        speedup = round(orig_median / max(opt_median, 0.001), 2)

        return ExecutionBenchmarkResult(
            original_exec_ms=orig_median,
            optimized_exec_ms=opt_median,
            speedup_ratio=speedup,
            results_equivalent=results_match,
            row_count=orig_count,
            validation_status="VERIFIED_EQUIVALENT" if results_match else "DATA_MISMATCH",
            trials_run=timed_trials,
            original_p95_ms=orig_p95,
            optimized_p95_ms=opt_p95,
            original_min_ms=orig_min,
            optimized_min_ms=opt_min,
        )
    except Exception as e:
        return ExecutionBenchmarkResult(
            original_exec_ms=0.0,
            optimized_exec_ms=0.0,
            speedup_ratio=1.0,
            results_equivalent=False,
            row_count=0,
            validation_status=f"BENCHMARK_ERROR: {str(e)}",
            trials_run=0,
        )
