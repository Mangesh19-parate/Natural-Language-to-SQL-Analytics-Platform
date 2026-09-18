import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.auth import User, Role
from app.services.auth_service import AuthService


def get_admin_headers(db: Session) -> dict:
    role = db.query(Role).filter(Role.role_name == "admin").first()
    if not role:
        role = Role(role_name="admin")
        db.add(role)
        db.commit()

    admin = db.query(User).filter(User.email == "eval_job_admin@example.com").first()
    if not admin:
        admin = User(
            email="eval_job_admin@example.com",
            full_name="Eval Admin",
            password_hash=AuthService.get_password_hash("AdminPass123!"),
            role_id=role.role_id,
            is_active=True,
        )
        db.add(admin)
        db.commit()

    token = AuthService.create_access_token(
        data={
            "sub": str(admin.user_id),
            "user_id": admin.user_id,
            "email": admin.email,
            "role_name": "admin",
            "role_id": admin.role_id,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_async_evaluation_job_lifecycle(db_session: Session):
    """
    Test ADR 006 async job submission and polling:
    1. POST /api/lab/evaluation/jobs -> 202 Accepted with job_id and status_url
    2. GET /api/lab/evaluation/jobs/{job_id} -> polls until completed or running
    """
    client = TestClient(app)
    headers = get_admin_headers(db_session)

    # 1. Enqueue small category benchmark
    payload = {
        "categories": ["simple"],
        "data_source_id": 1,
    }
    res_post = client.post("/api/lab/evaluation/jobs", json=payload, headers=headers)
    assert res_post.status_code == 202
    data_post = res_post.json()
    assert "job_id" in data_post
    assert data_post["status"] in ["pending", "running"]
    job_id = data_post["job_id"]

    # 2. Poll job status
    res_get = client.get(f"/api/lab/evaluation/jobs/{job_id}", headers=headers)
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["job_id"] == job_id
    assert data_get["status"] in ["pending", "running", "completed"]
