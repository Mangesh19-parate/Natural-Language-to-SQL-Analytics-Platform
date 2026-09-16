from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db, business_engine
from app.models.auth import User
from app.schemas.common import StandardResponse
from app.schemas.intent import (
    IntentClassifyRequest,
    IntentResolveRequest,
    IntentAnalysisResult,
)
from app.services.auth_service import get_current_user, get_effective_role_id
from app.services.semantic_catalog_service import SemanticCatalogService
from app.services.query_classifier import QueryClassifierService

router = APIRouter(prefix="/intent", tags=["Intent Analysis & Ambiguity"])


@router.post("/classify", response_model=StandardResponse[IntentAnalysisResult])
async def classify_intent(
    request: IntentClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    POST /api/intent/classify — Classifies question into Answerable / Ambiguous / Unsupported / Unauthorized (Rule R2.1).
    Strictly derives effective role from authenticated session.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty.")

    effective_role_id = get_effective_role_id(current_user, request.role_id)

    # Retrieve policy-filtered catalog for role
    catalog = SemanticCatalogService.get_catalog_for_role(
        db=db,
        data_source_id=request.data_source_id or 1,
        role_id=effective_role_id,
        business_engine=business_engine
    )

    result = QueryClassifierService.classify_question(
        question=request.question,
        catalog=catalog
    )

    return StandardResponse(
        success=True,
        message=f"Question classified as: {result.classification.value}",
        data=result
    )


@router.post("/resolve", response_model=StandardResponse[str])
async def resolve_intent(request: IntentResolveRequest):
    """
    POST /api/intent/resolve — Resolves ambiguous option selection into a concrete question.
    """
    resolved_q = QueryClassifierService.resolve_ambiguity(
        original_question=request.original_question,
        selected_option=request.selected_option
    )
    return StandardResponse(
        success=True,
        message="Ambiguity successfully resolved",
        data=resolved_q
    )
