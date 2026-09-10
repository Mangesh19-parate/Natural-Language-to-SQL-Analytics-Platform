import uuid
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Numeric, LargeBinary, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class LlmCallLog(Base):
    """
    LLM CALL LOG — hashed, privacy-safe by default (Rule R5.3).
    """
    __tablename__ = "llm_call_log"

    call_id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(36), ForeignKey("query_history.query_id"), nullable=True)
    model_name = Column(String(100), nullable=True)
    purpose = Column(String(30), nullable=False)  # 'sql_generation' | 'self_correction' | 'explanation' | 'ambiguity_check'
    retry_number = Column(Integer, default=0)
    prompt_hash = Column(String(64), nullable=False)
    response_hash = Column(String(64), nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cost_estimate = Column(Numeric(10, 4), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    query = relationship("QueryHistory", back_populates="llm_calls")
    trace = relationship("EncryptedTraceStore", back_populates="call_log", uselist=False)


class EncryptedTraceStore(Base):
    """
    Separate, access-restricted store for raw traces if ever needed for research (Rule R5.3).
    """
    __tablename__ = "encrypted_trace_store"

    trace_id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("llm_call_log.call_id"), nullable=False)
    prompt_enc = Column(LargeBinary, nullable=True)
    response_enc = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    call_log = relationship("LlmCallLog", back_populates="trace")


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)
    query_id = Column(String(36), ForeignKey("query_history.query_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    rating = Column(String(10), nullable=False)  # 'correct' | 'incorrect'
    feedback_type = Column(String(30), nullable=True)  # 'wrong_sql' | 'wrong_chart' | 'wrong_interpretation' | 'other'
    expected_behavior = Column(Text, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    query = relationship("QueryHistory", back_populates="feedbacks")
    user = relationship("User", back_populates="feedbacks")


class Report(Base):
    """
    REPORTS — owner-only download in v1 (REQ-RPT-01).
    """
    __tablename__ = "reports"

    report_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=True)
    title = Column(String(255), nullable=False)
    format = Column(String(10), nullable=False)  # 'pdf' | 'xlsx'
    file_path = Column(Text, nullable=False)
    scope = Column(String(20), default="single_query")  # 'single_query' | 'session'
    status = Column(String(20), default="ready")
    content_hash = Column(String(64), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="reports")
    session = relationship("SessionModel", back_populates="reports")
