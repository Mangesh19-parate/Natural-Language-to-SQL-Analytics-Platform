from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db, business_engine
from app.models.session import QueryHistory
from app.models.auth import User
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
from app.services.auth_service import get_current_user, get_effective_role_id
from app.services.sql_generator import SQLGeneratorService
from app.services.policy_engine import PolicyEngine
from app.services.sql_parser import SQLASTParser
from app.services.execution_sandbox import ExecutionSandboxService
from app.services.sql_critic import SQLCriticService
from app.services.self_correction import SelfCorrectionService
from app.services.result_validator import ResultValidatorService
from app.services.reliability_scorer import ReliabilityScorerService
from app.services.chart_engine import ChartEngineService
from app.services.join_optimizer import CostBasedJoinOptimizer
from app.schemas.optimize import GateDecisionEnum

router = APIRouter(prefix="/sql", tags=["SQL Generation & Policy Engine"])


@router.post("/generate", response_model=SQLGenerateResponse)
async def generate_sql_proposal(
    request: SQLGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a SQL query proposal via LLM provider using the authenticated user's Semantic Catalog,
    and subjects it to deterministic AST & Policy Engine validation (Principle R0)
    and SQL Critic semantic-smell analysis (Rule R3.1).
    """
    effective_role_id = get_effective_role_id(current_user, request.role_id)
    generator = SQLGeneratorService()
    response = await generator.generate_sql_proposal(
        db=db,
        question=request.question,
        role_id=effective_role_id,
        data_source_id=request.data_source_id,
        clarifications=request.clarifications,
    )
    return response


@router.post("/validate", response_model=SQLValidateResponse)
def validate_sql(
    request: SQLValidateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Performs deterministic AST and Policy Engine authorization checks on any SQL statement,
    including SQL Critic smell analysis, strictly enforcing server-side role.
    """
    effective_role_id = get_effective_role_id(current_user, request.role_id)
    analysis = SQLASTParser.analyze_sql(request.sql)
    policy_res = PolicyEngine.validate_sql(
        db=db,
        role_id=effective_role_id,
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
def critique_sql_endpoint(
    request: SQLCriticRequest,
    current_user: User = Depends(get_current_user),
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
def self_correct_sql(
    request: SelfCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes the E1–E7 self-correction retry loop (max 3) against DB execution errors.
    Enforces Rule R4.2: E5 authorization rejections are never retried.
    """
    effective_role_id = get_effective_role_id(current_user, request.role_id)
    correction_result = SelfCorrectionService.attempt_correction(
        db=db,
        original_question=request.original_question,
        failing_sql=request.failing_sql,
        error_message=request.error_message,
        data_source_id=request.data_source_id,
        role_id=effective_role_id,
        max_retries=request.max_retries,
    )
    return correction_result


@router.post("/validate-results", response_model=ResultValidationReport)
def validate_query_results(
    request: ResultValidationRequest,
    current_user: User = Depends(get_current_user),
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


def _persist_query_reliability(
    db: Session,
    query_id: Optional[str],
    reliability_dict: Dict[str, Any],
    final_sql: str,
    status_str: str,
    row_count: int,
    latency_ms: int,
    chart_type: Optional[str] = None,
    result_hash: Optional[str] = None,
    data_source_id: int = 1,
    user_id: Optional[int] = None,
):
    if not query_id:
        return
    try:
        q_row = db.query(QueryHistory).filter(QueryHistory.query_id == query_id).first()
        if q_row:
            q_row.reliability_breakdown = reliability_dict
            q_row.final_sql = final_sql
            q_row.status = status_str
            q_row.row_count = row_count
            q_row.execution_ms = latency_ms
            if user_id is not None:
                q_row.user_id = user_id
            if chart_type:
                q_row.chart_type = chart_type
            if result_hash:
                q_row.result_hash = result_hash
            if not q_row.prompt_version:
                q_row.prompt_version = "v1.4"
            if not q_row.model_name:
                q_row.model_name = "gpt-4o-mini"
            if not q_row.model_params:
                q_row.model_params = {"temperature": 0.0, "max_tokens": 512}
            if not q_row.schema_snapshot_id:
                from app.services.query_replay import QueryReplayService
                snapshot = QueryReplayService.capture_current_schema_snapshot(db, data_source_id)
                q_row.schema_snapshot_id = snapshot.schema_snapshot_id
            db.commit()
    except Exception:
        db.rollback()


@router.post("/execute", response_model=SQLExecuteResponse)
def execute_sandboxed_sql(
    request: SQLExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes a SQL query within the read-only execution sandbox with timeout and row cap,
    ONLY IF it passes all deterministic Policy Engine gates (Rule R1.1-R1.6),
    with post-execution Result Validation (REQ-RESULT-01), optional Self-Correction,
    deterministic Reliability Scoring (REQ-TRUST-01 / Rule R3.3), and Chart Spec generation (REQ-VIS-01).
    Strictly derives effective role from authenticated session.
    """
    effective_role_id = get_effective_role_id(current_user, request.role_id)

    policy_res = PolicyEngine.validate_sql(
        db=db,
        role_id=effective_role_id,
        data_source_id=request.data_source_id,
        sql=request.sql,
    )

    if not policy_res.is_allowed:
        error_type = SelfCorrectionService.classify_error(
            "; ".join([v.message for v in policy_res.violations]),
            is_policy_rejection=True,
        )
        reliability = ReliabilityScorerService.compute_reliability_score(
            db=db,
            sql=request.sql,
            role_id=effective_role_id,
            data_source_id=request.data_source_id,
            policy_validation=policy_res,
            execution_success=False,
            row_count=0,
            latency_ms=0,
        )
        _persist_query_reliability(
            db, request.query_id, reliability.model_dump(), request.sql, "rejected_policy", 0, 0, user_id=current_user.user_id
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
            reliability_breakdown=reliability,
        )

    # Use injected SQL (with active row filters) for execution
    execution_sql = policy_res.injected_sql or request.sql

    critic_res = SQLCriticService.critique_sql(
        db=db,
        data_source_id=request.data_source_id,
        sql=execution_sql,
    )

    # Pre-execution Cost-Based Join Planning & Admission Gating (Principle R2)
    opt_res = CostBasedJoinOptimizer.optimize_query(
        sql=execution_sql,
        engine=business_engine,
        data_source_id=request.data_source_id,
    )

    # Gate Decision Check (Block runaway Cartesian / excess cost)
    if opt_res.gate_decision in [GateDecisionEnum.BLOCK_RUNAWAY_CARTESIAN, GateDecisionEnum.BLOCK_EXPENSIVE]:
        error_type = ErrorTaxonomyType.E4_SEMANTIC
        reliability = ReliabilityScorerService.compute_reliability_score(
            db=db,
            sql=execution_sql,
            role_id=effective_role_id,
            data_source_id=request.data_source_id,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            execution_success=False,
            row_count=0,
            latency_ms=0,
        )
        _persist_query_reliability(
            db, request.query_id, reliability.model_dump(), execution_sql, "rejected_optimizer", 0, 0, user_id=current_user.user_id
        )
        return SQLExecuteResponse(
            success=False,
            sql=request.sql,
            injected_sql=execution_sql,
            columns=[],
            rows=[],
            row_count=0,
            latency_ms=0,
            truncated=False,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            error=f"Query rejected by Optimizer Admission Gate: {opt_res.gate_reason}",
            error_type=error_type,
            reliability_breakdown=reliability,
            optimization_plan=opt_res,
        )

    # Execute optimized SQL if safe rewrite was generated, else fallback to execution_sql
    final_execution_sql = opt_res.optimized_sql if (opt_res.optimized_sql and opt_res.gate_decision == GateDecisionEnum.ALLOW) else execution_sql

    sandbox_res = ExecutionSandboxService.execute_query(
        engine=business_engine,
        sql=final_execution_sql,
        timeout_seconds=request.timeout_seconds,
        max_rows=request.max_rows,
    )

    # If execution succeeded, perform Result Validation (REQ-RESULT-01) and Chart Generation (REQ-VIS-01)
    if sandbox_res.success:
        validation_report = ResultValidatorService.validate_results(
            db=db,
            sql=final_execution_sql,
            columns=sandbox_res.columns,
            rows=sandbox_res.rows,
            row_count=sandbox_res.row_count,
            query_id=request.query_id,
        )
        reliability = ReliabilityScorerService.compute_reliability_score(
            db=db,
            sql=final_execution_sql,
            role_id=effective_role_id,
            data_source_id=request.data_source_id,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            result_validation=validation_report,
            row_count=sandbox_res.row_count,
            latency_ms=sandbox_res.latency_ms,
            execution_success=True,
        )
        from app.services.query_replay import QueryReplayService
        res_hash = QueryReplayService.compute_result_hash(sandbox_res.columns, sandbox_res.rows)
        chart_spec = ChartEngineService.infer_chart_spec(
            columns=sandbox_res.columns,
            rows=sandbox_res.rows,
            question=request.question,
        )
        _persist_query_reliability(
            db, request.query_id, reliability.model_dump(), final_execution_sql, "success", sandbox_res.row_count, sandbox_res.latency_ms, chart_spec.chart_type.value, result_hash=res_hash, data_source_id=request.data_source_id, user_id=current_user.user_id
        )
        return SQLExecuteResponse(
            success=True,
            sql=request.sql,
            injected_sql=final_execution_sql,
            columns=sandbox_res.columns,
            rows=sandbox_res.rows,
            row_count=sandbox_res.row_count,
            latency_ms=sandbox_res.latency_ms,
            truncated=sandbox_res.truncated,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            result_validation=validation_report,
            reliability_breakdown=reliability,
            chart_spec=chart_spec,
            optimization_plan=opt_res,
        )

    # If execution failed, classify error
    err_type = SelfCorrectionService.classify_error(sandbox_res.error or "")
    correction_res = None

    if request.auto_correct and request.question and err_type != ErrorTaxonomyType.E5_AUTHORIZATION:
        correction_res = SelfCorrectionService.attempt_correction(
            db=db,
            original_question=request.question,
            failing_sql=final_execution_sql,
            error_message=sandbox_res.error or "Execution error",
            data_source_id=request.data_source_id,
            role_id=effective_role_id,
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
                reliability = ReliabilityScorerService.compute_reliability_score(
                    db=db,
                    sql=correction_res.final_sql,
                    role_id=effective_role_id,
                    data_source_id=request.data_source_id,
                    policy_validation=policy_res,
                    critic_analysis=critic_res,
                    correction_result=correction_res,
                    result_validation=val_rep,
                    row_count=repaired_exec.row_count,
                    latency_ms=repaired_exec.latency_ms,
                    execution_success=True,
                )
                repaired_chart_spec = ChartEngineService.infer_chart_spec(
                    columns=repaired_exec.columns,
                    rows=repaired_exec.rows,
                    question=request.question,
                )
                _persist_query_reliability(
                    db, request.query_id, reliability.model_dump(), correction_res.final_sql, "auto_corrected", repaired_exec.row_count, repaired_exec.latency_ms, repaired_chart_spec.chart_type.value, user_id=current_user.user_id
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
                    reliability_breakdown=reliability,
                    chart_spec=repaired_chart_spec,
                    optimization_plan=opt_res,
                )

    reliability = ReliabilityScorerService.compute_reliability_score(
        db=db,
        sql=final_execution_sql,
        role_id=effective_role_id,
        data_source_id=request.data_source_id,
        policy_validation=policy_res,
        critic_analysis=critic_res,
        correction_result=correction_res,
        row_count=0,
        latency_ms=sandbox_res.latency_ms,
        execution_success=False,
    )
    _persist_query_reliability(
        db, request.query_id, reliability.model_dump(), final_execution_sql, "failed", 0, sandbox_res.latency_ms, user_id=current_user.user_id
    )
    return SQLExecuteResponse(
        success=False,
        sql=request.sql,
        injected_sql=final_execution_sql,
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
        reliability_breakdown=reliability,
        optimization_plan=opt_res,
    )



