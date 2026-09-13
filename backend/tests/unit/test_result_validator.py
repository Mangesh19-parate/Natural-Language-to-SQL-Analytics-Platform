import pytest
from sqlalchemy.orm import Session
from app.schemas.query import ResultValidationType
from app.services.result_validator import ResultValidatorService
from app.models.trust import ResultValidation
from app.models.session import QueryHistory
import uuid


def test_zero_row_detection():
    """
    Task T-28: Test detection of zero rows returned from execution.
    """
    sql = "SELECT product_id, product_name FROM products WHERE unit_price > 99999;"
    columns = ["product_id", "product_name"]
    rows = []
    row_count = 0

    report = ResultValidatorService.validate_results(
        db=None,
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=row_count,
    )

    assert report.has_anomalies is True
    assert report.findings_count >= 1
    finding = next(f for f in report.findings if f.check_type == ResultValidationType.ZERO_ROW)
    assert finding.observed_value == "0 rows"
    assert finding.severity == "warning"


def test_null_explosion_detection():
    """
    Task T-28: Test detection of NULL-explosion (>=50% NULLs in projected column).
    """
    sql = "SELECT customer_id, phone_number FROM customers;"
    columns = ["customer_id", "phone_number"]
    # 8 out of 10 rows have NULL phone_number (80% NULLs)
    rows = [
        {"customer_id": i, "phone_number": "555-0100" if i < 2 else None}
        for i in range(10)
    ]
    row_count = len(rows)

    report = ResultValidatorService.validate_results(
        db=None,
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=row_count,
    )

    assert report.has_anomalies is True
    finding = next(f for f in report.findings if f.check_type == ResultValidationType.NULL_EXPLOSION)
    assert "phone_number" in finding.message
    assert "80% NULLs" in finding.observed_value


def test_cardinality_outlier_detection():
    """
    Task T-28: Test detection of extreme cardinality outputs (>=5000 rows).
    """
    sql = "SELECT * FROM sales;"
    columns = ["sale_id", "amount"]
    rows = [{"sale_id": i, "amount": 100} for i in range(5500)]
    row_count = 5500

    report = ResultValidatorService.validate_results(
        db=None,
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=row_count,
    )

    assert report.has_anomalies is True
    finding = next(f for f in report.findings if f.check_type == ResultValidationType.CARDINALITY_OUTLIER)
    assert "5500 rows" in finding.observed_value


def test_result_validation_persistence(db_session: Session):
    """
    Task T-28: Verifies that result anomalies are persisted to result_validation table.
    """
    q_id = str(uuid.uuid4())
    qh = QueryHistory(
        query_id=q_id,
        user_id=1,
        nl_question="Show customer phone numbers",
        initial_sql="SELECT customer_id, phone_number FROM customers;",
        status="success",
    )
    db_session.add(qh)
    db_session.commit()

    sql = "SELECT customer_id, phone_number FROM customers;"
    columns = ["customer_id", "phone_number"]
    rows = [{"customer_id": i, "phone_number": None} for i in range(10)]
    row_count = 10

    report = ResultValidatorService.validate_results(
        db=db_session,
        sql=sql,
        columns=columns,
        rows=rows,
        row_count=row_count,
        query_id=q_id,
    )

    assert report.has_anomalies is True
    db_records = db_session.query(ResultValidation).filter(ResultValidation.query_id == q_id).all()
    assert len(db_records) >= 1
    assert db_records[0].check_type == ResultValidationType.NULL_EXPLOSION.value
