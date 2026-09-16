import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, DataPolicy, SemanticCatalog
from tests.conftest import create_test_auth_headers

client = TestClient(app)


def test_intent_api_classify_and_resolve(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        headers = create_test_auth_headers(db_session, role_name="admin", user_id=1)
        ds = DataSource(name="Intent DB", db_type="postgresql", secret_ref="env:TEST", is_active=True)
        db_session.add(ds)
        db_session.flush()

        from app.models.auth import Role
        admin_role = db_session.query(Role).filter(Role.role_name == "admin").first()

        # Add catalog & policies
        db_session.add_all([
            SemanticCatalog(data_source_id=ds.data_source_id, table_name="orders", column_name="total_amount", data_type="NUMERIC", semantic_type="monetary"),
            SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="revenue", data_type="NUMERIC", semantic_type="monetary"),
            DataPolicy(role_id=admin_role.role_id, data_source_id=ds.data_source_id, table_name="orders", access_level="read"),
            DataPolicy(role_id=admin_role.role_id, data_source_id=ds.data_source_id, table_name="sales", access_level="read"),
        ])
        db_session.flush()

        # Test A: Ambiguous Question Classify
        payload = {
            "question": "What is our total revenue?",
            "data_source_id": ds.data_source_id,
            "role_id": admin_role.role_id
        }
        resp = client.post("/api/intent/classify", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["classification"] == "ambiguous"
        assert len(data["clarification_options"]) >= 2

        # Test B: Resolve Ambiguity
        resolve_payload = {
            "original_question": "What is our total revenue?",
            "selected_option_id": data["clarification_options"][0]["option_id"],
            "clarification_prompt": data["clarification_prompt"],
            "selected_option": data["clarification_options"][0]
        }
        resolve_resp = client.post("/api/intent/resolve", json=resolve_payload, headers=headers)
        assert resolve_resp.status_code == 200
        resolved_text = resolve_resp.json()["data"]
        assert "What is our total revenue?" in resolved_text
        assert data["clarification_options"][0]["column_name"] in resolved_text

        # Test C: Unsupported Question
        unsupp_payload = {
            "question": "What is our Google Ads click-through rate?",
            "data_source_id": ds.data_source_id,
            "role_id": admin_role.role_id
        }
        unsupp_resp = client.post("/api/intent/classify", json=unsupp_payload, headers=headers)
        assert unsupp_resp.status_code == 200
        unsupp_data = unsupp_resp.json()["data"]
        assert unsupp_data["classification"] == "unsupported"
        assert unsupp_data["evidence_gap"] is not None

    finally:
        app.dependency_overrides.clear()
