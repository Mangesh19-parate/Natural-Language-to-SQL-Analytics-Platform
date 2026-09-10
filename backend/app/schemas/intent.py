from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class IntentClassification(str, Enum):
    ANSWERABLE = "answerable"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"
    UNAUTHORIZED = "unauthorized"


class ClarificationOption(BaseModel):
    option_id: str
    label: str
    table_name: str
    column_name: str
    description: str


class IntentAnalysisResult(BaseModel):
    classification: IntentClassification
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: str
    evidence_gap: Optional[str] = None
    available_tables: List[str] = []
    clarification_prompt: Optional[str] = None
    clarification_options: List[ClarificationOption] = []
    resolved_question: Optional[str] = None


class IntentClassifyRequest(BaseModel):
    question: str
    data_source_id: Optional[int] = 1
    role_id: Optional[int] = None


class IntentResolveRequest(BaseModel):
    original_question: str
    selected_option_id: str
    clarification_prompt: str
    selected_option: ClarificationOption
