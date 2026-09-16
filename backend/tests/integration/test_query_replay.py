import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.models.session import QueryHistory
from app.models.policy import SchemaSnapshot, SemanticCatalog, DataSource, DataPolicy
from app.models.auth import Role
from app.services.query_replay import QueryReplayService
from tests.conftest import create_test_auth_headers

client = TestClient(app)


@pytest.fixture
def seed_replay_data(db_session):
    """Seeds test data for replay tests and wires get_db override."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = db_session.query(DataSource).first()
    if not ds:
        ds = DataSource(name="Replay Test DB", db_type="sqlite", secret_ref="local", is_active=True)
        db_session.add(ds)

    role_admin = db_session.query(Role).filter(Role.role_name == "admin").first()
    if not role_admin:
        role_admin = Role(role_name="admin")
        db_session.add(role_admin)

    db_session.flush()

    db_session.add(
        DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="customers", access_level="read", aggregate_allowed=True)
    )
    db_session.flush()

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
    }

    app.dependency_overrides.clear()


def test_schema_drift_detection_unit():
    # Historical snapshot
    hist_schema = {
        "tables": {
            "customers": {
                "columns": {
                    "customer_id": {"data_type": "INTEGER", "sensitivity": "NONE"},
                    "customer_name": {"data_type": "VARCHAR(150)", "sensitivity": "MEDIUM"},
                    "city": {"data_type": "VARCHAR(100)", "sensitivity": "NONE"},
                }
            }
        }
    }

    # Current schema with structural drift: new column, altered sensitivity, new table
    curr_schema = {
        "tables": {
            "customers": {
                "columns": {
                    "customer_id": {"data_type": "INTEGER", "sensitivity": "NONE"},
                    "customer_name": {"data_type": "VARCHAR(150)", "sensitivity": "HIGH"},  # Sensitivity changed
                    "city": {"data_type": "VARCHAR(100)", "sensitivity": "NONE"},
                    "country": {"data_type": "VARCHAR(100)", "sensitivity": "NONE"},  # Column added
                }
            },
            "audit_logs": {  # Table added
                "columns": {
                    "log_id": {"data_type": "INTEGER", "sensitivity": "NONE"}
                }
            }
        }
    }

    drift_report = QueryReplayService.detect_schema_drift(
        historical_schema=hist_schema,
        current_schema=curr_schema,
        historical_snapshot_id="test-snap-001",
        captured_at=datetime.now(timezone.utc),
    )

    assert drift_report.has_drift is True
    assert drift_report.drift_warning is not None
    assert "⚠ Schema has changed since this run" in drift_report.drift_warning
    assert "audit_logs" in drift_report.added_tables
    assert any(sc["column"] == "customer_name" for sc in drift_report.sensitivity_changes)


def test_query_replay_api_and_provenance(seed_replay_data):
    db = seed_replay_data["db"]
    ds_id = seed_replay_data["ds_id"]
    role_id = seed_replay_data["role_id"]

    # 1. Capture snapshot
    snapshot = QueryReplayService.capture_current_schema_snapshot(db, data_source_id=ds_id)
    assert snapshot.schema_snapshot_id is not None

    # 2. Seed query with provenance record
    q_id = str(uuid.uuid4())
    sql = "SELECT customer_id, customer_name, city FROM customers LIMIT 5"
    
    # Execute query once to compute initial result hash
    from app.services.execution_sandbox import ExecutionSandboxService
    from app.db.session import business_engine
    init_exec = ExecutionSandboxService.execute_query(business_engine, sql)
    init_hash = QueryReplayService.compute_result_hash(init_exec.columns, init_exec.rows)

    q_item = QueryHistory(
        query_id=q_id,
        nl_question="Show 5 customer names and cities",
        final_sql=sql,
        status="success",
        schema_snapshot_id=snapshot.schema_snapshot_id,
        prompt_version="v1.4",
        model_name="gpt-4o-mini",
        model_params={"temperature": 0.0, "max_tokens": 512},
        result_hash=init_hash,
        execution_ms=init_exec.latency_ms,
        row_count=init_exec.row_count,
        reliability_breakdown={"composite": 95.0, "schema_grounding": 100.0},
    )
    db.add(q_item)
    db.commit()

    headers = create_test_auth_headers(db, role_name="admin", user_id=1)

    # 3. Test GET /api/replay/{query_id} (Provenance Package)
    res_prov = client.get(f"/api/replay/{q_id}?data_source_id={ds_id}", headers=headers)
    assert res_prov.status_code == 200
    prov_data = res_prov.json()["data"]
    assert prov_data["query_id"] == q_id
    assert prov_data["schema_snapshot_id"] == snapshot.schema_snapshot_id
    assert prov_data["prompt_version"] == "v1.4"
    assert prov_data["model_name"] == "gpt-4o-mini"
    assert prov_data["result_hash"] == init_hash
    assert "drift_report" in prov_data

    # 4. Test POST /api/replay/{query_id} (Reproducible Replay Execution)
    res_replay = client.post(f"/api/replay/{q_id}?role_id={role_id}&data_source_id={ds_id}", headers=headers)
    assert res_replay.status_code == 200
    replay_data = res_replay.json()["data"]
    assert replay_data["is_reproducible"] is True
    assert replay_data["replayed_result_hash"] == init_hash
    assert "✓ Perfect reproducibility" in replay_data["reproducibility_message"]
    assert replay_data["replayed_execution"]["success"] is True
