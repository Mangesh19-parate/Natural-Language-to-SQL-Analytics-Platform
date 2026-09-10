import pytest
from app.services.prompt_builder import CatalogPromptBuilder
from app.schemas.catalog import SemanticCatalogResponse, TableCatalogItem, ColumnCatalogItem


def test_catalog_prompt_builder_consumes_catalog_only():
    """
    Task T-09 Acceptance Criteria:
    Prompt payload inspection shows zero raw-schema fields and zero unapproved tables.
    """
    catalog = SemanticCatalogResponse(
        data_source_id=1,
        data_source_name="Primary DB",
        role_id=2,
        role_name="sales_analyst",
        tables=[
            TableCatalogItem(
                table_name="products",
                description="Business entity products",
                columns=[
                    ColumnCatalogItem(
                        column_name="product_id",
                        data_type="INTEGER",
                        semantic_type="identifier",
                        sensitivity="NONE",
                        default_aggregation="COUNT"
                    ),
                    ColumnCatalogItem(
                        column_name="category",
                        data_type="VARCHAR(100)",
                        semantic_type="categorical",
                        sensitivity="NONE",
                        sanitized_examples=["Electronics", "Software"]
                    ),
                    ColumnCatalogItem(
                        column_name="price",
                        data_type="NUMERIC(12,2)",
                        semantic_type="monetary",
                        sensitivity="NONE",
                        default_aggregation="AVG"
                    )
                ],
                primary_keys=["product_id"],
                foreign_keys=[]
            )
        ]
    )

    system_prompt = CatalogPromptBuilder.build_system_prompt(catalog, dialect="PostgreSQL")
    user_prompt = CatalogPromptBuilder.build_user_prompt("What is the average price by category?")

    # 1. Assert authorized tables and columns appear
    assert "Table: products" in system_prompt
    assert "category (VARCHAR(100)) [type: categorical, examples: [\"Electronics\", \"Software\"]]" in system_prompt
    assert "price (NUMERIC(12,2)) [type: monetary, default_agg: AVG]" in system_prompt

    # 2. Assert unauthorized/unapproved tables (e.g. employees, customers) NEVER appear
    assert "Table: employees" not in system_prompt
    assert "Table: customers" not in system_prompt
    assert "salary" not in system_prompt

    # 3. Assert prompt structure
    assert "User Question: What is the average price by category?" in user_prompt
