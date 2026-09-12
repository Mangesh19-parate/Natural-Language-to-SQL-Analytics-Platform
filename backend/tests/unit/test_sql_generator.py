import pytest
from sqlalchemy.orm import Session
from app.models.policy import DataPolicy, SemanticCatalog, DataSource
from app.models.auth import Role
from app.services.sql_generator import SQLGeneratorService


@pytest.fixture
def setup_generator_db(db_session: Session):
    """Sets up data source, roles, semantic catalog, and data policies for generator testing."""
    ds = DataSource(data_source_id=1, name="Enterprise DB", db_type="postgresql", secret_ref="env:TEST_SECRET")
    db_session.add(ds)

    role_admin = Role(role_id=1, role_name="admin")
    role_guest = Role(role_id=99, role_name="guest")
    db_session.add(role_admin)
    db_session.add(role_guest)

    catalog_entries = [
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="employee_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="first_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="salary", semantic_type="currency", sensitivity="HIGH", default_aggregation="AVG"),
    ]
    for c in catalog_entries:
        db_session.add(c)

    # Policy for Role 1 (Admin/Analyst)
    db_session.add(
        DataPolicy(role_id=1, data_source_id=1, table_name="employees", access_level="read", aggregate_allowed=True)
    )
    db_session.commit()
    return db_session


@pytest.mark.asyncio
async def test_sql_generator_proposal_contract(setup_generator_db: Session):
    """
    Task T-14 / REQ-NLSQL-04: SQL Generator produces {sql, rationale} proposal.
    """
    db = setup_generator_db
    generator = SQLGeneratorService()

    response = await generator.generate_sql_proposal(
        db=db,
        question="How many employees are there in the company?",
        role_id=1,
        data_source_id=1,
    )

    assert response.question == "How many employees are there in the company?"
    assert response.proposal is not None
    assert response.proposal.is_proposal is True
    assert "SELECT" in response.proposal.sql.upper()
    assert response.proposal.rationale is not None
    assert response.can_execute is True
    assert response.policy_validation.is_allowed is True
    assert response.policy_validation.status == "APPROVED"


@pytest.mark.asyncio
async def test_sql_generator_unauthorized_proposal_blocked(setup_generator_db: Session):
    """
    Verifies that if an unauthorized role asks a question that generates a query,
    the PolicyEngine immediately flags it as non-executable.
    """
    db = setup_generator_db
    generator = SQLGeneratorService()

    # Role 99 has no policy row for employees
    response = await generator.generate_sql_proposal(
        db=db,
        question="How many employees are there?",
        role_id=99,
        data_source_id=1,
    )

    assert response.can_execute is False
    assert response.policy_validation.is_allowed is False
    assert response.policy_validation.status == "REJECTED"
    assert len(response.rejection_reasons) > 0
