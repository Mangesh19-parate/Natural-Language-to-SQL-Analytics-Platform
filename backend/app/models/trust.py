from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

JsonColumn = JSON().with_variant(JSONB, "postgresql")


class SqlCriticFinding(Base):
    """
    SQL CRITIC FINDINGS — semantic-smell checks before execution (REQ-CRITIC-01).
    """
    __tablename__ = "sql_critic_findings"

    finding_id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(36), ForeignKey("query_history.query_id"), nullable=False)
    finding_type = Column(String(50), nullable=False)  # 'aggregate_on_identifier' | 'suspicious_group_by' | 'type_mismatch_filter' | 'redundant_join'
    detail = Column(Text, nullable=True)
    suggested_fix = Column(Text, nullable=True)
    user_action = Column(String(20), nullable=True)  # 'proceeded' | 'revised' | 'ignored'
    created_at = Column(DateTime, server_default=func.now())

    query = relationship("QueryHistory", back_populates="critic_findings")


class ResultValidation(Base):
    """
    RESULT VALIDATION — sanity checks on the result set itself (REQ-RESULT-01).
    """
    __tablename__ = "result_validation"

    validation_id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(36), ForeignKey("query_history.query_id"), nullable=False)
    check_type = Column(String(50), nullable=False)  # 'zero_row' | 'cardinality_outlier' | 'join_multiplication' | 'null_explosion'
    expected_range = Column(String(100), nullable=True)
    observed_value = Column(String(100), nullable=True)
    severity = Column(String(10), default="info")  # 'info' | 'warning' | 'critical'
    created_at = Column(DateTime, server_default=func.now())

    query = relationship("QueryHistory", back_populates="validations")


class OptimizationSuggestion(Base):
    """
    OPTIMIZATION SUGGESTIONS (evidence-based; EXPLAIN by default, ANALYZE opt-in).
    """
    __tablename__ = "optimization_suggestions"

    suggestion_id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(36), ForeignKey("query_history.query_id"), nullable=False)
    mode = Column(String(10), default="explain")  # 'explain' | 'explain_analyze' (admin-gated)
    issue_type = Column(String(50), nullable=True)
    detail = Column(Text, nullable=True)
    evidence_json = Column(JsonColumn, nullable=True)  # estimated rows, existing indexes, plan cost
    confidence = Column(String(10), default="medium")  # 'low' | 'medium' | 'high'
    suggested_ddl = Column(Text, nullable=True)  # copyable only, never auto-executed
    created_at = Column(DateTime, server_default=func.now())

    query = relationship("QueryHistory", back_populates="optimizations")
