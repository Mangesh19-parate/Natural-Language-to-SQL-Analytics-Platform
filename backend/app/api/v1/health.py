import os
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.schemas.common import HealthResponse
from app.config import settings
from app.core.metrics import metrics

router = APIRouter(tags=["Health & Telemetry"])


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    meta_connected = False
    biz_connected = False
    
    try:
        db.execute(text("SELECT 1"))
        meta_connected = True
    except Exception:
        meta_connected = False

    try:
        from app.db.session import BusinessSessionLocal
        biz_db = BusinessSessionLocal()
        biz_db.execute(text("SELECT 1"))
        biz_connected = True
        biz_db.close()
    except Exception:
        biz_connected = False

    status_str = "healthy" if (meta_connected or biz_connected) else "degraded"

    return HealthResponse(
        status=status_str,
        environment=settings.ENVIRONMENT,
        metadata_db_connected=meta_connected,
        business_db_connected=biz_connected,
        version="1.2.0"
    )


@router.get("/health/ready")
def get_readiness_probe(db: Session = Depends(get_db)):
    """
    Kubernetes & Container Readiness Probe (REQ-OPS-01).
    Returns 200 OK when databases are connected and ready to serve traffic.
    Returns 503 Service Unavailable if downstream dependencies fail.
    """
    errors = []
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        errors.append(f"Metadata DB unreachable: {str(e)}")

    try:
        from app.db.session import BusinessSessionLocal
        biz_db = BusinessSessionLocal()
        biz_db.execute(text("SELECT 1"))
        biz_db.close()
    except Exception as e:
        errors.append(f"Business DB unreachable: {str(e)}")

    if errors:
        return Response(
            content=f'{{"status": "not_ready", "errors": {errors}}}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )

    return {
        "status": "ready",
        "environment": settings.ENVIRONMENT,
        "database_connections": "healthy",
    }


@router.get("/health/live")
def get_liveness_probe():
    """
    Kubernetes & Container Liveness Probe (REQ-OPS-02).
    Returns 200 OK indicating the application process is running.
    """
    return {"status": "alive"}


@router.get("/metrics")
def get_prometheus_metrics():
    """
    Prometheus Scraping Endpoint (REQ-OPS-03).
    Exports telemetry metrics in standard Prometheus text format.
    """
    body = metrics.export_prometheus_format()
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
