import pytest
from app.services.intent_analyzer import IntentAnalyzerService
from app.services.query_classifier import QueryClassifierService
from app.schemas.catalog import SemanticCatalogResponse, TableCatalogItem, ColumnCatalogItem
from app.schemas.intent import IntentClassification


@pytest.fixture
def full_admin_catalog():
    return SemanticCatalogResponse(
        data_source_id=1,
        data_source_name="Enterprise DB",
        role_id=1,
        role_name="admin",
        tables=[
            TableCatalogItem(
                table_name="departments",
                columns=[ColumnCatalogItem(column_name="department_id", data_type="INT"), ColumnCatalogItem(column_name="department_name", data_type="VARCHAR")]
            ),
            TableCatalogItem(
                table_name="employees",
                columns=[ColumnCatalogItem(column_name="employee_id", data_type="INT"), ColumnCatalogItem(column_name="salary", data_type="NUMERIC", sensitivity="HIGH")]
            ),
            TableCatalogItem(
                table_name="customers",
                columns=[ColumnCatalogItem(column_name="customer_id", data_type="INT"), ColumnCatalogItem(column_name="city", data_type="VARCHAR")]
            ),
            TableCatalogItem(
                table_name="products",
                columns=[ColumnCatalogItem(column_name="product_id", data_type="INT"), ColumnCatalogItem(column_name="price", data_type="NUMERIC")]
            ),
            TableCatalogItem(
                table_name="orders",
                columns=[ColumnCatalogItem(column_name="order_id", data_type="INT"), ColumnCatalogItem(column_name="total_amount", data_type="NUMERIC")]
            ),
            TableCatalogItem(
                table_name="sales",
                columns=[ColumnCatalogItem(column_name="sale_id", data_type="INT"), ColumnCatalogItem(column_name="revenue", data_type="NUMERIC")]
            ),
        ]
    )


@pytest.fixture
def restricted_analyst_catalog():
    # Only products and orders, no employees or salary access
    return SemanticCatalogResponse(
        data_source_id=1,
        data_source_name="Enterprise DB",
        role_id=2,
        role_name="analyst",
        tables=[
            TableCatalogItem(
                table_name="products",
                columns=[ColumnCatalogItem(column_name="product_id", data_type="INT"), ColumnCatalogItem(column_name="price", data_type="NUMERIC")]
            ),
            TableCatalogItem(
                table_name="orders",
                columns=[ColumnCatalogItem(column_name="order_id", data_type="INT"), ColumnCatalogItem(column_name="total_amount", data_type="NUMERIC")]
            ),
        ]
    )


def test_unsupported_detection_10_cases(full_admin_catalog):
    """
    Task T-10 Acceptance Criteria:
    10/10 seeded 'impossible' questions correctly refused with evidence-gap message.
    """
    impossible_questions = [
        "What is the average shipping carrier delivery delay time?",
        "Show me customer churn prediction scores for next quarter",
        "What was the Google Ads click-through rate for our spring campaign?",
        "List employee performance review scores from last year",
        "What is our competitor market share compared to Apple?",
        "How does warehouse shelf temperature correlate with product returns?",
        "Show average customer support ticket response time in Zendesk",
        "What is the current server latency and cpu utilization in AWS?",
        "Who is the current President of France?",
        "What was the rainfall and weather in New York yesterday?"
    ]

    refused_count = 0
    for q in impossible_questions:
        result = QueryClassifierService.classify_question(q, full_admin_catalog)
        if result.classification == IntentClassification.UNSUPPORTED and result.evidence_gap:
            refused_count += 1

    assert refused_count == 10, f"Expected 10/10 impossible questions refused, got {refused_count}/10"


def test_unauthorized_precheck(restricted_analyst_catalog):
    """
    Task T-11 Acceptance Criteria:
    Sensitive/unpermitted queries refused before SQL generation.
    """
    # 1. Analyst attempting to access restricted table 'employees'
    q1 = "How many employees are currently active in our workforce?"
    res1 = QueryClassifierService.classify_question(q1, restricted_analyst_catalog)
    assert res1.classification == IntentClassification.UNAUTHORIZED
    assert "employees" in res1.reasoning.lower()

    # 2. Analyst attempting to query sensitive salary data
    q2 = "Show the average employee salary by department"
    res2 = QueryClassifierService.classify_question(q2, restricted_analyst_catalog)
    assert res2.classification == IntentClassification.UNAUTHORIZED

    # 3. Unconfigured Viewer with 0 accessible tables
    empty_catalog = SemanticCatalogResponse(data_source_id=1, data_source_name="DB", tables=[])
    res3 = QueryClassifierService.classify_question("Show all products", empty_catalog)
    assert res3.classification == IntentClassification.UNAUTHORIZED


def test_answerable_question(full_admin_catalog):
    """
    Verifies that a clear, unambiguous, authorized question is classified as Answerable.
    """
    q = "List all products in the catalog with their price"
    res = QueryClassifierService.classify_question(q, full_admin_catalog)
    assert res.classification == IntentClassification.ANSWERABLE
    assert res.confidence == 1.0
    assert res.resolved_question == q
