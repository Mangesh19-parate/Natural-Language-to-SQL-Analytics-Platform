import asyncio
import os
import tempfile
import time
import statistics
import pytest
import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base, BusinessBase
from app.db.session import get_db
from app.models.policy import DataSource, DataPolicy
from app.models.auth import Role, User
from app.services.auth_service import AuthService


def compute_percentiles(latencies: list[float]) -> dict:
    """Computes p50, p90, p95, p99 latency metrics in milliseconds."""
    if not latencies:
        return {}
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    return {
        "count": n,
        "p50_ms": round(statistics.median(sorted_lats) * 1000, 2),
        "p90_ms": round(sorted_lats[int(n * 0.90) if int(n * 0.90) < n else n - 1] * 1000, 2),
        "p95_ms": round(sorted_lats[int(n * 0.95) if int(n * 0.95) < n else n - 1] * 1000, 2),
        "p99_ms": round(sorted_lats[int(n * 0.99) if int(n * 0.99) < n else n - 1] * 1000, 2),
        "mean_ms": round(statistics.mean(sorted_lats) * 1000, 2),
        "max_ms": round(max(sorted_lats) * 1000, 2),
    }


@pytest.fixture(scope="function")
def concurrent_db():
    """
    Creates a dedicated SQLite file database with WAL mode and thread-safe connection pooling.
    """
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_concurrent.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
        pool_size=50,
        max_overflow=50,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    BusinessBase.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed data
    init_db = SessionLocal()
    try:
        for r_id, r_name in [(1, "admin"), (2, "compliance"), (3, "engineer"), (4, "viewer")]:
            role = init_db.query(Role).filter(Role.role_id == r_id).first()
            if not role:
                init_db.add(Role(role_id=r_id, role_name=r_name))
        
        for uid, r_id, r_name in [
            (101, 1, "admin"),
            (102, 1, "admin"),
            (103, 4, "viewer"),
            (104, 1, "admin"),
        ]:
            user = init_db.query(User).filter(User.user_id == uid).first()
            if not user:
                init_db.add(User(
                    user_id=uid,
                    full_name=f"Test {r_name.capitalize()} {uid}",
                    email=f"load_test_{uid}@trustengine.ai",
                    password_hash=AuthService.get_password_hash("TestPass123!"),
                    role_id=r_id,
                    is_active=True,
                ))

        ds = init_db.query(DataSource).filter(DataSource.data_source_id == 1).first()
        if not ds:
            init_db.add(DataSource(data_source_id=1, name="Default DB", db_type="sqlite", secret_ref="local", is_active=True))

        for table in ["employees", "departments", "sales", "customers", "orders", "products"]:
            for role_id in [1, 2, 3, 4]:
                init_db.add(DataPolicy(
                    role_id=role_id,
                    data_source_id=1,
                    table_name=table,
                    access_level="read",
                    aggregate_allowed=True,
                ))
        init_db.commit()
    finally:
        init_db.close()

    def get_test_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_test_db
    yield engine
    app.dependency_overrides.clear()
    engine.dispose()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)
    except Exception:
        pass


