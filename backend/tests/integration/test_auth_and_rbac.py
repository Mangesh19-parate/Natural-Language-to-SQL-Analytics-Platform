import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.services.auth_service import AuthService
from app.models.auth import User, Role
from app.models.policy import DataPolicy, DataSource, SemanticCatalog

client = TestClient(app)


@pytest.fixture
def auth_test_context(db_session):
    """Provides test roles and data sources for auth tests."""
    app.dependency_overrides[get_db] = lambda: db_session

    # Ensure clean test roles
    role_admin = db_session.query(Role).filter(Role.role_name == "admin").first()
    if not role_admin:
        role_admin = Role(role_name="admin")
        db_session.add(role_admin)

    role_viewer = db_session.query(Role).filter(Role.role_name == "viewer").first()
    if not role_viewer:
        role_viewer = Role(role_name="viewer")
        db_session.add(role_viewer)

    role_analyst = db_session.query(Role).filter(Role.role_name == "analyst").first()
    if not role_analyst:
        role_analyst = Role(role_name="analyst")
        db_session.add(role_analyst)

    ds = db_session.query(DataSource).first()
    if not ds:
        ds = DataSource(name="Auth Test DB", db_type="sqlite", secret_ref="local", is_active=True)
        db_session.add(ds)

    db_session.flush()

    yield {
        "db": db_session,
        "admin_role": role_admin,
        "viewer_role": role_viewer,
        "analyst_role": role_analyst,
        "ds": ds,
    }

    app.dependency_overrides.clear()


def test_password_hashing_and_verification():
    raw_pw = "SecurePassword123!"
    hashed = AuthService.get_password_hash(raw_pw)
    assert hashed != raw_pw
    assert AuthService.verify_password(raw_pw, hashed) is True
    assert AuthService.verify_password("WrongPassword", hashed) is False


def test_auth_login_and_token_lifecycle(auth_test_context):
    db = auth_test_context["db"]
    admin_role = auth_test_context["admin_role"]

    test_email = "admin_test@trustengine.ai"
    user = db.query(User).filter(User.email == test_email).first()
    if not user:
        user = User(
            full_name="Admin Test User",
            email=test_email,
            password_hash=AuthService.get_password_hash("AdminPass123!"),
            role_id=admin_role.role_id,
            is_active=True,
        )
        db.add(user)
        db.flush()

    # Test invalid login
    res_bad = client.post(
        "/api/auth/login",
        json={"email": test_email, "password": "WrongPassword!"},
    )
    assert res_bad.status_code == 401

    # Test valid login
    res_good = client.post(
        "/api/auth/login",
        json={"email": test_email, "password": "AdminPass123!"},
    )
    assert res_good.status_code == 200
    data = res_good.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == test_email
    assert data["user"]["role_name"] == "admin"

    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # Test /auth/me with valid Bearer token
    res_me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert res_me.status_code == 200
    me_data = res_me.json()["data"]
    assert me_data["user"]["email"] == test_email
    assert me_data["role"]["role_name"] == "admin"

    # Test /auth/refresh
    res_refresh = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert res_refresh.status_code == 200
    new_token = res_refresh.json()["data"]["access_token"]
    assert new_token is not None


def test_policy_admin_matrix_and_fail_closed_visualization(auth_test_context):
    db = auth_test_context["db"]
    viewer_role = auth_test_context["viewer_role"]
    ds = auth_test_context["ds"]

    # Seed catalog entry for this data source
    cat = SemanticCatalog(
        data_source_id=ds.data_source_id,
        table_name="orders",
        column_name="order_id",
        semantic_type="identifier",
        sensitivity="NONE",
    )
    db.add(cat)
    db.flush()

    # Fetch policy matrix
    res = client.get(f"/api/policy/matrix?role_id={viewer_role.role_id}&data_source_id={ds.data_source_id}")
    assert res.status_code == 200
    matrix = res.json()["data"]
    assert matrix["role_name"] == "viewer"
    assert "tables" in matrix

    # Verify fail-closed flag for unconfigured tables
    for tbl in matrix["tables"]:
        if not tbl["is_explicit"]:
            assert tbl["is_fail_closed_denied"] is True
            assert tbl["access_level"] == "denied"


def test_data_policy_crud_operations(auth_test_context):
    db = auth_test_context["db"]
    analyst_role = auth_test_context["analyst_role"]
    ds = auth_test_context["ds"]

    # 1. Create a policy
    create_payload = {
        "role_id": analyst_role.role_id,
        "data_source_id": ds.data_source_id,
        "table_name": "orders",
        "column_name": None,
        "access_level": "read",
        "aggregate_allowed": True,
        "row_filter_sql": "total_amount > 50",
    }
    res_create = client.post("/api/policy", json=create_payload)
    assert res_create.status_code == 200
    pol_id = res_create.json()["data"]["policy_id"]

    # 2. List policies
    res_list = client.get(f"/api/policy?role_id={analyst_role.role_id}&table_name=orders")
    assert res_list.status_code == 200
    assert len(res_list.json()["data"]) >= 1

    # 3. Update policy
    res_update = client.put(
        f"/api/policy/{pol_id}",
        json={"row_filter_sql": "total_amount > 100", "aggregate_allowed": False},
    )
    assert res_update.status_code == 200
    assert res_update.json()["data"]["row_filter_sql"] == "total_amount > 100"
    assert res_update.json()["data"]["aggregate_allowed"] is False

    # 4. Delete policy
    res_del = client.delete(f"/api/policy/{pol_id}")
    assert res_del.status_code == 200

    # Verify fail-closed reversion
    res_after = client.get(f"/api/policy?role_id={analyst_role.role_id}&table_name=orders")
    assert len(res_after.json()["data"]) == 0
