from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.schemas.observatory import (
    FailureObservatoryStatsResponse,
    ProblematicPhraseItem,
    FailureLogItem,
)
from app.schemas.common import StandardResponse
from app.services.observatory_service import ObservatoryService

router = APIRouter(prefix="/observatory", tags=["Failure Observatory"])


class LogFailureRequest(BaseModel):
    failure_class: str
    query_id: Optional[str] = None
    problematic_phrase: Optional[str] = None


@router.get("/stats", response_model=StandardResponse[FailureObservatoryStatsResponse])
def get_failure_observatory_stats(db: Session = Depends(get_db)):
    """
    Retrieves Failure Observatory aggregation metrics across all 7 taxonomy classes (REQ-FAILOBS-01).
    """
    stats = ObservatoryService.get_observatory_stats(db)
    return StandardResponse(
        success=True,
        message="Failure observatory statistics aggregated",
        data=stats,
    )


@router.get("/phrases", response_model=StandardResponse[List[ProblematicPhraseItem]])
def get_problematic_phrases(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Returns the top problematic natural-language phrases and recommended catalog interventions.
    """
    phrases = ObservatoryService.get_top_problematic_phrases(db, limit=limit)
    return StandardResponse(
        success=True,
        message="Top problematic phrases retrieved",
        data=phrases,
    )


@router.get("/logs", response_model=StandardResponse[List[FailureLogItem]])
def get_recent_failure_logs(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns recent failure log feed.
    """
    logs = ObservatoryService.get_failure_logs(db, limit=limit)
    return StandardResponse(
        success=True,
        message="Failure logs retrieved",
        data=logs,
    )


@router.post("/log", response_model=StandardResponse[FailureLogItem])
def log_failure_event(
    request: LogFailureRequest,
    db: Session = Depends(get_db),
):
    """
    Logs an explicit failure occurrence into the observatory stream.
    """
    record = ObservatoryService.log_failure(
        db=db,
        failure_class=request.failure_class,
        query_id=request.query_id,
        problematic_phrase=request.problematic_phrase,
    )
    return StandardResponse(
        success=True,
        message="Failure event logged",
        data=FailureLogItem.model_validate(record),
    )
