import pytest
from app.services.value_grounding import ValueGroundingService
from app.models.business import Department
from sqlalchemy.orm import Session


def test_high_medium_sensitivity_never_sampled(test_engine):
    """
    Task T-07 & Rule R2.5 Acceptance Criteria:
    Zero raw values from HIGH/MEDIUM sensitivity columns appear in generated examples.
    """
    # 1. HIGH Sensitivity (Salary) -> Must return None
    salary_examples = ValueGroundingService.extract_sanitized_examples(
        engine=test_engine,
        table_name="employees",
        column_name="salary",
        semantic_type="monetary",
        sensitivity="HIGH"
    )
    assert salary_examples is None, "Security violation: HIGH sensitivity column was sampled!"

    # 2. MEDIUM Sensitivity (Customer Name / PII) -> Must return None
    name_examples = ValueGroundingService.extract_sanitized_examples(
        engine=test_engine,
        table_name="customers",
        column_name="customer_name",
        semantic_type="identifier",
        sensitivity="MEDIUM"
    )
    assert name_examples is None, "Security violation: MEDIUM sensitivity column was sampled!"


def test_categorical_low_none_sensitivity_sampled(test_engine, db_session: Session):
    """
    Verifies that low/none sensitivity categorical columns produce clean sanitized distinct lists.
    """
    # Insert test department data
    db_session.add_all([
        Department(department_name="Engineering"),
        Department(department_name="Sales"),
        Department(department_name="Marketing"),
    ])
    db_session.flush()

    dept_examples = ValueGroundingService.extract_sanitized_examples(
        engine=test_engine,
        table_name="departments",
        column_name="department_name",
        semantic_type="categorical",
        sensitivity="NONE",
        max_examples=5
    )

    assert dept_examples is not None
    assert isinstance(dept_examples, list)
    assert len(dept_examples) > 0
    assert "Engineering" in dept_examples
