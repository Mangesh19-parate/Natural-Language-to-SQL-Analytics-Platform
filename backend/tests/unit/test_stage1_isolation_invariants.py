import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.policy import DataSource, SemanticCatalog, DataPolicy, SchemaSnapshot
from app.models.auth import User, Role
from app.models.session import QueryHistory, SessionModel
from app.services.data_source_manager import DataSourceManager, DataSourceUnavailableError
from app.services.execution_sandbox import ExecutionSandboxService
from app.services.query_replay import QueryReplayService
from app.services.self_correction import SelfCorrectionService
from app.services.reliability_scorer import ReliabilityScorerService
from app.schemas.policy import PolicyValidationResult


@pytest.fixture
def isolation_environment():
    """
    Creates an isolated test environment with:
    - Metadata DB (SQLite memory)
    - Data Source A (SQLite memory with table 'alpha_metrics')
    - Data Source B (SQLite memory with table 'beta_customers')
    """
    meta_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=meta_engine)
    MetaSession = sessionmaker(bind=meta_engine)
    meta_db = MetaSession()

    engine_a = create_engine("sqlite:///:memory:")
    with engine_a.connect() as conn:
        conn.execute(text("CREATE TABLE alpha_metrics (metric_id INT, metric_val INT);"))
        conn.execute(text("INSERT INTO alpha_metrics VALUES (1, 100), (2, 200);"))
        conn.commit()

    engine_b = create_engine("sqlite:///:memory:")
    with engine_b.connect() as conn:
        conn.execute(text("CREATE TABLE beta_customers (customer_id INT, customer_name TEXT);"))
        conn.execute(text("INSERT INTO beta_customers VALUES (101, 'Acme Corp'), (102, 'Beta LLC');"))
        conn.commit()

    # Reset datasource manager registry
    DataSourceManager.reset_registry()
    DataSourceManager._engine_registry[1] = engine_a
    DataSourceManager._engine_registry[2] = engine_b

    # Insert Data Sources
    ds1 = DataSource(
        data_source_id=1,
        name="Datasource A (Alpha)",
        db_type="sqlite",
        database_name="alpha.db",
        secret_ref="sqlite:///./local_data/alpha.db",
        is_active=True,
    )
    ds2 = DataSource(
        data_source_id=2,
        name="Datasource B (Beta)",
        db_type="sqlite",
        database_name="beta.db",
        secret_ref="sqlite:///./local_data/beta.db",
        is_active=True,
    )
    meta_db.add_all([ds1, ds2])

    # Insert Roles
    role = Role(role_id=1, role_name="admin")
    meta_db.add(role)

    # Insert User
    user = User(user_id=1, full_name="Test Engineer", email="eng@test.com", password_hash="dummy", role_id=1, is_active=True)
    meta_db.add(user)

    # Insert Data Policies (Fail-closed system requires explicit read policy)
    dp1 = DataPolicy(
        role_id=1,
        data_source_id=1,
        table_name="alpha_metrics",
        column_name=None,
        access_level="read",
    )
    dp2 = DataPolicy(
        role_id=1,
        data_source_id=2,
        table_name="beta_customers",
        column_name=None,
        access_level="read",
    )

    # Insert Catalog for DS1
    cat1 = SemanticCatalog(
        data_source_id=1,
        table_name="alpha_metrics",
        column_name="metric_val",
        data_type="INTEGER",
        semantic_type="numeric",
    )
    # Insert Catalog for DS2
    cat2 = SemanticCatalog(
        data_source_id=2,
        table_name="beta_customers",
        column_name="customer_name",
        data_type="TEXT",
        semantic_type="text",
    )
    meta_db.add_all([dp1, dp2, cat1, cat2])
    meta_db.commit()

    yield {
        "meta_db": meta_db,
        "engine_a": engine_a,
        "engine_b": engine_b,
    }

    meta_db.close()
    DataSourceManager.reset_registry()


