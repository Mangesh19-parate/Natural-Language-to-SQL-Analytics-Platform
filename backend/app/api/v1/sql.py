from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db, business_engine
from app.schemas.query import (
    SQLGenerateRequest,
    SQLGenerateResponse,
    SQLValidateRequest,
    SQLValidateResponse,
    SQLCriticRequest,
    SQLCriticResponse,
    SQLExecuteRequest,
    SQLExecuteResponse,
    SelfCorrectionRequest,
    SelfCorrectionResult,
    ResultValidationRequest,
    ResultValidationReport,
    ErrorTaxonomyType,
)
from app.services.sql_generator import SQLGeneratorService
from app.services.policy_engine import PolicyEngine
from app.services.sql_parser import SQLASTParser
from app.services.execution_sandbox import ExecutionSandboxService
from app.services.sql_critic import SQLCriticService
from app.services.self_correction import SelfCorrectionService
from app.services.result_validator import ResultValidatorService

router = APIRouter(prefix="/sql", tags=["SQL Generation & Policy Engine"])


@router.post("/generate", response_model=SQLGenerateResponse)
async def generate_sql_proposal(
    request: SQLGenerateRequest,
    db: Session = Depends(get_db),
):
    """
    Generates a SQL query proposal via LLM provider using the role's Semantic Catalog,
    and subjects it to deterministic AST & Policy Engine validation (Principle R0)
    and SQL Critic semantic-smell analysis (Rule R3.1).
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
    Performs deterministic AST and Policy Engine authorization checks on any SQL statement,
    including SQL Critic smell analysis.
    """
    analysis = SQLASTParser.analyze_sql(request.sql)
    policy_res = PolicyEngine.validate_sql(
        db=db,
        role_id=request.role_id,
        data_source_id=request.data_source_id,
        sql=request.sql,
    )
    critic_res = None
    if policy_res.is_allowed:
        critic_res = SQLCriticService.critique_sql(
            db=db,
            data_source_id=request.data_source_id,
            sql=policy_res.injected_sql or request.sql,
        )

    return SQLValidateResponse(
        sql=request.sql,
        policy_validation=policy_res,
        critic_analysis=critic_res,
        analysis=analysis.model_dump(),
    )


@router.post("/critic", response_model=SQLCriticResponse)
async def critique_sql_endpoint(
    request: SQLCriticRequest,
    db: Session = Depends(get_db),
):
    """
    Evaluates semantic smells in an ad-hoc SQL query using the Semantic Catalog metadata.
    """
    critic_res = SQLCriticService.critique_sql(
        db=db,
        data_source_id=request.data_source_id,
        sql=request.sql,
    )

    if request.query_id and critic_res.findings:
        SQLCriticService.persist_findings(
            db=db,
            query_id=request.query_id,
            findings=critic_res.findings,
        )

    return SQLCriticResponse(
        sql=request.sql,
        critic_analysis=critic_res,
    )


@router.post("/correct", response_model=SelfCorrectionResult)
async def self_correct_sql(
    request: SelfCorrectionRequest,
    db: Session = Depends(get_db),
):
    """
    Executes the E1–E7 self-correction retry loop (max 3) against DB execution errors.
    Enforces Rule R4.2: E5 authorization rejections are never retried.
    """
    correction_result = SelfCorrectionService.attempt_correction(
        db=db,
        original_question=request.original_question,
        failing_sql=request.failing_sql,
        error_message=request.error_message,
        data_source_id=request.data_source_id,
        role_id=request.role_id,
        max_retries=request.max_retries,
    )
    return correction_result


@router.post("/validate-results", response_model=ResultValidationReport)
async def validate_query_results(
    request: ResultValidationRequest,
    db: Session = Depends(get_db),
):
    """
    Runs Result Sanity Validator (zero-row, cardinality, null-explosion, join-multiplication).
    """
    report = ResultValidatorService.validate_results(
        db=db,
        sql=request.sql,
        columns=request.columns,
        rows=request.rows,
        row_count=request.row_count,
        query_id=request.query_id,
    )
    return report


