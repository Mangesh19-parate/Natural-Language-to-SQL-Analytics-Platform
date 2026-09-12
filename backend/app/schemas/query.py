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
