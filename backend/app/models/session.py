import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

JsonColumn = JSON().with_variant(JSONB, "postgresql")


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.data_source_id"), nullable=True)
    started_at = Column(DateTime, server_default=func.now())
    last_active_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    active_dataset = Column(String(150), nullable=True)
    active_filters = Column(JsonColumn, nullable=True)
    time_context = Column(JsonColumn, nullable=True)
    entities = Column(JsonColumn, nullable=True)
    conversation_summary = Column(Text, nullable=True)
    turn_count = Column(Integer, default=0)
    context_version = Column(Integer, default=1)
    expires_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")
    data_source = relationship("DataSource", back_populates="sessions")
    queries = relationship("QueryHistory", back_populates="session")
    reports = relationship("Report", back_populates="session")


class QueryHistory(Base):
    """
    QUERY HISTORY — extended for Trust Engine + reproducibility (Query Replay).
    """
    __tablename__ = "query_history"

    query_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    nl_question = Column(Text, nullable=False)
    classification = Column(String(20), nullable=True)  # 'answerable' | 'ambiguous' | 'unsupported' | 'unauthorized'
    ambiguity_flag = Column(Boolean, default=False)
    clarification_asked = Column(Text, nullable=True)
    initial_sql = Column(Text, nullable=True)
    final_sql = Column(Text, nullable=True)
    dialect = Column(String(20), nullable=True)
    correction_count = Column(Integer, default=0)
    error_type = Column(String(10), nullable=True)  # E1..E7
    status = Column(String(20), nullable=False, index=True)  # 'success' | 'auto_corrected' | 'failed' | 'rejected_policy' | 'rejected_unsupported'
    error_message = Column(Text, nullable=True)
    execution_ms = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    chart_type = Column(String(20), nullable=True)
    explanation = Column(Text, nullable=True)
    result_hash = Column(String(64), nullable=True)
    
    # Reproducibility (Query Replay) & Multi-Datasource Isolation
    data_source_id = Column(Integer, ForeignKey("data_sources.data_source_id"), nullable=True, index=True)
    schema_snapshot_id = Column(String(36), ForeignKey("schema_snapshot.schema_snapshot_id"), nullable=True)
    prompt_version = Column(String(20), nullable=True)
    model_name = Column(String(100), nullable=True)
    model_params = Column(JsonColumn, nullable=True)

    # Reliability scoring (5 checkable sub-scores)
    reliability_breakdown = Column(JsonColumn, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("SessionModel", back_populates="queries")
    user = relationship("User", back_populates="queries")
    data_source = relationship("DataSource", backref="queries")
    schema_snapshot = relationship("SchemaSnapshot", back_populates="queries")
    
    critic_findings = relationship("SqlCriticFinding", back_populates="query", cascade="all, delete-orphan")
    validations = relationship("ResultValidation", back_populates="query", cascade="all, delete-orphan")
    optimizations = relationship("OptimizationSuggestion", back_populates="query", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="query", cascade="all, delete-orphan")
    llm_calls = relationship("LlmCallLog", back_populates="query", cascade="all, delete-orphan")
    failures = relationship("FailureLog", back_populates="query", cascade="all, delete-orphan")
