from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.query import (
    SQLGenerateRequest,
    SQLGenerateResponse,
    SQLValidateRequest,
    SQLValidateResponse,
)
from app.services.sql_generator import SQLGeneratorService
from app.services.policy_engine import PolicyEngine
from app.services.sql_parser import SQLASTParser

router = APIRouter(prefix="/sql", tags=["SQL Generation & Policy Engine"])


@router.post("/generate", response_model=SQLGenerateResponse)
async def generate_sql_proposal(
    request: SQLGenerateRequest,
    db: Session = Depends(get_db),
):
    """
    Generates a SQL query proposal via LLM provider using the role's Semantic Catalog,
    and subjects it to deterministic AST & Policy Engine validation (Principle R0).
    """
    generator = SQLGeneratorService()
    response = await generator.generate_sql_proposal(
        db=db,
        question=request.question,
        role_id=request.role_id,
        data_source_id=request.data_source_id,
        clarifications=request.clarifications,
    )
    return response


@router.post("/validate", response_model=SQLValidateResponse)
async def validate_sql(
    request: SQLValidateRequest,
    db: Session = Depends(get_db),
):
    """
    Performs deterministic AST and Policy Engine authorization checks on any SQL statement.
    """
    analysis = SQLASTParser.analyze_sql(request.sql)
    policy_res = PolicyEngine.validate_sql(
        db=db,
        role_id=request.role_id,
        data_source_id=request.data_source_id,
        sql=request.sql,
    )
    return SQLValidateResponse(
        sql=request.sql,
        policy_validation=policy_res,
        analysis=analysis.model_dump(),
    )
