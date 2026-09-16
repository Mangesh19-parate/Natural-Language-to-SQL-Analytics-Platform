import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from tests.conftest import create_test_auth_headers


def test_pdf_report_export_and_download_api(db_session: Session):
    """
    Test POST /api/report/pdf generates report and GET /api/report/{id}/download streams the file.
    """
    client = TestClient(app)
    headers = create_test_auth_headers(db_session, role_name="admin", user_id=1)
    payload = {
        "title": "Quarterly Revenue Summary",
        "scope": "single_query",
        "user_id": 1,
        "role_name": "Admin",
        "data_source_name": "Commercial DB",
        "queries": [
            {
                "question": "What is the total quarterly sales?",
                "executed_sql": "SELECT SUM(total_amount) AS revenue FROM sales;",
                "status": "success",
                "latency_ms": 15,
                "row_count": 1,
                "reliability_breakdown": {
                    "composite_score": 0.95,
                    "sub_scores": {
                        "schema_grounding": 1.0,
                        "join_confidence": 1.0,
                        "filter_interpretation": 1.0,
                        "execution_validation": 1.0,
                        "result_sanity": 0.75,
                    },
                },
                "columns": ["revenue"],
                "rows": [{"revenue": 245000.0}],
            }
        ],
    }

    # Generate PDF
    res = client.post("/api/report/pdf", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "pdf"
    assert data["status"] == "ready"
    assert data["report_id"] is not None
    assert "download_url" in data

    # Download PDF
    report_id = data["report_id"]
    dl_res = client.get(f"/api/report/{report_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert len(dl_res.content) > 1000


def test_excel_report_export_api(db_session: Session):
    """
    Test POST /api/report/excel generates xlsx and GET /api/report/{id}/download downloads it.
    """
    client = TestClient(app)
    headers = create_test_auth_headers(db_session, role_name="admin", user_id=1)
    payload = {
        "title": "Employee Directory Export",
        "scope": "single_query",
        "user_id": 1,
        "role_name": "Admin",
        "queries": [
            {
                "question": "List all departments",
                "executed_sql": "SELECT department_name FROM departments;",
                "columns": ["department_name"],
                "rows": [{"department_name": "Executive"}, {"department_name": "Finance"}],
            }
        ],
    }

    res = client.post("/api/report/excel", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["format"] == "xlsx"

    report_id = data["report_id"]
    dl_res = client.get(f"/api/report/{report_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert "spreadsheetml" in dl_res.headers["content-type"]
    assert len(dl_res.content) > 500


def test_list_reports_api(db_session: Session):
    """
    Test GET /api/report/list returns user's reports.
    """
    client = TestClient(app)
    headers = create_test_auth_headers(db_session, role_name="admin", user_id=1)
    res = client.get("/api/report/list?user_id=1", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert isinstance(data["reports"], list)
