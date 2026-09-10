import pytest
from app.services.query_classifier import QueryClassifierService
from app.schemas.catalog import SemanticCatalogResponse, TableCatalogItem, ColumnCatalogItem
from app.schemas.intent import IntentClassification


@pytest.fixture
def full_catalog():
    return SemanticCatalogResponse(
        data_source_id=1,
        data_source_name="Enterprise DB",
        role_id=1,
        role_name="admin",
        tables=[
            TableCatalogItem(table_name="customers", columns=[ColumnCatalogItem(column_name="customer_id"), ColumnCatalogItem(column_name="total_spent")]),
            TableCatalogItem(table_name="products", columns=[ColumnCatalogItem(column_name="product_id"), ColumnCatalogItem(column_name="price")]),
            TableCatalogItem(table_name="orders", columns=[ColumnCatalogItem(column_name="order_id"), ColumnCatalogItem(column_name="order_date"), ColumnCatalogItem(column_name="total_amount")]),
            TableCatalogItem(table_name="sales", columns=[ColumnCatalogItem(column_name="sale_id"), ColumnCatalogItem(column_name="revenue")]),
        ]
    )


def test_ambiguity_detection_benchmark(full_catalog):
    """
    Task T-12 Acceptance Criteria:
    >=80% of a 20-question ambiguous benchmark set correctly triggers clarification with real column options.
    """
    ambiguous_test_set = [
        # Revenue ambiguity (orders.total_amount vs sales.revenue)
        "Show our total revenue",
        "What was our gross revenue last month?",
        "List top product categories by sales revenue",
        "Show the highest revenue month",
        "What is our overall company turnover?",
        "Display monthly sales revenue figures",
        "Calculate annual revenue for 2023",
        "Which division brought the most sales amount?",

        # Customer spending ambiguity (customers.total_spent vs orders.total_amount)
        "Who is our top customer?",
        "Find the biggest customer by spending",
        "Show customer spend breakdown",
        "Rank best customer accounts",
        "Who spent the most money this year?",
        "List high value customer purchases",

        # Temporal ambiguity ("recent", "latest")
        "Show all recent orders",
        "List recently placed invoices",
        "What are our latest sales transactions?",
        "Find newest orders in the database",
        "Show sales trends from past few weeks",

        # Product value ambiguity (products.price vs sales.revenue)
        "What is our most expensive product?",
    ]

    assert len(ambiguous_test_set) == 20, "Test set must have exactly 20 ambiguous questions"

    ambiguity_detected_count = 0
    for q in ambiguous_test_set:
        result = QueryClassifierService.classify_question(q, full_catalog)
        if result.classification == IntentClassification.AMBIGUOUS:
            assert len(result.clarification_options) >= 2, f"Expected >=2 options for '{q}'"
            assert result.clarification_prompt is not None
            ambiguity_detected_count += 1

    accuracy_pct = (ambiguity_detected_count / 20.0) * 100.0
    print(f"\nAmbiguity Benchmark Accuracy: {accuracy_pct}% ({ambiguity_detected_count}/20 caught)")
    assert accuracy_pct >= 80.0, f"Ambiguity catch rate {accuracy_pct}% was below 80% threshold!"


def test_ambiguity_resolution():
    """
    Verifies that selecting an option cleanly resolves the question.
    """
    from app.schemas.intent import ClarificationOption
    selected_opt = ClarificationOption(
        option_id="sales_revenue",
        label="Net Item Revenue (sales.revenue)",
        table_name="sales",
        column_name="revenue",
        description="Calculates revenue based on sales table."
    )
    resolved = QueryClassifierService.resolve_ambiguity("Show total revenue", selected_opt)
    assert "sales.revenue" in resolved
    assert "Show total revenue" in resolved
