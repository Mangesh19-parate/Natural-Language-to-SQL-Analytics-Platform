from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.schemas.replay import (
    ProvenancePackage,
    QueryReplayResponse,
)
from app.schemas.common import StandardResponse
from app.services.auth_service import get_current_user_optional
from app.services.query_replay import QueryReplayService

router = APIRouter(prefix="/replay", tags=["Query Replay & Provenance"])


@router.get("/{query_id}", response_model=StandardResponse[ProvenancePackage])
def get_provenance_record(
    query_id: str,
    data_source_id: int = Query(1, description="Data source ID"),
    db: Session = Depends(get_db),
):
    """
    Retrieves full reproducibility provenance package for a past query run (REQ-REPLAY-01),
    including schema snapshot comparison and schema drift alerts (Day 81–82).
    """
    try:
        provenance = QueryReplayService.get_provenance_package(
            db=db,
            query_id=query_id,
            data_source_id=data_source_id,
        )
        return StandardResponse(
            success=True,
            message="Provenance package retrieved",
            data=provenance,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{query_id}", response_model=StandardResponse[QueryReplayResponse])
def replay_query_endpoint(
    query_id: str,
    role_id: Optional[int] = Query(None, description="Role ID to replay under"),
    data_source_id: int = Query(1, description="Data source ID"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Executes a reproducible rerun of a past query run and computes result hash comparison (REQ-REPLAY-01).
    """
    effective_role_id = role_id
    if effective_role_id is None and current_user:
        effective_role_id = current_user.role_id
    if effective_role_id is None:
        effective_role_id = 1  # Default admin/analyst role

    try:
        replay_res = QueryReplayService.replay_and_verify(
            db=db,
            query_id=query_id,
            role_id=effective_role_id,
            data_source_id=data_source_id,
        )
        return StandardResponse(
            success=True,
            message=replay_res.reproducibility_message,
            data=replay_res,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
