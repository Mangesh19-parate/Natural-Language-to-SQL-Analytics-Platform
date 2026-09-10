import pytest
from app.services.schema_introspector import SchemaIntrospectorService


def test_schema_introspection(test_engine):
    """
    Task T-06 Acceptance Criteria:
    Schema introspection service returns tables, columns, PKs, and FKs for a given database.
    """
    tables = SchemaIntrospectorService.introspect_database(test_engine)
    table_map = {t.table_name: t for t in tables}

    # Verify all 6 business domain tables exist
    expected_tables = ["departments", "employees", "customers", "products", "orders", "sales"]
    for expected in expected_tables:
        assert expected in table_map, f"Missing table: {expected}"

    # Verify columns and PK on employees
    emp_table = table_map["employees"]
    emp_cols = {c.name: c for c in emp_table.columns}
    assert "employee_id" in emp_cols
    assert "salary" in emp_cols
    assert "department_id" in emp_cols
    assert "employee_id" in emp_table.primary_keys

    # Verify foreign key from employees to departments
    dept_fk = next((fk for fk in emp_table.foreign_keys if fk.referred_table == "departments"), None)
    assert dept_fk is not None, "Foreign key from employees to departments not detected"
    assert "department_id" in dept_fk.constrained_columns

    # Verify foreign key from orders to customers
    orders_table = table_map["orders"]
    cust_fk = next((fk for fk in orders_table.foreign_keys if fk.referred_table == "customers"), None)
    assert cust_fk is not None, "Foreign key from orders to customers not detected"
    assert "customer_id" in cust_fk.constrained_columns