@router.post("/execute", response_model=SQLExecuteResponse)
async def execute_sandboxed_sql(
    request: SQLExecuteRequest,
    db: Session = Depends(get_db),
):
    """
    Executes a SQL query within the read-only execution sandbox with timeout and row cap,
    ONLY IF it passes all deterministic Policy Engine gates (Rule R1.1-R1.6),
    with post-execution Result Validation (REQ-RESULT-01) and optional Self-Correction.
    """
    policy_res = PolicyEngine.validate_sql(
        db=db,
        role_id=request.role_id,
        data_source_id=request.data_source_id,
        sql=request.sql,
    )

    if not policy_res.is_allowed:
        error_type = SelfCorrectionService.classify_error(
            "; ".join([v.message for v in policy_res.violations]),
            is_policy_rejection=True,
        )
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
            error_type=error_type,
        )

    # Use injected SQL (with active row filters) for execution
    execution_sql = policy_res.injected_sql or request.sql

    critic_res = SQLCriticService.critique_sql(
        db=db,
        data_source_id=request.data_source_id,
        sql=execution_sql,
    )

    sandbox_res = ExecutionSandboxService.execute_query(
        engine=business_engine,
        sql=execution_sql,
        timeout_seconds=request.timeout_seconds,
        max_rows=request.max_rows,
    )

    # If execution succeeded, perform Result Validation (REQ-RESULT-01)
    if sandbox_res.success:
        validation_report = ResultValidatorService.validate_results(
            db=db,
            sql=execution_sql,
            columns=sandbox_res.columns,
            rows=sandbox_res.rows,
            row_count=sandbox_res.row_count,
            query_id=request.query_id,
        )
        return SQLExecuteResponse(
            success=True,
            sql=request.sql,
            injected_sql=execution_sql,
            columns=sandbox_res.columns,
            rows=sandbox_res.rows,
            row_count=sandbox_res.row_count,
            latency_ms=sandbox_res.latency_ms,
            truncated=sandbox_res.truncated,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            result_validation=validation_report,
        )

    # If execution failed, classify error
    err_type = SelfCorrectionService.classify_error(sandbox_res.error or "")
    correction_res = None

    if request.auto_correct and request.question and err_type != ErrorTaxonomyType.E5_AUTHORIZATION:
        correction_res = SelfCorrectionService.attempt_correction(
            db=db,
            original_question=request.question,
            failing_sql=execution_sql,
            error_message=sandbox_res.error or "Execution error",
            data_source_id=request.data_source_id,
            role_id=request.role_id,
            max_retries=3,
        )
        if correction_res.recovered:
            # Re-execute repaired SQL
            repaired_exec = ExecutionSandboxService.execute_query(
                engine=business_engine,
                sql=correction_res.final_sql,
                timeout_seconds=request.timeout_seconds,
                max_rows=request.max_rows,
            )
            if repaired_exec.success:
                val_rep = ResultValidatorService.validate_results(
                    db=db,
                    sql=correction_res.final_sql,
                    columns=repaired_exec.columns,
                    rows=repaired_exec.rows,
                    row_count=repaired_exec.row_count,
                    query_id=request.query_id,
                )
                return SQLExecuteResponse(
                    success=True,
                    sql=request.sql,
                    injected_sql=correction_res.final_sql,
                    columns=repaired_exec.columns,
                    rows=repaired_exec.rows,
                    row_count=repaired_exec.row_count,
                    latency_ms=repaired_exec.latency_ms,
                    truncated=repaired_exec.truncated,
                    policy_validation=policy_res,
                    critic_analysis=critic_res,
                    correction_result=correction_res,
                    result_validation=val_rep,
                )

    return SQLExecuteResponse(
        success=False,
        sql=request.sql,
        injected_sql=execution_sql,
        columns=[],
        rows=[],
        row_count=0,
        latency_ms=sandbox_res.latency_ms,
        truncated=False,
        policy_validation=policy_res,
        critic_analysis=critic_res,
        error=sandbox_res.error,
        error_type=err_type,
        correction_result=correction_res,
    )