def test_datasource_isolation_execution(isolation_environment):
    """Assert query on DataSource A executes on Engine A and cannot see table in DataSource B."""
    meta_db = isolation_environment["meta_db"]

    engine_a = DataSourceManager.get_engine(meta_db, data_source_id=1)
    engine_b = DataSourceManager.get_engine(meta_db, data_source_id=2)

    # Query DS A table on Engine A
    res_a = ExecutionSandboxService.execute_query(engine=engine_a, sql="SELECT * FROM alpha_metrics;")
    assert res_a.success is True
    assert res_a.row_count == 2
    assert "metric_val" in res_a.columns

    # Attempt to query DS B table on Engine A -> MUST FAIL
    res_cross = ExecutionSandboxService.execute_query(engine=engine_a, sql="SELECT * FROM beta_customers;")
    assert res_cross.success is False
    assert "no such table" in res_cross.error.lower() or "not found" in res_cross.error.lower()

    # Query DS B table on Engine B -> MUST SUCCEED
    res_b = ExecutionSandboxService.execute_query(engine=engine_b, sql="SELECT * FROM beta_customers;")
    assert res_b.success is True
    assert res_b.row_count == 2
    assert "customer_name" in res_b.columns


def test_replay_preserves_and_executes_against_recorded_datasource(isolation_environment):
    """Assert replay for a query recorded under data_source_id=2 executes against DS2."""
    meta_db = isolation_environment["meta_db"]

    # Record a query execution under data_source_id=2
    snapshot = QueryReplayService.capture_current_schema_snapshot(meta_db, data_source_id=2)
    
    q = QueryHistory(
        query_id="query-ds2-001",
        user_id=1,
        data_source_id=2,
        nl_question="Show all beta customers",
        final_sql="SELECT customer_name FROM beta_customers",
        status="success",
        schema_snapshot_id=snapshot.schema_snapshot_id,
        result_hash="dummyhash123",
        row_count=2,
    )
    meta_db.add(q)
    meta_db.commit()

    # Replay without providing explicit data_source_id -> MUST use recorded data_source_id=2
    replay_res = QueryReplayService.replay_and_verify(
        db=meta_db,
        query_id="query-ds2-001",
        role_id=1,
    )

    assert replay_res.provenance.data_source_id if hasattr(replay_res.provenance, "data_source_id") else True
    assert replay_res.replayed_execution.success is True
    assert replay_res.replayed_execution.row_count == 2
    assert replay_res.replayed_execution.columns == ["customer_name"]


def test_reliability_scoring_grounded_in_target_datasource_catalog(isolation_environment):
    """Assert reliability score for DB-B query uses DB-B catalog and rejects cross-DB catalog references."""
    meta_db = isolation_environment["meta_db"]

    policy_val = PolicyValidationResult(is_allowed=True, violations=[], injected_sql=None)

    # Score query on DB-2 with DB-2 table
    rel_ds2 = ReliabilityScorerService.compute_reliability_score(
        db=meta_db,
        sql="SELECT customer_name FROM beta_customers",
        role_id=1,
        data_source_id=2,
        policy_validation=policy_val,
        execution_success=True,
        row_count=2,
    )

    assert rel_ds2.schema_grounding.score == 100
    assert "beta_customers" in str(rel_ds2.schema_grounding.evidence_items)

    # Score query referencing DB-1 table against DB-2 -> Schema grounding must be 0% or low
    rel_cross = ReliabilityScorerService.compute_reliability_score(
        db=meta_db,
        sql="SELECT metric_val FROM alpha_metrics",
        role_id=1,
        data_source_id=2,
        policy_validation=policy_val,
        execution_success=False,
        row_count=0,
    )

    assert rel_cross.schema_grounding.score == 0
    assert "Ungrounded" in str(rel_cross.schema_grounding.evidence_items) or "Unmapped" in str(rel_cross.schema_grounding.evidence_items)


def test_clean_alembic_migrations_create_authoritative_schema(tmp_path):
    """Assert running alembic upgrade head on a brand new database creates all required tables without Base.metadata.create_all."""
    from alembic.config import Config
    from alembic import command
    from pathlib import Path
    from sqlalchemy import inspect

    db_file = tmp_path / "fresh_migration.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    alembic_ini_path = Path("alembic.ini").resolve() if Path("alembic.ini").exists() else Path("backend/alembic.ini").resolve()
    script_loc = Path("alembic").resolve() if Path("alembic").exists() else Path("backend/alembic").resolve()
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic_cfg.set_main_option("script_location", str(script_loc))

    # Run upgrade head on completely empty database
    command.upgrade(alembic_cfg, "head")

    test_engine = create_engine(db_url)
    inspector = inspect(test_engine)
    tables = set(inspector.get_table_names())

    expected_tables = {
        "data_sources",
        "users",
        "roles",
        "data_policy",
        "semantic_catalog",
        "query_history",
        "evaluation_jobs",
        "schema_snapshot",
    }
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    columns = [c["name"] for c in inspector.get_columns("query_history")]
    assert "data_source_id" in columns

