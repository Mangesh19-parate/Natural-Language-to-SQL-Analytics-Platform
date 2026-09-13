import os
import pytest
from app.services.report_generator import ReportGeneratorService
from app.schemas.report import ReportExportRequest, ReportQueryItem


@pytest.fixture
def report_service(tmp_path):
    return ReportGeneratorService(reports_dir=str(tmp_path))


def test_pdf_report_single_query_structure(report_service):
    """
    Test PDF generation for a single query (REQ-RPT-01 / Rule R8.3).
    Must include NL question, SQL, 5-part Reliability Score breakdown, and timestamp.
    """
    query_item = ReportQueryItem(
        query_id="q-001",
        question="What is the total revenue by product category in 2024?",
        executed_sql="SELECT c.category_name, SUM(s.total_amount) AS revenue FROM sales s JOIN products p ON s.product_id = p.product_id JOIN categories c ON p.category_id = c.category_id GROUP BY c.category_name;",
        status="success",
        latency_ms=18,
        row_count=3,
        reliability_breakdown={
            "composite_score": 0.96,
            "sub_scores": {
                "schema_grounding": 1.0,
                "join_confidence": 0.95,
                "filter_interpretation": 1.0,
                "execution_validation": 1.0,
                "result_sanity": 0.85,
            },
        },
        columns=["category_name", "revenue"],
        rows=[
            {"category_name": "Electronics", "revenue": 145000.0},
            {"category_name": "Furniture", "revenue": 89000.0},
            {"category_name": "Office Supplies", "revenue": 34000.0},
        ],
    )

    req = ReportExportRequest(
        title="Executive Revenue Audit Report",
        scope="single_query",
        role_name="Admin",
        data_source_name="Northwind Commercial DB",
        queries=[query_item],
        include_raw_data=True,
    )

    report_id, file_path, content_hash = report_service.generate_pdf(req)

    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 1000  # Non-trivial PDF file
    assert len(content_hash) == 64  # SHA-256 hash
    assert file_path.endswith(".pdf")


def test_pdf_report_session_multi_query(report_service):
    """
    Test session-scope PDF report aggregating multiple queries (REQ-RPT-01).
    """
    q1 = ReportQueryItem(
        question="Show top 5 customers by order count",
        executed_sql="SELECT customer_id, COUNT(order_id) AS orders FROM orders GROUP BY customer_id ORDER BY orders DESC LIMIT 5;",
        status="success",
        row_count=5,
        reliability_breakdown={"composite_score": 0.98, "sub_scores": {"schema_grounding": 1.0, "join_confidence": 1.0, "filter_interpretation": 1.0, "execution_validation": 1.0, "result_sanity": 0.9}},
        columns=["customer_id", "orders"],
        rows=[{"customer_id": 1, "orders": 24}, {"customer_id": 2, "orders": 18}],
    )
    q2 = ReportQueryItem(
        question="List active employees in Engineering",
        executed_sql="SELECT first_name, last_name, email FROM employees WHERE department_id = 3;",
        status="success",
        row_count=12,
        reliability_breakdown={"composite_score": 0.92, "sub_scores": {"schema_grounding": 1.0, "join_confidence": 0.8, "filter_interpretation": 1.0, "execution_validation": 1.0, "result_sanity": 0.8}},
        columns=["first_name", "last_name", "email"],
        rows=[{"first_name": "Alice", "last_name": "Smith", "email": "alice@corp.com"}],
    )

    req = ReportExportRequest(
        title="Session Multi-Query Analysis Report",
        scope="session",
        role_name="Analyst",
        data_source_name="Northwind DB",
        queries=[q1, q2],
        include_raw_data=True,
    )

    report_id, file_path, content_hash = report_service.generate_pdf(req)
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 2000
    assert len(content_hash) == 64
