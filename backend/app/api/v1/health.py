from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db, get_business_db
from app.schemas.common import HealthResponse
from app.config import settings

router = APIRouter(tags=["Health"])


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

    status = "healthy" if (meta_connected or biz_connected) else "degraded"

    return HealthResponse(
        status=status,
        environment=settings.ENVIRONMENT,
        metadata_db_connected=meta_connected,
        business_db_connected=biz_connected,
        version="1.2.0"
    )
