import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.services.auth_service import AuthService
from app.models.auth import User, Role
from app.models.audit import Report
from app.models.policy import DataPolicy, DataSource, SemanticCatalog
from app.models.session import QueryHistory

client = TestClient(app)


@pytest.fixture
def security_test_context(db_session):
    """Sets up roles, test users (admin, analyst, viewer), and overrides get_db."""
    app.dependency_overrides[get_db] = lambda: db_session
    from app.services.auth_service import get_current_user
    app.dependency_overrides.pop(get_current_user, None)

    # Seed roles
    roles = {}
    for r_name in ["admin", "analyst", "viewer"]:
        r = db_session.query(Role).filter(Role.role_name == r_name).first()
        if not r:
            r = Role(role_name=r_name)
            db_session.add(r)
            db_session.flush()
        roles[r_name] = r

    # Seed users
    users = {}
    tokens = {}
    for r_name in ["admin", "analyst", "viewer"]:
        email = f"sec_{r_name}@trustengine.ai"
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(
                full_name=f"Security {r_name.capitalize()}",
                email=email,
                password_hash=AuthService.get_password_hash(f"{r_name.capitalize()}Pass123!"),
                role_id=roles[r_name].role_id,
                is_active=True,
            )
            db_session.add(u)
            db_session.flush()
        users[r_name] = u

        # Generate access token
        token = AuthService.create_access_token({
            "sub": str(u.user_id),
            "user_id": u.user_id,
            "email": u.email,
            "role_name": r_name,
            "role_id": u.role_id,
        })
        tokens[r_name] = token

    # Seed an active DataSource
    ds = db_session.query(DataSource).first()
    if not ds:
        ds = DataSource(name="Sec Test DB", db_type="sqlite", secret_ref="local", is_active=True)
        db_session.add(ds)
        db_session.flush()

    # Seed a policy: analyst can read 'customers', viewer is denied
    pol_analyst = DataPolicy(
        role_id=roles["analyst"].role_id,
        data_source_id=ds.data_source_id,
        table_name="customers",
        access_level="read",
        aggregate_allowed=True,
    )
    pol_viewer = DataPolicy(
        role_id=roles["viewer"].role_id,
        data_source_id=ds.data_source_id,
        table_name="customers",
        access_level="denied",
        aggregate_allowed=False,
    )
    db_session.add_all([pol_analyst, pol_viewer])
    db_session.flush()

    yield {
        "db": db_session,
        "roles": roles,
        "users": users,
        "tokens": tokens,
        "ds": ds,
    }

    app.dependency_overrides.clear()


def test_unauthenticated_requests_rejected(security_test_context):
    """Verifies that protected endpoints reject unauthenticated requests with HTTP 401."""
    # SQL validate
    res = client.post("/api/sql/validate", json={"sql": "SELECT * FROM customers;", "role_id": 1, "data_source_id": 1})
    assert res.status_code == 401

    # SQL execute
    res = client.post("/api/sql/execute", json={"sql": "SELECT * FROM customers;", "role_id": 1, "data_source_id": 1})
    assert res.status_code == 401

    # EXPLAIN ANALYZE
    res = client.post("/api/optimize/analyze", json={"sql": "SELECT * FROM customers;", "role_name": "admin"})
    assert res.status_code == 401

    # Policy mutation
    res = client.post("/api/policy", json={"role_id": 1, "data_source_id": 1, "table_name": "salaries", "access_level": "read"})
    assert res.status_code == 401

    # Report export
    res = client.post("/api/report/pdf", json={"title": "Test", "sql": "SELECT 1;", "user_id": 1})
    assert res.status_code == 401


