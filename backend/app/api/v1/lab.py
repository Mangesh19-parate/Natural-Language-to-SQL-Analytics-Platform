from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.auth import User
from app.schemas.lab import (
    SecurityAttackRunRequest,
    SecurityAttackRunResponse,
    EvaluationBenchmarkRequest,
    EvaluationBenchmarkResponse,
)
from app.services.auth_service import get_current_user, require_roles
from app.services.security_attack_lab import SecurityAttackLabService
from app.services.evaluation_lab import EvaluationLabService

router = APIRouter(prefix="/lab", tags=["Security & Evaluation Labs"])


@router.post("/security/run", response_model=SecurityAttackRunResponse)
async def run_security_attack_suite(
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
async def get_latest_security_attack_run(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the latest standing Security Attack Lab run.
    Requires authenticated user access.
    """
    response = SecurityAttackLabService.execute_attack_suite(
        db=db,
        data_source_id=1,
    )
    return response


@router.post("/evaluation/run", response_model=EvaluationBenchmarkResponse)
async def run_evaluation_benchmark(
    request: EvaluationBenchmarkRequest,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """
    Executes the Evaluation Lab benchmark comparing Baselines A, B, C, and D across 9 categories (REQ-EVALLAB-01).
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
async def get_latest_evaluation_benchmark(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the benchmark comparison matrix across all 4 baseline variants.
    Requires authenticated user access.
    """
    response = await EvaluationLabService.run_benchmark_suite(
        db=db,
        data_source_id=1,
    )
    return response

