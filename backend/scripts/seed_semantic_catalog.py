import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal, business_engine
from app.models.policy import DataSource, SemanticCatalog
from app.services.value_grounding import ValueGroundingService


def seed_semantic_catalog():
    """
    Seeds the Semantic Catalog with typed, sensitivity-classified schema metadata (Task T-05 & T-07).
    Extracts sanitized categorical examples for low/none sensitivity columns.
    """
    print("--- [T-05] Seeding Semantic Catalog ---")
    db: Session = SessionLocal()

    try:
        # 1. Fetch default DataSource
        ds = db.query(DataSource).first()
        if not ds:
            print("Error: No data source found. Run init_metadata_db.py first.")
            return

        # 2. Schema classification metadata definitions
        catalog_definitions = [
            # departments
            {"table": "departments", "column": "department_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Unique identifier for department"},
            {"table": "departments", "column": "department_name", "type": "VARCHAR(100)", "sem_type": "categorical", "sens": "NONE", "agg": None, "desc": "Name of the operational business department"},

            # employees
            {"table": "employees", "column": "employee_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Unique identifier for company employee"},
            {"table": "employees", "column": "first_name", "type": "VARCHAR(100)", "sem_type": "text", "sens": "MEDIUM", "agg": None, "desc": "First name of employee"},
            {"table": "employees", "column": "last_name", "type": "VARCHAR(100)", "sem_type": "text", "sens": "MEDIUM", "agg": None, "desc": "Last name of employee"},
            {"table": "employees", "column": "department_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Foreign key reference to departments table"},
            {"table": "employees", "column": "salary", "type": "NUMERIC(12,2)", "sem_type": "monetary", "sens": "HIGH", "agg": "AVG", "desc": "Annual employee compensation in USD"},
            {"table": "employees", "column": "hire_date", "type": "DATE", "sem_type": "temporal", "sens": "NONE", "agg": None, "desc": "Date when employee was hired"},

            # customers
            {"table": "customers", "column": "customer_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Unique identifier for customer account"},
            {"table": "customers", "column": "customer_name", "type": "VARCHAR(150)", "sem_type": "identifier", "sens": "MEDIUM", "agg": None, "desc": "Corporate or individual client name"},
            {"table": "customers", "column": "city", "type": "VARCHAR(100)", "sem_type": "categorical", "sens": "LOW", "agg": None, "desc": "Primary city location of customer headquarters or residence"},
            {"table": "customers", "column": "total_spent", "type": "NUMERIC(12,2)", "sem_type": "monetary", "sens": "NONE", "agg": "SUM", "desc": "Cumulative total dollar spend across all orders"},

            # products
            {"table": "products", "column": "product_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Unique product SKU identifier"},
            {"table": "products", "column": "product_name", "type": "VARCHAR(150)", "sem_type": "text", "sens": "NONE", "agg": None, "desc": "Commercial name of product item"},
            {"table": "products", "column": "category", "type": "VARCHAR(100)", "sem_type": "categorical", "sens": "NONE", "agg": None, "desc": "Market category grouping"},
            {"table": "products", "column": "price", "type": "NUMERIC(12,2)", "sem_type": "monetary", "sens": "NONE", "agg": "AVG", "desc": "Unit catalog selling price in USD"},

            # orders
            {"table": "orders", "column": "order_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Unique purchase order identifier"},
            {"table": "orders", "column": "customer_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Foreign key reference to customers table"},
            {"table": "orders", "column": "order_date", "type": "DATE", "sem_type": "temporal", "sens": "NONE", "agg": None, "desc": "Date when purchase order was placed"},
            {"table": "orders", "column": "total_amount", "type": "NUMERIC(12,2)", "sem_type": "monetary", "sens": "NONE", "agg": "SUM", "desc": "Gross total invoice value for order"},

            # sales
            {"table": "sales", "column": "sale_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Unique sales line item identifier"},
            {"table": "sales", "column": "order_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Foreign key reference to orders table"},
            {"table": "sales", "column": "product_id", "type": "INTEGER", "sem_type": "identifier", "sens": "NONE", "agg": "COUNT", "desc": "Foreign key reference to products table"},
            {"table": "sales", "column": "quantity", "type": "INTEGER", "sem_type": "metric", "sens": "NONE", "agg": "SUM", "desc": "Units sold in transaction"},
            {"table": "sales", "column": "revenue", "type": "NUMERIC(12,2)", "sem_type": "monetary", "sens": "NONE", "agg": "SUM", "desc": "Net sales revenue generated in USD"},
        ]

        seeded_count = 0
        for item in catalog_definitions:
            # Check for existing catalog entry
            entry = (
                db.query(SemanticCatalog)
                .filter(
                    SemanticCatalog.data_source_id == ds.data_source_id,
                    SemanticCatalog.table_name == item["table"],
                    SemanticCatalog.column_name == item["column"],
                )
                .first()
            )

            # Ground sanitized categorical examples safely (Rule R2.5)
            examples = ValueGroundingService.extract_sanitized_examples(
                engine=business_engine,
                table_name=item["table"],
                column_name=item["column"],
                semantic_type=item["sem_type"],
                sensitivity=item["sens"],
                max_examples=5
            )

            if not entry:
                entry = SemanticCatalog(
                    data_source_id=ds.data_source_id,
                    table_name=item["table"],
                    column_name=item["column"],
                    data_type=item["type"],
                    semantic_type=item["sem_type"],
                    sensitivity=item["sens"],
                    default_aggregation=item["agg"],
                    sanitized_examples=examples,
                    description=item["desc"]
                )
                db.add(entry)
            else:
                entry.data_type = item["type"]
                entry.semantic_type = item["sem_type"]
                entry.sensitivity = item["sens"]
                entry.default_aggregation = item["agg"]
                entry.sanitized_examples = examples
                entry.description = item["desc"]

            seeded_count += 1

        db.commit()
        print(f"[OK] Seeded/Updated {seeded_count} Semantic Catalog column definitions.")
        print("--- [T-05] Semantic Catalog Seeding Complete ---")

    except Exception as e:
        db.rollback()
        print(f"Error seeding semantic catalog: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_semantic_catalog()
