from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import User
from app.models.session import QueryHistory
from app.schemas.replay import (
    ProvenancePackage,
    QueryReplayResponse,
)
from app.schemas.common import StandardResponse
from app.services.auth_service import get_current_user, get_effective_role_id, authorize_resource_access
from app.services.query_replay import QueryReplayService

router = APIRouter(prefix="/replay", tags=["Query Replay & Provenance"])


@router.get("/{query_id}", response_model=StandardResponse[ProvenancePackage])
def get_provenance_record(
    query_id: str,
    data_source_id: Optional[int] = Query(None, description="Data source ID (defaults to query's recorded data source)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full reproducibility provenance package for a past query run (REQ-REPLAY-01),
    including schema snapshot comparison and schema drift alerts (Day 81–82).
    Strictly enforces resource ownership: non-admin callers can only inspect their own queries.
    """
    # 1. Authorize resource ownership
    query_record = db.query(QueryHistory).filter(QueryHistory.query_id == query_id).first()
    if not query_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Query {query_id} not found",
        )
    authorize_resource_access(query_record.user_id, current_user, "query provenance", "view provenance for")

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
    role_id: Optional[int] = Query(None, description="Role ID to replay under (Admin only)"),
    data_source_id: Optional[int] = Query(None, description="Data source ID (defaults to query's recorded data source)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes a reproducible rerun of a past query run and computes result hash comparison (REQ-REPLAY-01).
    Strictly enforces resource ownership: non-admin callers can only replay their own queries.
    Strictly derives effective role from authenticated session.
    """
    # 1. Authorize resource ownership
    query_record = db.query(QueryHistory).filter(QueryHistory.query_id == query_id).first()
    if not query_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Query {query_id} not found",
        )
    authorize_resource_access(query_record.user_id, current_user, "historical query", "replay")

    effective_role_id = get_effective_role_id(current_user, role_id)

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

