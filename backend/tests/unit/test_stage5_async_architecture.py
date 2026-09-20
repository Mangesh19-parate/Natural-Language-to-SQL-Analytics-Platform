import os
import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.models.auth import User, Role
from app.models.lab import EvaluationJob
from app.models.policy import DataSource, DataPolicy
from app.services.auth_service import AuthService
from app.services.evaluation_lab import EvaluationLabService
from app.services.storage_service import StorageService


@pytest.fixture
def stage5_db(db_session: Session):
    """Sets up users, roles, and policies for Stage 5 async testing."""
    role_admin = Role(role_id=1, role_name="admin")
    role_viewer = Role(role_id=3, role_name="viewer")
    db_session.add_all([role_admin, role_viewer])
    db_session.flush()

    user_admin = User(
        user_id=10,
        email="admin_stage5@test.com",
        full_name="Admin Stage 5",
        password_hash=AuthService.get_password_hash("AdminPass123!"),
        role_id=1,
        is_active=True,
    )
    user_viewer = User(
        user_id=20,
        email="viewer_stage5@test.com",
        full_name="Viewer Stage 5",
        password_hash=AuthService.get_password_hash("ViewerPass123!"),
        role_id=3,
        is_active=True,
    )
    ds = DataSource(data_source_id=1, name="Async DB", db_type="postgresql", secret_ref="env:TEST", is_active=True)
    db_session.add_all([user_admin, user_viewer, ds])

    for tbl in ["customers", "departments", "employees", "products", "orders", "sales"]:
        db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name=tbl, access_level="read", aggregate_allowed=True))

    db_session.commit()
    return db_session


def test_stage5_job_durability_and_db_fallback(stage5_db: Session):
    """
    Stage 5 Invariant: Durable Job State.
    Verify that job state persisted in the database is fully recoverable
    even if the in-memory cache is wiped.
    """
    job_id = f"job-test-{uuid.uuid4().hex[:8]}"
    db_job = EvaluationJob(
        job_id=job_id,
        created_by_user_id=10,
        status="completed",
        progress_pct=100.0,
        result_json='{"run_id":"run-1","total_questions":10,"tested_baselines":[],"overall_metrics":{},"category_breakdown":[],"detailed_results":[],"executed_at":"2026-09-20T00:00:00"}',
    )
    stage5_db.add(db_job)
    stage5_db.commit()

    # Clear in-memory job cache to simulate process restart
    with EvaluationLabService._job_lock:
        EvaluationLabService._jobs.pop(job_id, None)

    # Status must recover seamlessly from the database
    recovered = EvaluationLabService.get_job_status(job_id, db=stage5_db)
    assert recovered is not None
    assert recovered["job_id"] == job_id
    assert recovered["status"] == "completed"
    assert recovered["progress_pct"] == 100.0
    assert recovered["result"] is not None


def test_stage5_job_cancellation_lifecycle(stage5_db: Session):
    """
    Stage 5 Invariant: Job Cancellation.
    Verify that an enqueued/running job can be cancelled, transitioning status to 'cancelled'.
    """
    job_id = f"job-cancel-{uuid.uuid4().hex[:8]}"
    db_job = EvaluationJob(
        job_id=job_id,
        created_by_user_id=10,
        status="running",
        progress_pct=25.0,
    )
    stage5_db.add(db_job)
    stage5_db.commit()

    with EvaluationLabService._job_lock:
        EvaluationLabService._jobs[job_id] = {
            "job_id": job_id,
            "created_by_user_id": 10,
            "status": "running",
            "progress_pct": 25.0,
            "error": None,
            "result": None,
            "created_at": "2026-09-20T00:00:00",
            "completed_at": None,
        }

    # Execute cancellation
    cancelled = EvaluationLabService.cancel_job(job_id, db=stage5_db)
    assert cancelled is True

    # Verify status in database
    status = EvaluationLabService.get_job_status(job_id, db=stage5_db)
    assert status["status"] == "cancelled"


def test_stage5_storage_service_abstraction(tmp_path):
    """
    Stage 5 Invariant: Storage Abstraction.
    Verify that StorageService stores and retrieves binary artifacts (reports, exports)
    with metadata round-trip.
    """
    storage = StorageService()
    test_bytes = b"PDF-1.4 Mock Report Content for Benchmark"
    filename = f"benchmark_report_{uuid.uuid4().hex[:6]}.pdf"

    stored = storage.store_artifact(
        content=test_bytes,
        filename=filename,
        content_type="application/pdf",
        prefix="benchmarks",
    )

    assert stored["file_key"] == f"benchmarks/{filename}"
    assert stored["size_bytes"] == len(test_bytes)
    assert stored["content_type"] == "application/pdf"

    retrieved = storage.retrieve_artifact(stored["file_key"])
    assert retrieved == test_bytes


def test_stage5_job_cancel_idor_protection(stage5_db: Session):
    """
    Stage 5 Invariant: IDOR Protection on Job Operations.
    Non-admin user cannot cancel another user's job.
    """
    client = TestClient(app)

    # Job created by Admin (user_id=10)
    job_id = f"job-idor-{uuid.uuid4().hex[:8]}"
    db_job = EvaluationJob(
        job_id=job_id,
        created_by_user_id=10,
        status="running",
        progress_pct=50.0,
    )
    stage5_db.add(db_job)
    stage5_db.commit()

    # Viewer token (user_id=20)
    token_viewer = AuthService.create_access_token(
        data={"sub": "20", "user_id": 20, "email": "viewer_stage5@test.com", "role_name": "viewer", "role_id": 3}
    )
    viewer_headers = {"Authorization": f"Bearer {token_viewer}"}

    # Viewer tries to cancel admin's job -> 403 Forbidden
    res = client.post(f"/api/lab/evaluation/jobs/{job_id}/cancel", headers=viewer_headers)
    assert res.status_code == 403

    # Viewer tries to read admin's job -> 403 Forbidden
    res_get = client.get(f"/api/lab/evaluation/jobs/{job_id}", headers=viewer_headers)
    assert res_get.status_code == 403
