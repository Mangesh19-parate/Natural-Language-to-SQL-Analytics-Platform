from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.models.auth import User
from app.schemas.lab import (
    SecurityAttackRunRequest,
    SecurityAttackRunResponse,
    EvaluationBenchmarkRequest,
    EvaluationBenchmarkResponse,
    EvaluationJobAcceptedResponse,
    EvaluationJobStatusResponse,
)
from app.services.auth_service import get_current_user, require_roles
from app.services.security_attack_lab import SecurityAttackLabService
from app.services.evaluation_lab import EvaluationLabService

router = APIRouter(prefix="/lab", tags=["Security & Evaluation Labs"])


@router.post("/security/run", response_model=SecurityAttackRunResponse)
def run_security_attack_suite(
    request: SecurityAttackRunRequest,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Executes the standing 128-case adversarial suite (structural, UNION, unauth table/col,
    aggregate bypass, dangerous functions, Cartesian product, prompt injections) (REQ-SECLAB-01).
    Enforces Hard Gate: 100% blocked, 0.00% safety violation rate.
    Strictly restricted to Admin role to prevent denial-of-service abuse.
    """
    response = SecurityAttackLabService.execute_attack_suite(
        db=db,
        data_source_id=request.data_source_id,
        custom_attacks=request.custom_attacks,
    )
    return response


@router.get("/security/latest", response_model=SecurityAttackRunResponse)
def get_latest_security_attack_run(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the latest standing Security Attack Lab run from database without re-executing.
    Requires authenticated user access.
    """
    response = SecurityAttackLabService.get_latest_attack_run(db=db)
    return response


@router.post(
    "/evaluation/jobs",
    response_model=EvaluationJobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue Async Benchmark Evaluation Job (ADR 006)",
)
def enqueue_evaluation_job(
    request: EvaluationBenchmarkRequest,
    current_user: User = Depends(require_roles(["admin"])),
):
    """
    Submits a benchmark evaluation job to the asynchronous background worker queue (ADR 006).
    Returns HTTP 202 Accepted with a trackable job_id and status polling URL.
    """
    def _get_db_session():
        from app.main import app as fastapi_app
        override = fastapi_app.dependency_overrides.get(get_db)
        if override:
            return override()
        return SessionLocal()

    job_id = EvaluationLabService.submit_benchmark_job(
        db_factory=_get_db_session,
        request=request,
        created_by_user_id=current_user.user_id,
    )
    return EvaluationJobAcceptedResponse(
        job_id=job_id,
        status="pending",
        message="Evaluation benchmark job enqueued successfully.",
        status_url=f"/api/lab/evaluation/jobs/{job_id}",
    )


@router.get(
    "/evaluation/jobs/{job_id}",
    response_model=EvaluationJobStatusResponse,
    summary="Poll Async Benchmark Evaluation Job Status (ADR 006)",
)
def get_evaluation_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Polls the execution status and output results of an asynchronous benchmark job.
    Enforces IDOR ownership protection (owner or admin only).
    """
    job_record = EvaluationLabService.get_job_status(job_id, db=db)
    if not job_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation job '{job_id}' not found.",
        )

    # IDOR Access Control: Admins or Job Creator only
    user_role_name = getattr(current_user.role, "role_name", "") if current_user.role else ""
    if not user_role_name and current_user.role_id and db:
        from app.models.auth import Role
        r = db.query(Role).filter(Role.role_id == current_user.role_id).first()
        if r:
            user_role_name = r.role_name

    is_admin = user_role_name.lower() == "admin"
    job_creator_id = job_record.get("created_by_user_id")
    if not is_admin and job_creator_id is not None and job_creator_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to view this benchmark job.",
        )

    return EvaluationJobStatusResponse(
        job_id=job_record["job_id"],
        created_by_user_id=job_record.get("created_by_user_id"),
        status=job_record["status"],
        progress_pct=job_record.get("progress_pct", 0.0),
        error=job_record.get("error"),
        result=job_record.get("result"),
        created_at=job_record["created_at"],
        completed_at=job_record.get("completed_at"),
    )


@router.post("/evaluation/run", response_model=EvaluationBenchmarkResponse)
async def run_evaluation_benchmark(
    request: EvaluationBenchmarkRequest,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Executes the Evaluation Lab benchmark synchronously comparing Baselines A, B, C, and D across categories.
    Strictly restricted to Admin role to prevent expensive computational abuse.
    """
    response = await EvaluationLabService.run_benchmark_suite(
        db=db,
        baseline_variants=request.baseline_variants,
        categories=request.categories,
        data_source_id=request.data_source_id,
    )
    return response


@router.get("/evaluation/latest", response_model=EvaluationBenchmarkResponse)
def get_latest_evaluation_benchmark(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the latest benchmark comparison matrix from database without re-executing.
    Requires authenticated user access.
    """
    response = EvaluationLabService.get_latest_evaluation_run(db=db)
    return response


