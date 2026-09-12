from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db, business_engine
from app.schemas.query import (
    SQLGenerateRequest,
    SQLGenerateResponse,
    SQLValidateRequest,
    SQLValidateResponse,
    SQLExecuteRequest,
    SQLExecuteResponse,
)
from app.services.sql_generator import SQLGeneratorService
from app.services.policy_engine import PolicyEngine
from app.services.sql_parser import SQLASTParser
from app.services.execution_sandbox import ExecutionSandboxService

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


@router.post("/execute", response_model=SQLExecuteResponse)
async def execute_sandboxed_sql(
    request: SQLExecuteRequest,
    db: Session = Depends(get_db),
):
    """
    Executes a SQL query within the read-only execution sandbox with timeout and row cap,
    ONLY IF it passes all deterministic Policy Engine gates (Rule R1.1-R1.6).
    """
    policy_res = PolicyEngine.validate_sql(
        db=db,
        role_id=request.role_id,
        data_source_id=request.data_source_id,
        sql=request.sql,
    )

    if not policy_res.is_allowed:
        return SQLExecuteResponse(
            success=False,
            sql=request.sql,
            injected_sql=None,
            columns=[],
            rows=[],
            row_count=0,
            latency_ms=0,
            truncated=False,
            policy_validation=policy_res,
            error=f"Query rejected by Policy Engine: {'; '.join([v.message for v in policy_res.violations])}",
        )

    # Use injected SQL (with active row filters) for execution
    execution_sql = policy_res.injected_sql or request.sql

    sandbox_res = ExecutionSandboxService.execute_query(
        engine=business_engine,
        sql=execution_sql,
        timeout_seconds=request.timeout_seconds,
        max_rows=request.max_rows,
    )

    return SQLExecuteResponse(
        success=sandbox_res.success,
        sql=request.sql,
        injected_sql=execution_sql,
        columns=sandbox_res.columns,
        rows=sandbox_res.rows,
        row_count=sandbox_res.row_count,
        latency_ms=sandbox_res.latency_ms,
        truncated=sandbox_res.truncated,
        policy_validation=policy_res,
        error=sandbox_res.error,
    )