def test_client_cannot_spoof_role_id_to_bypass_policy(security_test_context):
    """A Viewer token submitting role_id=1 in body cannot execute queries on denied tables."""
    viewer_token = security_test_context["tokens"]["viewer"]
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # Attempt to spoof role_id=1 (admin) to access 'customers' table
    res = client.post(
        "/api/sql/execute",
        headers=headers,
        json={
            "sql": "SELECT * FROM customers;",
            "role_id": 1,  # Spoofed admin role in payload
            "data_source_id": security_test_context["ds"].data_source_id,
        },
    )
    assert res.status_code == 200
    data = res.json()
    # Must be rejected because viewer's actual DB role denies 'customers'
    assert data["success"] is False
    assert "rejected by Policy Engine" in data["error"] or data["policy_validation"]["is_allowed"] is False


def test_non_admin_cannot_access_explain_analyze(security_test_context):
    """Analyst or Viewer tokens receive 403 on /optimize/analyze even if role_name='admin' in body."""
    analyst_token = security_test_context["tokens"]["analyst"]
    headers = {"Authorization": f"Bearer {analyst_token}"}

    res = client.post(
        "/api/optimize/analyze",
        headers=headers,
        json={
            "sql": "SELECT * FROM customers;",
            "role_name": "admin",  # Spoofed admin claim in payload
        },
    )
    assert res.status_code == 403
    assert "Access denied" in res.json().get("detail", "")


def test_owner_only_report_download(security_test_context):
    """User B cannot download User A's generated report (403 Forbidden), but Admin can."""
    db = security_test_context["db"]
    viewer_user = security_test_context["users"]["viewer"]
    analyst_token = security_test_context["tokens"]["analyst"]
    admin_token = security_test_context["tokens"]["admin"]
    viewer_token = security_test_context["tokens"]["viewer"]

    # Create a report owned by viewer_user
    report = Report(
        report_id="rpt_test_owner_123",
        user_id=viewer_user.user_id,
        title="Confidential Report",
        format="pdf",
        file_path="nonexistent_for_test.pdf",
        scope="single_query",
        status="ready",
        content_hash="hash123",
    )
    db.add(report)
    db.commit()

    # Analyst attempts to download Viewer's report -> 403 Forbidden
    res_analyst = client.get(
        f"/api/report/{report.report_id}/download",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert res_analyst.status_code == 403

    # Viewer (owner) requests report -> Not 403 (might be 404 because dummy file path)
    res_viewer = client.get(
        f"/api/report/{report.report_id}/download",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_viewer.status_code != 403

    # Admin requests report -> Not 403 (Admin has override access)
    res_admin = client.get(
        f"/api/report/{report.report_id}/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code != 403


def test_non_admin_cannot_mutate_policies(security_test_context):
    """Non-admin token receives 403 on POST/PUT/DELETE /api/policy."""
    analyst_token = security_test_context["tokens"]["analyst"]
    headers = {"Authorization": f"Bearer {analyst_token}"}

    res_post = client.post(
        "/api/policy",
        headers=headers,
        json={
            "role_id": 2,
            "data_source_id": security_test_context["ds"].data_source_id,
            "table_name": "salaries",
            "access_level": "read",
            "aggregate_allowed": True,
        },
    )
    assert res_post.status_code == 403

    res_put = client.put(
        "/api/policy/1",
        headers=headers,
        json={"access_level": "read"},
    )
    assert res_put.status_code == 403

    res_del = client.delete(
        "/api/policy/1",
        headers=headers,
    )
    assert res_del.status_code == 403


def test_registration_privilege_escalation_blocked(security_test_context):
    """Public registration with role_id=1 in body assigns 'viewer' role instead of admin."""
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Attacker Trying Admin",
            "email": "attacker@evil.com",
            "password": "Password123!",
            "role_id": 1,  # Attacker asking for admin role
        },
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["role_name"] == "viewer"
    assert data["role_id"] != 1


def test_plaintext_password_rejected():
    """Verifies that plain string and mock hash string comparisons fail verification."""
    raw_pw = "MySecretPass"
    assert AuthService.verify_password(raw_pw, raw_pw) is False
    assert AuthService.verify_password(raw_pw, f"mock_hash_{raw_pw}") is False

    # Bcrypt matches properly
    hashed = AuthService.get_password_hash(raw_pw)
    assert AuthService.verify_password(raw_pw, hashed) is True