def _create_token(user_id: int, role_name: str, role_id: int) -> dict:
    token = AuthService.create_access_token({
        "sub": str(user_id),
        "user_id": user_id,
        "email": f"load_test_{user_id}@trustengine.ai",
        "role_name": role_name,
        "role_id": role_id,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_concurrent_join_plan_burst_10(concurrent_db):
    """
    Simulates 10 concurrent clients submitting complex multi-join queries
    to the Cost-Based Join Optimizer endpoint.
    """
    headers = _create_token(user_id=101, role_name="admin", role_id=1)
    payload = {
        "sql": "SELECT * FROM employees e JOIN departments d ON e.department_id = d.department_id JOIN sales s ON e.employee_id = s.employee_id",
        "data_source_id": 1,
        "max_allowed_cost": 500000.0,
    }

    transport = httpx.ASGITransport(app=app)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=timeout) as client:
        latencies = []

        async def send_req():
            t0 = time.perf_counter()
            resp = await client.post("/api/optimize/join-plan", json=payload, headers=headers)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
            return resp

        responses = await asyncio.gather(*(send_req() for _ in range(10)))

        assert all(r.status_code == 200 for r in responses), f"Errors: {[r.text for r in responses if r.status_code != 200]}"
        metrics = compute_percentiles(latencies)
        assert metrics["p95_ms"] < 2500.0, f"p95 latency {metrics['p95_ms']}ms exceeds 2500ms SLA"
        print(f"\n[LoadTest 10 Concurrency] JoinPlan Metrics: {metrics}")


@pytest.mark.asyncio
async def test_concurrent_join_plan_burst_50(concurrent_db):
    """
    Simulates 50 concurrent requests evaluating DP Join Optimizer trees
    to verify worker threadpool isolation and non-blocking event-loop behavior.
    """
    headers = _create_token(user_id=102, role_name="admin", role_id=1)
    payload = {
        "sql": "SELECT e.first_name, d.department_name, s.amount FROM employees e JOIN departments d ON e.department_id = d.department_id JOIN sales s ON e.employee_id = s.employee_id WHERE s.amount > 100",
        "data_source_id": 1,
        "max_allowed_cost": 500000.0,
    }

    transport = httpx.ASGITransport(app=app)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=timeout) as client:
        latencies = []

        async def send_req():
            t0 = time.perf_counter()
            resp = await client.post("/api/optimize/join-plan", json=payload, headers=headers)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
            return resp

        responses = await asyncio.gather(*(send_req() for _ in range(50)))

        assert all(r.status_code == 200 for r in responses), f"Errors: {[r.text for r in responses if r.status_code != 200]}"
        metrics = compute_percentiles(latencies)
        assert metrics["p95_ms"] < 3500.0, f"p95 latency {metrics['p95_ms']}ms exceeds 3500ms SLA"
        print(f"\n[LoadTest 50 Concurrency] JoinPlan Metrics: {metrics}")


@pytest.mark.asyncio
async def test_concurrent_sql_validation_burst_100(concurrent_db):
    """
    Simulates 100 concurrent requests to AST Policy validation endpoint.
    Verifies that synchronous AST parsing and policy evaluation execute across
    worker threads without event-loop starvation.
    """
    headers = _create_token(user_id=103, role_name="viewer", role_id=4)
    payload = {
        "sql": "SELECT employee_id, first_name, department_id FROM employees WHERE department_id = 2",
        "data_source_id": 1,
        "role_id": 4,
    }

    transport = httpx.ASGITransport(app=app)
    timeout = httpx.Timeout(45.0)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=timeout) as client:
        latencies = []

        async def send_req():
            t0 = time.perf_counter()
            resp = await client.post("/api/sql/validate", json=payload, headers=headers)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
            return resp

        responses = await asyncio.gather(*(send_req() for _ in range(100)))

        assert all(r.status_code == 200 for r in responses), f"Errors: {[r.text for r in responses if r.status_code != 200]}"
        metrics = compute_percentiles(latencies)
        assert metrics["p95_ms"] < 5000.0, f"p95 latency {metrics['p95_ms']}ms exceeds 5000ms SLA"
        print(f"\n[LoadTest 100 Concurrency] Validation Metrics: {metrics}")


@pytest.mark.asyncio
async def test_concurrent_token_revocation_under_load(concurrent_db):
    """
    Verifies concurrent token verification and revocation under high contention.
    """
    headers = _create_token(user_id=104, role_name="admin", role_id=1)

    transport = httpx.ASGITransport(app=app)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=timeout) as client:
        async def verify_me():
            return await client.get("/api/auth/me", headers=headers)

        # Run 30 concurrent auth checks
        responses = await asyncio.gather(*(verify_me() for _ in range(30)))
        assert all(r.status_code == 200 for r in responses), f"Errors: {[r.text for r in responses if r.status_code != 200]}"

        # Logout (revoke)
        logout_resp = await client.post("/api/auth/logout", headers=headers)
        assert logout_resp.status_code == 200

        # Run 30 concurrent checks after logout - all must be rejected 401
        responses_after = await asyncio.gather(*(verify_me() for _ in range(30)))
        assert all(r.status_code == 401 for r in responses_after)
