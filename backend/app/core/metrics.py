import time
from collections import defaultdict
from typing import Dict, Any, List
from threading import Lock


class MetricsCollector:
    """
    In-memory Prometheus & Telemetry Metrics Collector for Trust Engine.
    Collects request counts, latency distributions, policy blocks, and pipeline metrics.
    Exports in standard Prometheus text format (`/metrics`) and JSON (`/api/observatory/metrics`).
    """

    def __init__(self):
        self._lock = Lock()
        self._http_requests_total = defaultdict(int)  # (method, path, status_code) -> count
        self._http_duration_seconds_sum = defaultdict(float)  # (method, path) -> sum
        self._http_duration_seconds_count = defaultdict(int)  # (method, path) -> count
        self._sql_executions_total = defaultdict(int)  # (status, stage) -> count
        self._policy_violations_total = defaultdict(int)  # (violation_type, role) -> count
        self._llm_requests_total = defaultdict(int)  # (provider, model, status) -> count
        self._llm_latency_seconds_sum = defaultdict(float)
        self._llm_latency_seconds_count = defaultdict(int)
        self._active_sessions = 0
        self._start_time = time.time()

    def record_http_request(self, method: str, path: str, status_code: int, duration_seconds: float):
        with self._lock:
            # Normalize path (e.g. /api/report/123/download -> /api/report/{id}/download)
            norm_path = path.split("?")[0]
            self._http_requests_total[(method, norm_path, str(status_code))] += 1
            self._http_duration_seconds_sum[(method, norm_path)] += duration_seconds
            self._http_duration_seconds_count[(method, norm_path)] += 1

    def record_sql_pipeline_step(self, stage: str, status: str):
        with self._lock:
            self._sql_executions_total[(stage, status)] += 1

    def record_policy_violation(self, violation_type: str, role_name: str = "unknown"):
        with self._lock:
            self._policy_violations_total[(violation_type, role_name)] += 1

    def record_llm_request(self, provider: str, model: str, status: str, latency_seconds: float):
        with self._lock:
            self._llm_requests_total[(provider, model, status)] += 1
            self._llm_latency_seconds_sum[(provider, model)] += latency_seconds
            self._llm_latency_seconds_count[(provider, model)] += 1

    def export_prometheus_format(self) -> str:
        """Generates valid Prometheus text exposition format (version 0.0.4)."""
        lines: List[str] = [
            "# HELP trustengine_http_requests_total Total count of HTTP requests processed by the API.",
            "# TYPE trustengine_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), count in self._http_requests_total.items():
                lines.append(f'trustengine_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')

            lines.append("# HELP trustengine_http_request_duration_seconds Duration of HTTP requests in seconds.")
            lines.append("# TYPE trustengine_http_request_duration_seconds summary")
            for (method, path), sum_dur in self._http_duration_seconds_sum.items():
                count = self._http_duration_seconds_count[(method, path)]
                lines.append(f'trustengine_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {sum_dur:.6f}')
                lines.append(f'trustengine_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}')

            lines.append("# HELP trustengine_sql_executions_total Total SQL pipeline actions and validations.")
            lines.append("# TYPE trustengine_sql_executions_total counter")
            for (stage, status), count in self._sql_executions_total.items():
                lines.append(f'trustengine_sql_executions_total{{stage="{stage}",status="{status}"}} {count}')

            lines.append("# HELP trustengine_policy_violations_total Total governance policy violations blocked.")
            lines.append("# TYPE trustengine_policy_violations_total counter")
            for (v_type, role), count in self._policy_violations_total.items():
                lines.append(f'trustengine_policy_violations_total{{type="{v_type}",role="{role}"}} {count}')

            lines.append("# HELP trustengine_llm_requests_total Total LLM provider generation calls.")
            lines.append("# TYPE trustengine_llm_requests_total counter")
            for (provider, model, status), count in self._llm_requests_total.items():
                lines.append(f'trustengine_llm_requests_total{{provider="{provider}",model="{model}",status="{status}"}} {count}')

            uptime = time.time() - self._start_time
            lines.append("# HELP trustengine_process_uptime_seconds Process uptime in seconds.")
            lines.append("# TYPE trustengine_process_uptime_seconds gauge")
            lines.append(f"trustengine_process_uptime_seconds {uptime:.2f}")

        return "\n".join(lines) + "\n"

    def export_summary_json(self) -> Dict[str, Any]:
        """Provides structured telemetry summary for application dashboards."""
        with self._lock:
            total_reqs = sum(self._http_requests_total.values())
            total_violations = sum(self._policy_violations_total.values())
            total_sql = sum(self._sql_executions_total.values())
            total_llm = sum(self._llm_requests_total.values())
            uptime = time.time() - self._start_time

            return {
                "uptime_seconds": round(uptime, 2),
                "total_http_requests": total_reqs,
                "total_sql_executions": total_sql,
                "total_policy_violations_blocked": total_violations,
                "total_llm_requests": total_llm,
                "http_requests_breakdown": [
                    {"method": m, "path": p, "status": s, "count": c}
                    for (m, p, s), c in self._http_requests_total.items()
                ],
                "policy_violations_breakdown": [
                    {"violation_type": vt, "role": r, "count": c}
                    for (vt, r), c in self._policy_violations_total.items()
                ],
            }


# Singleton Global Metrics Collector
metrics = MetricsCollector()
