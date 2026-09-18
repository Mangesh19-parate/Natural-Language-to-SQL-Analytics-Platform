from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.router import api_router
from app.db.base import Base, BusinessBase
from app.db.session import metadata_engine, business_admin_engine
from app.middleware.correlation import CorrelationAndMetricsMiddleware
from app.middleware.rate_limiter import DistributedRateLimitMiddleware
from app.core.metrics import metrics
from app.core.logging_config import setup_logging

# Initialize logging
setup_logging(log_level="INFO", json_format=not settings.DEBUG)

# Initialize tables for dev/local setup if enabled (decoupled in production for privilege separation)
if getattr(settings, "DEBUG", True) and getattr(settings, "AUTO_CREATE_TABLES", False):
    Base.metadata.create_all(bind=metadata_engine)
    BusinessBase.metadata.create_all(bind=business_admin_engine)

app = FastAPI(
    title="Intelligent SQL Assistant (Trust Engine) API",
    version="1.2.0",
    description="A Trustworthy Natural-Language Analytics Engine with Verification, Self-Correction and Evidence-Grounded Query Execution.",
    debug=settings.DEBUG
)

# Custom correlation tracing & metrics middleware
app.add_middleware(CorrelationAndMetricsMiddleware)

# Distributed Sliding-Window Rate Limiting Middleware (REQ-SEC-RATELIMIT)
app.add_middleware(DistributedRateLimitMiddleware, requests_per_minute=120)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Correlation-ID"],
)

app.include_router(api_router, prefix="/api")


@app.get("/metrics", tags=["Telemetry"])
def get_root_prometheus_metrics():
    """Root Prometheus metrics scraper endpoint (REQ-OPS-03)."""
    return Response(
        content=metrics.export_prometheus_format(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/")
def root():
    return {
        "app": "Intelligent SQL Assistant (Trust Engine)",
        "version": "1.2.0",
        "docs": "/docs",
        "health": "/api/health",
        "metrics": "/metrics"
    }
