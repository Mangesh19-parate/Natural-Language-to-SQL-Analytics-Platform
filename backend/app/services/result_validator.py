from typing import Optional, List, Dict, Any, Set
from sqlalchemy.orm import Session
import sqlglot
from sqlglot import exp

from app.schemas.query import (
    ResultValidationType,
    ResultValidationFinding,
    ResultValidationReport,
)
from app.models.trust import ResultValidation


class ResultValidatorService:
    """
    Result Sanity Validator (REQ-RESULT-01, Task T-28).
    
    Performs deterministic post-execution sanity checks on output datasets:
      1. zero_row: Flags empty results for queries.
      2. cardinality_outlier: Detects excessive or maxed-out row counts.
      3. null_explosion: Detects columns with >=50% or 100% NULL values.
      4. join_multiplication: Detects unexpected row inflation from join fans.
    """

    @classmethod
    def validate_results(
        cls,
        db: Optional[Session],
        sql: str,
        columns: List[str],
        rows: List[Dict[str, Any]],
        row_count: int,
        query_id: Optional[str] = None,
    ) -> ResultValidationReport:
        findings: List[ResultValidationFinding] = []

        # 1. Zero-Row Check
        if row_count == 0:
            findings.append(
                ResultValidationFinding(
                    check_type=ResultValidationType.ZERO_ROW,
                    severity="warning",
                    expected_range=">0 rows",
                    observed_value="0 rows",
                    message="Query execution returned 0 rows. Verify filter criteria and join predicate matches.",
                )
            )

        # 2. Cardinality Outlier Check
        if row_count >= 5000:
            severity = "critical" if row_count >= 10000 else "warning"
            findings.append(
                ResultValidationFinding(
                    check_type=ResultValidationType.CARDINALITY_OUTLIER,
                    severity=severity,
                    expected_range="<5000 rows",
                    observed_value=f"{row_count} rows",
                    message=(
                        f"High output cardinality ({row_count} rows). "
                        "Query may lack necessary filtering, aggregation, or pagination."
                    ),
                )
            )

        if row_count > 0 and rows:
            # 3. NULL Explosion Check
            for col in columns:
                null_count = sum(1 for r in rows if r.get(col) is None)
                null_ratio = null_count / row_count
                if null_ratio >= 0.5:
                    severity = "critical" if null_ratio == 1.0 else "warning"
                    findings.append(
                        ResultValidationFinding(
                            check_type=ResultValidationType.NULL_EXPLOSION,
                            severity=severity,
                            expected_range="<50% NULLs",
                            observed_value=f"{null_ratio * 100:.0f}% NULLs ({null_count}/{row_count})",
                            message=(
                                f"Column '{col}' exhibits a NULL-explosion ({null_ratio * 100:.0f}% NULLs). "
                                "Possible mismatched LEFT JOIN or unpopulated column."
                            ),
                        )
                    )

            # 4. Join Multiplication Check
            # Check if query has multiple joins and lacks GROUP BY, but yields large row counts
            try:
                ast = sqlglot.parse_one(sql, read="postgres")
                joins = list(ast.find_all(exp.Join))
                group_by = ast.find(exp.Group)
                if len(joins) >= 2 and not group_by and row_count >= 500:
                    findings.append(
                        ResultValidationFinding(
                            check_type=ResultValidationType.JOIN_MULTIPLICATION,
                            severity="warning",
                            expected_range="1-to-1 or bounded fan-out",
                            observed_value=f"{row_count} rows with {len(joins)} un-grouped joins",
                            message=(
                                f"Potential join-multiplication detected ({len(joins)} joins without GROUP BY "
                                f"returned {row_count} rows). Verify join cardinality to prevent duplicated metrics."
                            ),
                        )
                    )
            except Exception:
                pass

        # Persist findings if DB and query_id provided
        if db and query_id and findings:
            cls.persist_validations(db, query_id, findings)

        return ResultValidationReport(
            has_anomalies=len(findings) > 0,
            findings_count=len(findings),
            findings=findings,
        )

    @classmethod
    def persist_validations(
        cls,
        db: Session,
        query_id: str,
        findings: List[ResultValidationFinding],
    ) -> List[ResultValidation]:
        """Persists validation findings into the result_validation table (REQ-RESULT-01)."""
        records = []
        for f in findings:
            rec = ResultValidation(
                query_id=query_id,
                check_type=f.check_type.value,
                expected_range=f.expected_range,
                observed_value=f.observed_value,
                severity=f.severity,
            )
            db.add(rec)
            records.append(rec)

        try:
            db.commit()
        except Exception:
            db.rollback()

        return records
