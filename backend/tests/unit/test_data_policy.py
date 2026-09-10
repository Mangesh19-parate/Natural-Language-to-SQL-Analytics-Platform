import pytest
from sqlalchemy.orm import Session
from app.models.auth import Role
from app.models.policy import DataSource, DataPolicy
from app.services.policy_engine import PolicyLookupService


def test_default_deny(db_session: Session):
    """
    T-04 Acceptance Criteria:
    Query for a role with no policy row returns ZERO tables, not all tables (Fail-Closed Deny-by-Default).
    """
    # 1. Setup Role and DataSource
    viewer_role = Role(role_name="unconfigured_viewer")
    db_session.add(viewer_role)
    
    ds = DataSource(
        name="Test DB",
        db_type="postgresql",
        secret_ref="env:TEST",
        is_active=True
    )
    db_session.add(ds)
    db_session.flush()

    # 2. Call PolicyLookupService with no data_policy rows created
    policy = PolicyLookupService.get_effective_policy(db_session, viewer_role.role_id, ds.data_source_id)

    # 3. Assert zero tables accessible
    assert len(policy.accessible_tables) == 0, "Security violation: unconfigured role was granted table access!"
    assert PolicyLookupService.is_table_accessible(db_session, viewer_role.role_id, ds.data_source_id, "employees") is False
    assert PolicyLookupService.is_column_accessible(db_session, viewer_role.role_id, ds.data_source_id, "employees", "salary") is False


def test_explicit_table_grant(db_session: Session):
    """
    Verifies that explicit table read grants allow access to all columns of that table by default.
    """
    analyst_role = Role(role_name="analyst_role")
    ds = DataSource(name="Analytics DB", db_type="postgresql", secret_ref="env:TEST", is_active=True)
    db_session.add_all([analyst_role, ds])
    db_session.flush()

    # Explicitly grant read on 'products' table
    prod_policy = DataPolicy(
        role_id=analyst_role.role_id,
        data_source_id=ds.data_source_id,
        table_name="products",
        column_name=None,
        access_level="read"
    )
    db_session.add(prod_policy)
    db_session.flush()

    assert PolicyLookupService.is_table_accessible(db_session, analyst_role.role_id, ds.data_source_id, "products") is True
    assert PolicyLookupService.is_column_accessible(db_session, analyst_role.role_id, ds.data_source_id, "products", "price") is True
    # Still deny access to ungranted 'employees' table
    assert PolicyLookupService.is_table_accessible(db_session, analyst_role.role_id, ds.data_source_id, "employees") is False


def test_column_level_denial(db_session: Session):
    """
    Verifies that explicit column-level denial overrides table-level read access.
    """
    analyst_role = Role(role_name="limited_analyst")
    ds = DataSource(name="Finance DB", db_type="postgresql", secret_ref="env:TEST", is_active=True)
    db_session.add_all([analyst_role, ds])
    db_session.flush()

    # Grant read on table 'employees'
    db_session.add(DataPolicy(
        role_id=analyst_role.role_id,
        data_source_id=ds.data_source_id,
        table_name="employees",
        column_name=None,
        access_level="read"
    ))
    # Explicitly deny column 'salary'
    db_session.add(DataPolicy(
        role_id=analyst_role.role_id,
        data_source_id=ds.data_source_id,
        table_name="employees",
        column_name="salary",
        access_level="denied"
    ))
    db_session.flush()

    assert PolicyLookupService.is_table_accessible(db_session, analyst_role.role_id, ds.data_source_id, "employees") is True
    assert PolicyLookupService.is_column_accessible(db_session, analyst_role.role_id, ds.data_source_id, "employees", "first_name") is True
    assert PolicyLookupService.is_column_accessible(db_session, analyst_role.role_id, ds.data_source_id, "employees", "salary") is False


def test_aggregate_guard(db_session: Session):
    """
    Verifies Rule R1.4 / SEC-3: AVG/SUM/MAX/MIN cannot be executed on sensitive column without aggregate_allowed.
    """
    analyst_role = Role(role_name="stats_analyst")
    ds = DataSource(name="HR DB", db_type="postgresql", secret_ref="env:TEST", is_active=True)
    db_session.add_all([analyst_role, ds])
    db_session.flush()

    # Column salary with aggregate_allowed = False
    db_session.add(DataPolicy(
        role_id=analyst_role.role_id,
        data_source_id=ds.data_source_id,
        table_name="employees",
        column_name="salary",
        access_level="read_aggregate_only",
        aggregate_allowed=False
    ))
    # Column bonus with aggregate_allowed = True
    db_session.add(DataPolicy(
        role_id=analyst_role.role_id,
        data_source_id=ds.data_source_id,
        table_name="employees",
        column_name="bonus",
        access_level="read_aggregate_only",
        aggregate_allowed=True
    ))
    db_session.flush()

    assert PolicyLookupService.is_aggregate_allowed(db_session, analyst_role.role_id, ds.data_source_id, "employees", "salary") is False
    assert PolicyLookupService.is_aggregate_allowed(db_session, analyst_role.role_id, ds.data_source_id, "employees", "bonus") is True


def test_row_filter_retrieval(db_session: Session):
    """
    Verifies that row_filter_sql clause is correctly preserved and retrieved for injection.
    """
    role = Role(role_name="regional_manager")
    ds = DataSource(name="Sales DB", db_type="postgresql", secret_ref="env:TEST", is_active=True)
    db_session.add_all([role, ds])
    db_session.flush()

    db_session.add(DataPolicy(
        role_id=role.role_id,
        data_source_id=ds.data_source_id,
        table_name="orders",
        column_name=None,
        access_level="read",
        row_filter_sql="region = 'EMEA'"
    ))
    db_session.flush()

    filter_sql = PolicyLookupService.get_row_filter(db_session, role.role_id, ds.data_source_id, "orders")
    assert filter_sql == "region = 'EMEA'"
