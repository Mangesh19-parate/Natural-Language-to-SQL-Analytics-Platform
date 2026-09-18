import uuid
from collections import Counter
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text

from app.main import app
from app.models.auth import User, Role
from app.models.session import QueryHistory
from app.models.policy import DataSource
from app.services.auth_service import AuthService, authorize_query_access
from app.services.data_source_manager import DataSourceManager
from app.services.optimizer import CostBasedJoinOptimizer
from app.services.execution_sandbox import ExecutionSandboxService


def create_user_with_role(db: Session, user_id: int, email: str, role_name: str) -> User:
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if not role:
        role = Role(role_name=role_name)
        db.add(role)
        db.commit()

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(
            user_id=user_id,
            email=email,
            full_name=f"Test {role_name.capitalize()}",
            password_hash=AuthService.get_password_hash("SecurePass123!"),
            role_id=role.role_id,
            is_active=True,
        )
        db.add(user)
        db.commit()
    return user


def get_auth_headers_for_user(user: User) -> dict:
    role_name = user.role.role_name if user.role else "viewer"
    token = AuthService.create_access_token(
        data={
            "sub": str(user.user_id),
            "user_id": user.user_id,
            "email": user.email,
            "role_name": role_name,
            "role_id": user.role_id,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_idor_query_ownership_invariant(db_session: Session):
    """
    Invariant: For any query_id owned by User A, User B cannot view, rerun, or delete it,
    while Admin retains supervisory access.
    """
    user_a = create_user_with_role(db_session, 301, "alice@example.com", "analyst")
    user_b = create_user_with_role(db_session, 302, "bob@example.com", "analyst")
    admin_user = create_user_with_role(db_session, 303, "admin_auditor@example.com", "admin")

    query_id = f"q-{uuid.uuid4().hex[:10]}"
    q_entry = QueryHistory(
        query_id=query_id,
        user_id=user_a.user_id,
        nl_question="What are total sales by department?",
        final_sql="SELECT department_id, SUM(amount) FROM sales GROUP BY department_id;",
        status="success",
    )
    db_session.add(q_entry)
    db_session.commit()

    # User A (Owner) can access
    accessible_by_a = authorize_query_access(db_session, user_a, query_id, action="view")
    assert accessible_by_a.query_id == query_id

    # User B (Attacker / Different Tenant) is strictly denied with HTTP 403
    with pytest.raises(HTTPException) as exc_info:
        authorize_query_access(db_session, user_b, query_id, action="view")
    assert exc_info.value.status_code == 403

    # Admin retains audit access
    admin_access = authorize_query_access(db_session, admin_user, query_id, action="view")
    assert admin_access.query_id == query_id


def test_idor_history_endpoints_http_contract(db_session: Session):
    """
    Invariant: HTTP API endpoints (/history/{id}, /history/{id}/rerun, DELETE /history/{id})
    strictly deny cross-user access with HTTP 403.
    """
    client = TestClient(app)
    user_a = create_user_with_role(db_session, 311, "owner_a@example.com", "viewer")
    user_b = create_user_with_role(db_session, 312, "attacker_b@example.com", "viewer")

    headers_a = get_auth_headers_for_user(user_a)
    headers_b = get_auth_headers_for_user(user_b)

    query_id = f"q-{uuid.uuid4().hex[:10]}"
    q_entry = QueryHistory(
        query_id=query_id,
        user_id=user_a.user_id,
        nl_question="List customer cities",
        final_sql="SELECT city FROM customers;",
        status="success",
    )
    db_session.add(q_entry)
    db_session.commit()

    # 1. User B cannot view User A's query detail
    res_get = client.get(f"/api/history/{query_id}", headers=headers_b)
    assert res_get.status_code == 403

    # 2. User B cannot rerun User A's query
    res_rerun = client.post(f"/api/history/{query_id}/rerun", json={}, headers=headers_b)
    assert res_rerun.status_code == 403

    # 3. User B cannot delete User A's query
    res_del = client.delete(f"/api/history/{query_id}", headers=headers_b)
    assert res_del.status_code == 403

    # Verify query still exists in DB
    assert db_session.query(QueryHistory).filter(QueryHistory.query_id == query_id).first() is not None

    # 4. User A can successfully delete their own query
    res_del_owner = client.delete(f"/api/history/{query_id}", headers=headers_a)
    assert res_del_owner.status_code == 200
    assert db_session.query(QueryHistory).filter(QueryHistory.query_id == query_id).first() is None


def test_user_listing_admin_authorization_invariant(db_session: Session):
    """
    Invariant: GET /api/auth/users is strictly gated to admin role.
    Viewers and Analysts receive HTTP 403 Forbidden.
    """
    client = TestClient(app)
    viewer_user = create_user_with_role(db_session, 321, "viewer_list@example.com", "viewer")
    admin_user = create_user_with_role(db_session, 322, "admin_list@example.com", "admin")

    viewer_headers = get_auth_headers_for_user(viewer_user)
    admin_headers = get_auth_headers_for_user(admin_user)

    # Viewer rejected
    res_viewer = client.get("/api/auth/users", headers=viewer_headers)
    assert res_viewer.status_code == 403

    # Admin authorized
    res_admin = client.get("/api/auth/users", headers=admin_headers)
    assert res_admin.status_code == 200
    assert len(res_admin.json()["data"]) >= 2


def test_multi_source_connection_routing_invariant(db_session: Session):
    """
    Invariant: DataSourceManager dynamically maps distinct data_source_ids to isolated engine pools.
    """
    # Test primary engine resolution for ID 1
    engine_1 = DataSourceManager.get_engine(db_session, data_source_id=1)
    assert engine_1 is not None

    # Register dynamic data source 2
    ds_2 = db_session.query(DataSource).filter(DataSource.data_source_id == 2).first()
    if not ds_2:
        ds_2 = DataSource(
            data_source_id=2,
            name="Analytics Replica",
            db_type="sqlite",
            database_name="business.db",
            secret_ref="sqlite:///./local_data/business.db",
            is_active=True,
        )
        db_session.add(ds_2)
        db_session.commit()

    engine_2 = DataSourceManager.get_engine(db_session, data_source_id=2)
    assert engine_2 is not None

    # Verify health check against engine 2
    health = DataSourceManager.check_health(db_session, data_source_id=2)
    assert health["status"] == "healthy"


def test_optimizer_result_multiset_equivalence_invariant():
    """
    Invariant: Optimal join reordering of commutative/associative INNER joins
    preserves exact multiset relational equivalence with original query.
    """
    test_engine = create_engine("sqlite:///:memory:")
    with test_engine.connect() as conn:
        conn.execute(text("CREATE TABLE t_customers (customer_id INT PRIMARY KEY, city TEXT);"))
        conn.execute(text("CREATE TABLE t_orders (order_id INT PRIMARY KEY, customer_id INT, amount REAL);"))
        conn.execute(text("INSERT INTO t_customers VALUES (1, 'Mumbai'), (2, 'Pune'), (3, 'Delhi');"))
        conn.execute(text("INSERT INTO t_orders VALUES (101, 1, 500.0), (102, 1, 300.0), (103, 2, 750.0);"))
        conn.commit()

    orig_sql = "SELECT c.customer_id, c.city, o.amount FROM t_orders o JOIN t_customers c ON o.customer_id = c.customer_id"
    plan = CostBasedJoinOptimizer.optimize_query(orig_sql, engine=test_engine)

    orig_res = ExecutionSandboxService.execute_query(test_engine, orig_sql)
    opt_res = ExecutionSandboxService.execute_query(test_engine, plan.optimized_sql or orig_sql)

    assert orig_res.success and opt_res.success

    # Multiset equality over normalized row tuples
    orig_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in orig_res.rows]
    opt_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in opt_res.rows]
    assert Counter(orig_tuples) == Counter(opt_tuples)
