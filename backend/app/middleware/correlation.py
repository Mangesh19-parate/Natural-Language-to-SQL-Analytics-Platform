import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import correlation_id_ctx
from app.core.metrics import metrics

logger = logging.getLogger("trustengine.http")


class CorrelationAndMetricsMiddleware(BaseHTTPMiddleware):
    """
    Enterprise middleware for:
    1. Distributed Request Tracing (X-Correlation-ID / X-Request-ID propagation)
    2. Response Latency Headers (X-Process-Time)
    3. Real-time Telemetry and Prometheus Metrics recording
    4. Structured Access Logging
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate Correlation ID
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )
        token = correlation_id_ctx.set(correlation_id)

        start_time = time.perf_counter()
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            duration_s = time.perf_counter() - start_time
            duration_ms = duration_s * 1000

            # Attach tracing headers to response
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

            # Record telemetry metrics
            metrics.record_http_request(
                method=method,
                path=path,
                status_code=response.status_code,
                duration_seconds=duration_s,
            )

            # Access log
            logger.info(
                f"{method} {path} - {response.status_code} ({duration_ms:.2f}ms) [cid={correlation_id}]"
            )

            return response

        except Exception as exc:
            duration_s = time.perf_counter() - start_time
            metrics.record_http_request(
                method=method,
                path=path,
                status_code=500,
                duration_seconds=duration_s,
            )
            logger.error(
                f"Unhandled exception during {method} {path} [cid={correlation_id}]: {exc}",
                exc_info=True,
            )
            raise exc
        finally:
            correlation_id_ctx.reset(token)
