import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.policy import DataSource, DataPolicy
from app.models.auth import User, Role
from app.models.session import QueryHistory
from app.services.auth_service import (
    get_effective_role_id,
    authorize_resource_access,
    authorize_query_access,
    authorize_datasource,
    authorize_job_access,
)


@pytest.fixture
def security_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    admin_role = Role(role_id=1, role_name="admin")
    analyst_role = Role(role_id=2, role_name="analyst")
    viewer_role = Role(role_id=3, role_name="viewer")
    db.add_all([admin_role, analyst_role, viewer_role])

    user_admin = User(user_id=1, full_name="Admin User", email="admin@test.com", password_hash="dummy", role_id=1, is_active=True)
    user_alice = User(user_id=2, full_name="Alice Analyst", email="alice@test.com", password_hash="dummy", role_id=2, is_active=True)
    user_bob = User(user_id=3, full_name="Bob Viewer", email="bob@test.com", password_hash="dummy", role_id=3, is_active=True)
    user_inactive = User(user_id=4, full_name="Inactive User", email="inactive@test.com", password_hash="dummy", role_id=3, is_active=False)
    db.add_all([user_admin, user_alice, user_bob, user_inactive])

    ds1 = DataSource(data_source_id=1, name="DS1", db_type="sqlite", secret_ref="sqlite:///./test1.db", is_active=True)
    ds2 = DataSource(data_source_id=2, name="DS2", db_type="sqlite", secret_ref="sqlite:///./test2.db", is_active=True)
    db.add_all([ds1, ds2])

    # Grant Alice access to DS1 and DS2, but Bob has no policies on DS2
    dp1 = DataPolicy(role_id=2, data_source_id=1, table_name="sales", access_level="read")
    dp2 = DataPolicy(role_id=2, data_source_id=2, table_name="customers", access_level="read")
    dp3 = DataPolicy(role_id=3, data_source_id=1, table_name="sales", access_level="read")
    db.add_all([dp1, dp2, dp3])

    # Query created by Alice
    q1 = QueryHistory(
        query_id="query-alice-100",
        user_id=2,
        data_source_id=1,
        nl_question="Sales query",
        final_sql="SELECT * FROM sales",
        status="success",
    )
    db.add(q1)
    db.commit()

    yield {
        "db": db,
        "admin": user_admin,
        "alice": user_alice,
        "bob": user_bob,
        "inactive": user_inactive,
    }

    db.close()


def test_server_side_role_resolution_clamp(security_db_session):
    """Non-admin requesting Admin role_id=1 must be strictly clamped to their assigned role."""
    alice = security_db_session["alice"]
    bob = security_db_session["bob"]
    admin = security_db_session["admin"]

    # Non-admin requests role_id=1 (Admin)
    eff_alice = get_effective_role_id(current_user=alice, requested_role_id=1)
    assert eff_alice == 2  # Clamped to Analyst

    eff_bob = get_effective_role_id(current_user=bob, requested_role_id=1)
    assert eff_bob == 3  # Clamped to Viewer

    # Admin is permitted to simulate role_id=2
    eff_admin = get_effective_role_id(current_user=admin, requested_role_id=2)
    assert eff_admin == 2


def test_idor_query_access_enforcement(security_db_session):
    """Bob cannot access Alice's query history record (HTTP 403), Alice and Admin can."""
    db = security_db_session["db"]
    alice = security_db_session["alice"]
    bob = security_db_session["bob"]
    admin = security_db_session["admin"]

    # Alice accesses own query -> OK
    q_alice = authorize_query_access(db, alice, "query-alice-100", action="view")
    assert q_alice.query_id == "query-alice-100"

    # Admin accesses Alice's query -> OK
    q_admin = authorize_query_access(db, admin, "query-alice-100", action="view")
    assert q_admin.query_id == "query-alice-100"

    # Bob attempts to access Alice's query -> MUST RAISE HTTP 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        authorize_query_access(db, bob, "query-alice-100", action="view")
    assert exc_info.value.status_code == 403


def test_datasource_authorization_gate(security_db_session):
    """Bob is forbidden from accessing DS2 where his role has no active policies."""
    db = security_db_session["db"]
    alice = security_db_session["alice"]
    bob = security_db_session["bob"]
    admin = security_db_session["admin"]

    # Alice has policy on DS2 -> OK
    ds_alice = authorize_datasource(db, alice, data_source_id=2)
    assert ds_alice.data_source_id == 2

    # Admin accesses DS2 -> OK
    ds_admin = authorize_datasource(db, admin, data_source_id=2)
    assert ds_admin.data_source_id == 2

    # Bob has no policies on DS2 -> MUST RAISE HTTP 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        authorize_datasource(db, bob, data_source_id=2)
    assert exc_info.value.status_code == 403
