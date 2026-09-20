from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.session import QueryHistory, SessionModel
from app.models.auth import User
from app.models.trust import SqlCriticFinding, ResultValidation
from app.schemas.history import (
    QueryHistorySummary,
    QueryHistoryDetail,
    QueryHistoryListResponse,
    QueryRerunRequest,
)
from app.schemas.query import SQLExecuteResponse
from app.schemas.common import StandardResponse
from app.services.auth_service import get_current_user, get_effective_role_id, authorize_query_access
from app.services.data_source_manager import DataSourceManager, DataSourceUnavailableError
from app.services.policy_engine import PolicyEngine
from app.services.execution_sandbox import ExecutionSandboxService
from app.services.sql_critic import SQLCriticService
from app.services.result_validator import ResultValidatorService
from app.services.reliability_scorer import ReliabilityScorerService
from app.services.chart_engine import ChartEngineService

router = APIRouter(prefix="/history", tags=["Query History Engine"])


@router.get("", response_model=StandardResponse[QueryHistoryListResponse])
def list_query_history(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by execution status"),
    search: Optional[str] = Query(None, description="Search in question or SQL"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves a paginated list of past queries with execution status and reliability scores (REQ-HIST-01).
    Scoped to current_user unless requester is Admin.
    """
    query = db.query(QueryHistory)
    user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"

    if user_role_name == "admin" and user_id is not None:
        query = query.filter(QueryHistory.user_id == user_id)
    elif user_role_name != "admin":
        query = query.filter(QueryHistory.user_id == current_user.user_id)

    if session_id:
        query = query.filter(QueryHistory.session_id == session_id)
    if status_filter:
        query = query.filter(QueryHistory.status == status_filter)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (QueryHistory.nl_question.ilike(search_fmt)) | (QueryHistory.final_sql.ilike(search_fmt))
        )

    total = query.count()
    offset = (page - 1) * page_size
    items_db = query.order_by(desc(QueryHistory.created_at)).offset(offset).limit(page_size).all()

    items = []
    for item in items_db:
        rel_score = None
        if item.reliability_breakdown and isinstance(item.reliability_breakdown, dict):
            rel_score = item.reliability_breakdown.get("composite")

        items.append(
            QueryHistorySummary(
                query_id=item.query_id,
                session_id=item.session_id,
                user_id=item.user_id,
                nl_question=item.nl_question,
                classification=item.classification,
                status=item.status,
                execution_ms=item.execution_ms,
                row_count=item.row_count,
                chart_type=item.chart_type,
                final_sql=item.final_sql,
                reliability_score=rel_score,
                created_at=item.created_at,
            )
        )

    return StandardResponse(
        success=True,
        message="Query history retrieved",
        data=QueryHistoryListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        ),
    )


@router.get("/{query_id}", response_model=StandardResponse[QueryHistoryDetail])
def get_query_history_detail(
    query_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full execution audit details for a specific query run with strict IDOR ownership authorization.
    """
    item = authorize_query_access(db, current_user, query_id, action="view")

    critic_findings = (
        db.query(SqlCriticFinding).filter(SqlCriticFinding.query_id == query_id).all()
    )
    validations = (
        db.query(ResultValidation).filter(ResultValidation.query_id == query_id).all()
    )

    detail = QueryHistoryDetail(
        query_id=item.query_id,
        session_id=item.session_id,
        user_id=item.user_id,
        nl_question=item.nl_question,
        classification=item.classification,
        initial_sql=item.initial_sql,
        final_sql=item.final_sql,
        status=item.status,
        execution_ms=item.execution_ms,
        row_count=item.row_count,
        chart_type=item.chart_type,
        schema_snapshot_id=item.schema_snapshot_id,
        result_hash=item.result_hash,
        prompt_version=item.prompt_version,
        model_name=item.model_name,
        model_params=item.model_params,
        reliability_breakdown=item.reliability_breakdown,
        critic_findings=[
            {
                "finding_id": f.finding_id,
                "smell_type": f.smell_type,
                "severity": f.severity,
                "description": f.description,
                "suggestion": f.suggestion,
            }
            for f in critic_findings
        ],
        validations=[
            {
                "validation_id": v.validation_id,
                "check_type": v.check_type,
                "expected_range": v.expected_range,
                "observed_value": v.observed_value,
                "severity": v.severity,
            }
            for v in validations
        ],
        created_at=item.created_at,
    )

    return StandardResponse(
        success=True,
        message="Query details retrieved",
        data=detail,
    )


@router.post("/{query_id}/rerun", response_model=StandardResponse[SQLExecuteResponse])
def rerun_historical_query(
    query_id: str,
    rerun_req: QueryRerunRequest = QueryRerunRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reruns a historical query LIVE against current database and policies (REQ-HIST-01).
    Enforces 'Rerun-by-Default' principle: never returns stale cached results.
    Strictly enforces query ownership and derives authorization role from current_user.
    """
    item = authorize_query_access(db, current_user, query_id, action="rerun")

    sql_to_run = item.final_sql or item.initial_sql
    if not sql_to_run:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Historical record does not contain executable SQL",
        )

    # Determine effective role_id strictly on server side
    effective_role_id = get_effective_role_id(current_user, rerun_req.role_id)

    # Validate against Policy Engine
    policy_res = PolicyEngine.validate_sql(
        db=db,
        role_id=effective_role_id,
        data_source_id=rerun_req.data_source_id,
        sql=sql_to_run,
    )

    if not policy_res.is_allowed:
        rel_score = ReliabilityScorerService.compute_reliability_score(
            db=db,
            sql=sql_to_run,
            role_id=effective_role_id,
            data_source_id=rerun_req.data_source_id,
            policy_validation=policy_res,
            execution_success=False,
            row_count=0,
            latency_ms=0,
        )
        return StandardResponse(
            success=False,
            message="Query rejected by current Policy Engine rules",
            data=SQLExecuteResponse(
                success=False,
                sql=sql_to_run,
                injected_sql=None,
                columns=[],
                rows=[],
                row_count=0,
                latency_ms=0,
                truncated=False,
                policy_validation=policy_res,
                error=f"Live rerun rejected: {'; '.join([v.message for v in policy_res.violations])}",
                reliability_breakdown=rel_score,
            ),
        )

    exec_sql = policy_res.injected_sql or sql_to_run
    critic_res = SQLCriticService.critique_sql(
        db=db,
        data_source_id=rerun_req.data_source_id,
        sql=exec_sql,
    )

    # Resolve target engine dynamically via DataSourceManager
    try:
        exec_engine = DataSourceManager.get_engine(db, data_source_id=rerun_req.data_source_id)
    except DataSourceUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    # Execute sandbox
    sandbox_res = ExecutionSandboxService.execute_query(
        engine=exec_engine,
        sql=exec_sql,
        timeout_seconds=rerun_req.timeout_seconds,
        max_rows=rerun_req.max_rows,
    )

    if sandbox_res.success:
        validation_report = ResultValidatorService.validate_results(
            db=db,
            sql=exec_sql,
            columns=sandbox_res.columns,
            rows=sandbox_res.rows,
            row_count=sandbox_res.row_count,
            query_id=query_id,
        )
        reliability = ReliabilityScorerService.compute_reliability_score(
            db=db,
            sql=exec_sql,
            role_id=effective_role_id,
            data_source_id=rerun_req.data_source_id,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            result_validation=validation_report,
            row_count=sandbox_res.row_count,
            latency_ms=sandbox_res.latency_ms,
            execution_success=True,
        )
        chart_spec = ChartEngineService.infer_chart_spec(
            columns=sandbox_res.columns,
            rows=sandbox_res.rows,
            question=item.nl_question,
        )

        return StandardResponse(
            success=True,
            message="Query rerun live successfully (fresh execution)",
            data=SQLExecuteResponse(
                success=True,
                sql=sql_to_run,
                injected_sql=exec_sql,
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
            ),
        )

    reliability = ReliabilityScorerService.compute_reliability_score(
        db=db,
        sql=exec_sql,
        role_id=effective_role_id,
        data_source_id=rerun_req.data_source_id,
        policy_validation=policy_res,
        critic_analysis=critic_res,
        row_count=0,
        latency_ms=sandbox_res.latency_ms,
        execution_success=False,
    )

    return StandardResponse(
        success=False,
        message="Live execution failed",
        data=SQLExecuteResponse(
            success=False,
            sql=sql_to_run,
            injected_sql=exec_sql,
            columns=[],
            rows=[],
            row_count=0,
            latency_ms=sandbox_res.latency_ms,
            truncated=False,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            error=sandbox_res.error,
            reliability_breakdown=reliability,
        ),
    )


@router.delete("/{query_id}", response_model=StandardResponse[dict])
def delete_query_history(
    query_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes a query history entry strictly verified against caller ownership.
    """
    item = authorize_query_access(db, current_user, query_id, action="delete")

    db.delete(item)
    db.commit()

    return StandardResponse(
        success=True,
        message=f"Query history record {query_id} deleted successfully",
        data={"deleted_query_id": query_id},
    )

