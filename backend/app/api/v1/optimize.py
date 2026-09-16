from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import Engine

from app.db.session import get_db, get_business_db, business_engine
from app.models.trust import OptimizationSuggestion
from app.models.auth import User
from app.models.session import QueryHistory
from app.schemas.optimize import (
    OptimizeExplainRequest,
    OptimizeAnalyzeRequest,
    OptimizeResponse,
    OptimizationItem,
)
from app.services.auth_service import get_current_user, require_roles, authorize_resource_access
from app.services.policy_engine import PolicyEngine
from app.services.sql_parser import SQLASTParser
from app.services.optimizer import QueryOptimizerService

router = APIRouter(prefix="", tags=["Optimization"])


@router.post(
    "/explain",
    response_model=OptimizeResponse,
    summary="Generate Evidence-Based Optimization Suggestions via Safe EXPLAIN (REQ-OPT-01)",
)
def optimize_explain(
    request: OptimizeExplainRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes a plan-only EXPLAIN (safe, does not execute query).
    Strictly validated by Policy Engine before EXPLAIN execution (SEC-OPT-POLICY).
    Identifies unindexed filters, expensive joins, and unindexed sort operations.
    Returns structured evidence and confidence ratings (Low / Medium / High).
    """
    # 1. Deterministic Policy Gate check before EXPLAIN
    user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"
    if user_role_name != "admin":
        policy_res = PolicyEngine.validate_sql(
            db=db,
            sql=request.sql,
            role_id=current_user.role_id or 3,
            data_source_id=1,
        )
        if not policy_res.is_allowed:
            violation_msg = "; ".join(v.message for v in policy_res.violations) if policy_res.violations else "Policy rule violation"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Policy violation in optimization candidate SQL: {violation_msg}",
            )

    try:
        plan_raw, plan_summary = QueryOptimizerService.run_explain(business_engine, request.sql)
        suggestions = QueryOptimizerService.generate_suggestions(
            business_engine,
            request.sql,
            plan_raw,
            plan_summary,
            is_analyze=False,
        )

        now_str = datetime.now(timezone.utc).isoformat()

        # Save to DB if query_id provided
        if request.query_id:
            try:
                for s in suggestions:
                    opt_row = OptimizationSuggestion(
                        query_id=request.query_id,
                        mode="explain",
                        issue_type=s.issue_type,
                        detail=s.detail,
                        evidence_json=s.evidence_json,
                        confidence=s.confidence,
                        suggested_ddl=s.suggested_ddl,
                    )
                    db.add(opt_row)
                db.commit()
            except Exception:
                db.rollback()

        return OptimizeResponse(
            mode="explain",
            plan_raw=plan_raw,
            plan_summary=plan_summary,
            suggestions=suggestions,
            execution_stats=None,
            query_id=request.query_id,
            created_at=now_str,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization explain failed: {str(e)}",
        )


@router.post(
    "/analyze",
    response_model=OptimizeResponse,
    summary="Admin-Gated EXPLAIN ANALYZE Mode (REQ-OPT-02)",
)
def optimize_analyze(
    request: OptimizeAnalyzeRequest,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Opt-in EXPLAIN ANALYZE execution. Strictly gated to admin role on the server side (REQ-OPT-02 / Rule R0).
    Runs inside read-only execution sandbox with query timeout, row limit, and AST policy validation.
    """
    # 1. Full Deterministic Policy Engine AST Validation Gate
    analysis = SQLASTParser.analyze_sql(request.sql)
    if not analysis.is_valid_syntax:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SQL Syntax Error: {analysis.syntax_error}",
        )
    if not analysis.is_select_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=analysis.syntax_error or "Only SELECT queries are permitted in EXPLAIN ANALYZE (Rule R1.1).",
        )
    if analysis.disallowed_functions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Disallowed functions blocked: {', '.join(analysis.disallowed_functions)}",
        )

    user_role_name = current_user.role.role_name.lower() if current_user.role else "viewer"
    injected_sql = None
    if user_role_name != "admin":
        policy_res = PolicyEngine.validate_sql(
            db=db,
            sql=request.sql,
            role_id=current_user.role_id or 1,
            data_source_id=1,
        )
        if not policy_res.is_allowed:
            violation_msg = "; ".join(v.message for v in policy_res.violations) if policy_res.violations else "Policy rule violation"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Policy violation in EXPLAIN ANALYZE candidate SQL: {violation_msg}",
            )
        injected_sql = policy_res.injected_sql

    try:
        exec_sql = injected_sql or request.sql
        plan_raw, plan_summary, exec_stats = QueryOptimizerService.run_explain_analyze(
            business_engine,
            exec_sql,
            role="admin",
            timeout_seconds=10.0,
        )

        suggestions = QueryOptimizerService.generate_suggestions(
            business_engine,
            request.sql,
            plan_raw,
            plan_summary,
            is_analyze=True,
            exec_stats=exec_stats,
        )

        now_str = datetime.now(timezone.utc).isoformat()

        # Save to DB if query_id provided
        if request.query_id:
            try:
                for s in suggestions:
                    opt_row = OptimizationSuggestion(
                        query_id=request.query_id,
                        mode="explain_analyze",
                        issue_type=s.issue_type,
                        detail=s.detail,
                        evidence_json=s.evidence_json,
                        confidence=s.confidence,
                        suggested_ddl=s.suggested_ddl,
                    )
                    db.add(opt_row)
                db.commit()
            except Exception:
                db.rollback()

        return OptimizeResponse(
            mode="explain_analyze",
            plan_raw=plan_raw,
            plan_summary=plan_summary,
            suggestions=suggestions,
            execution_stats=exec_stats,
            query_id=request.query_id,
            created_at=now_str,
        )
    except PermissionError as pe:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(pe),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization analyze failed: {str(e)}",
        )


@router.get(
    "/{query_id}",
    summary="Get Stored Optimization Suggestions for a Query",
)
def get_query_optimizations(
    query_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves stored optimization suggestions for a given query history record.
    Enforces resource ownership access control.
    """
    query_record = db.query(QueryHistory).filter(QueryHistory.query_id == query_id).first()
    if query_record:
        authorize_resource_access(query_record.user_id, current_user, "optimization record", "view")

    records = db.query(OptimizationSuggestion).filter(OptimizationSuggestion.query_id == query_id).all()
    return {
        "success": True,
        "query_id": query_id,
        "suggestions": [
            {
                "suggestion_id": r.suggestion_id,
                "mode": r.mode,
                "issue_type": r.issue_type,
                "detail": r.detail,
                "evidence_json": r.evidence_json,
                "confidence": r.confidence,
                "suggested_ddl": r.suggested_ddl,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }

