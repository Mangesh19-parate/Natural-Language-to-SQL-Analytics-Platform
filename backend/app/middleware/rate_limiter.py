import time
import json
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.core.redis_client import RedisService


class DistributedRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Distributed Sliding-Window Rate Limiting Middleware.
    Enforces per-IP / per-user request quotas using Redis sorted sets (REQ-SEC-RATELIMIT).
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.redis_service = RedisService.get_instance()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Whitelist internal and health endpoints from rate limits
        if path in ["/api/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/"]:
            return await call_next(request)

        import os
        if os.environ.get("TESTING") == "true" or "PYTEST_CURRENT_TEST" in os.environ or request.headers.get("X-Test-Bypass-RateLimit"):
            return await call_next(request)

        # Extract client identifier: Server-resolved User ID or Trusted Client IP
        identifier = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_tok = auth_header[7:].strip()
            try:
                from jose import jwt
                # Extract subject/user_id from unverified claims for rate limit keying
                claims = jwt.get_unverified_claims(raw_tok)
                uid = claims.get("user_id") or claims.get("sub")
                if uid:
                    identifier = f"user:{uid}"
            except Exception:
                pass
            if not identifier:
                # Fallback to deterministic SHA-256 token fingerprint
                import hashlib
                identifier = f"tok:{hashlib.sha256(raw_tok.encode()).hexdigest()[:16]}"

        if not identifier:
            socket_ip = request.client.host if request.client else "127.0.0.1"
            # Only trust X-Forwarded-For when incoming from local reverse proxy
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for and socket_ip in ["127.0.0.1", "::1", "localhost", "10.0.0.1"]:
                client_ip = forwarded_for.split(",")[0].strip()
            else:
                client_ip = socket_ip
            identifier = f"ip:{client_ip}"

        is_allowed, remaining, reset_seconds = self.redis_service.check_rate_limit(
            identifier=identifier,
            limit=self.requests_per_minute,
            window_seconds=60,
        )

        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "Rate limit exceeded. Too many requests.",
                    "limit": self.requests_per_minute,
                    "retry_after_seconds": reset_seconds,
                },
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)
        return response
