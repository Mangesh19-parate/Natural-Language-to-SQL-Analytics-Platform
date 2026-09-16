from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.auth import User
from app.schemas.agent import (
    PlanCompoundAnalysisRequest,
    PlanCompoundAnalysisResponse,
)
from app.schemas.common import StandardResponse
from app.services.auth_service import get_current_user, get_effective_role_id
from app.services.planner_agent import PlannerAgentService

router = APIRouter(prefix="/agent", tags=["Multi-Step Planner Agent"])


@router.post("/execute", response_model=StandardResponse[PlanCompoundAnalysisResponse])
async def execute_planner_agent(
    request: PlanCompoundAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes compound multi-step analytical workflow (REQ-AGENT-01 / Task T-44 / Week 14 P2).
    Decomposes question into sub-tasks, enforces Policy Engine on every step, and returns execution trace.
    Strictly derives effective role from authenticated session.
    """
    effective_role_id = get_effective_role_id(current_user, request.role_id)
    result = await PlannerAgentService.execute_plan(
        db=db,
        question=request.question,
        role_id=effective_role_id,
        data_source_id=request.data_source_id,
    )
    return StandardResponse(
        success=True,
        message="Multi-step compound plan executed",
        data=result,
    )

