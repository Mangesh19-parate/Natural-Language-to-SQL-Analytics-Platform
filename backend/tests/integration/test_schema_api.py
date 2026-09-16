import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.auth import Role, User
from app.models.policy import DataSource, DataPolicy, SemanticCatalog
from tests.conftest import create_test_auth_headers

client = TestClient(app)


def test_schema_api_policy_filtering(db_session: Session):
    """
    Task T-08 Acceptance Criteria:
    GET /api/schema returns catalog view filtered strictly by the caller's role via PolicyLookupService.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        # 1. Create Roles and Data Source
        viewer_role = Role(role_name="test_viewer")
        analyst_role = Role(role_name="test_analyst")
        ds = DataSource(name="API Test DB", db_type="postgresql", secret_ref="env:TEST", is_active=True)
        db_session.add_all([viewer_role, analyst_role, ds])
        db_session.flush()

        viewer_headers = create_test_auth_headers(db_session, role_name="test_viewer", user_id=31, email="viewer_schema@test.com")
        analyst_headers = create_test_auth_headers(db_session, role_name="test_analyst", user_id=32, email="analyst_schema@test.com")

        # 2. Add Semantic Catalog entries
        db_session.add_all([
            SemanticCatalog(
                data_source_id=ds.data_source_id,
                table_name="products",
                column_name="product_name",
                data_type="VARCHAR(150)",
                semantic_type="text",
                sensitivity="NONE"
            ),
            SemanticCatalog(
                data_source_id=ds.data_source_id,
                table_name="employees",
                column_name="salary",
                data_type="NUMERIC(12,2)",
                semantic_type="monetary",
                sensitivity="HIGH"
            ),
        ])

        # 3. Grant Analyst access only to 'products' table
        db_session.add(DataPolicy(
            role_id=analyst_role.role_id,
            data_source_id=ds.data_source_id,
            table_name="products",
            column_name=None,
            access_level="read"
        ))
        db_session.flush()

        # Case A: Unconfigured Viewer Role -> 0 tables returned (Fail-Closed Deny-by-Default)
        viewer_resp = client.get(f"/api/schema?data_source_id={ds.data_source_id}", headers=viewer_headers)
        assert viewer_resp.status_code == 200
        viewer_data = viewer_resp.json()["data"]
        assert len(viewer_data["tables"]) == 0, "Security violation: Viewer got unpermitted tables"

        # Case B: Analyst Role -> Only 'products' table returned, 'employees' is excluded
        analyst_resp = client.get(f"/api/schema?data_source_id={ds.data_source_id}", headers=analyst_headers)
        assert analyst_resp.status_code == 200
        analyst_data = analyst_resp.json()["data"]
        assert len(analyst_data["tables"]) == 1
        assert analyst_data["tables"][0]["table_name"] == "products"
        table_names = [t["table_name"] for t in analyst_data["tables"]]
        assert "employees" not in table_names
    finally:
        app.dependency_overrides.clear()

