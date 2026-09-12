from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.policy import PolicyValidationResult


class SQLProposal(BaseModel):
    sql: str
    rationale: str
    is_proposal: bool = True


class SQLGenerateRequest(BaseModel):
    question: str
    data_source_id: int = 1
    role_id: int = 4  # Default to viewer/analyst role
    session_id: Optional[str] = None
    clarifications: Optional[Dict[str, Any]] = None


class SQLGenerateResponse(BaseModel):
    question: str
    proposal: SQLProposal
    policy_validation: PolicyValidationResult
    can_execute: bool
    rejection_reasons: List[str] = Field(default_factory=list)


class SQLValidateRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 4


class SQLValidateResponse(BaseModel):
    sql: str
    policy_validation: PolicyValidationResult
    analysis: Optional[Dict[str, Any]] = None


class SQLExecuteRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 4
    timeout_seconds: float = 10.0
    max_rows: int = 10000


class SQLExecuteResponse(BaseModel):
    success: bool
    sql: str
    injected_sql: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    latency_ms: int = 0
    truncated: bool = False
    policy_validation: PolicyValidationResult
    error: Optional[str] = None
