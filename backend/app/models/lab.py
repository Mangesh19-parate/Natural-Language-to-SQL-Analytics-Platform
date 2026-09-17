import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Numeric, Index, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class SecurityAttackLog(Base):
    """
    SECURITY ATTACK LAB — standing adversarial test results (REQ-SECLAB-01).
    """
    __tablename__ = "security_attack_log"

    attack_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), nullable=False, index=True)  # groups one full attack-suite run
    attack_name = Column(String(150), nullable=False)  # 'drop_table', 'union_privilege_escalation', ...
    attack_class = Column(String(30), nullable=False)  # 'structural' | 'prompt_injection'
    input_payload = Column(Text, nullable=True)
    blocked = Column(Boolean, nullable=False)
    blocked_at_stage = Column(String(30), nullable=False)  # 'ast' | 'schema_auth' | 'column_auth' | 'function_allowlist' | 'resource_limit'
    created_at = Column(DateTime, server_default=func.now())


class FailureLog(Base):
    """
    FAILURE OBSERVATORY — aggregation source (REQ-FAILOBS-01, P1).
    """
    __tablename__ = "failure_log"

    failure_id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(36), ForeignKey("query_history.query_id"), nullable=True)
    failure_class = Column(String(30), nullable=False, index=True)
    problematic_phrase = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    query = relationship("QueryHistory", back_populates="failures")


class EvaluationRun(Base):
    """
    EVALUATION LAB — benchmark persistence (REQ-EVALLAB-01).
    """
    __tablename__ = "evaluation_run"

    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    baseline_variant = Column(String(30), nullable=False)  # 'A_plain_llm' | 'B_schema_aware' | 'C_schema_and_correction' | 'D_proposed'
    schema_snapshot_id = Column(String(36), ForeignKey("schema_snapshot.schema_snapshot_id"), nullable=True)
    prompt_version = Column(String(20), nullable=True)
    model_name = Column(String(100), nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    schema_snapshot = relationship("SchemaSnapshot", back_populates="evaluation_runs")
    results = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")


class EvaluationResult(Base):
    """
    EVALUATION RESULT — per-question evaluation breakdown.
    """
    __tablename__ = "evaluation_result"

    result_id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), ForeignKey("evaluation_run.run_id"), nullable=False, index=True)
    question_id = Column(String(20), nullable=False)
    category = Column(String(30), nullable=False, index=True)  # simple/temporal/join/nested/ambiguous/adversarial/invalid/unauthorized/optimization
    baseline_variant = Column(String(40), nullable=True, index=True)
    execution_success = Column(Boolean, default=False)
    result_correct = Column(Boolean, default=False)
    error_type = Column(String(10), nullable=True)  # E1..E7 if failed
    safety_violation = Column(Boolean, default=False)
    unauthorized_exposure = Column(Boolean, default=False)
    latency_ms = Column(Integer, nullable=True)
    token_cost = Column(Numeric(10, 4), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    run = relationship("EvaluationRun", back_populates="results")

