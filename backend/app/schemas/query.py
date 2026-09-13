from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from app.schemas.policy import PolicyValidationResult
from app.schemas.reliability import ReliabilityBreakdown


class CriticFindingType(str, Enum):
    AGGREGATE_ON_IDENTIFIER = "aggregate_on_identifier"
    SUSPICIOUS_GROUP_BY = "suspicious_group_by"
    REDUNDANT_JOIN = "redundant_join"
    COUNT_ON_LEFT_JOIN = "count_on_left_join"
    MISSING_LIMIT = "missing_limit"
    TYPE_MISMATCH_FILTER = "type_mismatch_filter"


class CriticFinding(BaseModel):
    finding_id: Optional[int] = None
    finding_type: CriticFindingType
    severity: str = "warning"  # "warning" | "advisory"
    title: str
    detail: str
    suggested_fix: Optional[str] = None
    suggested_sql: Optional[str] = None
    user_action: Optional[str] = None  # 'proceeded' | 'revised' | 'fix_applied'


class CriticAnalysisResult(BaseModel):
    has_findings: bool
    findings_count: int = 0
    findings: List[CriticFinding] = Field(default_factory=list)


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
    critic_analysis: Optional[CriticAnalysisResult] = None
    reliability_breakdown: Optional[ReliabilityBreakdown] = None
    can_execute: bool
    rejection_reasons: List[str] = Field(default_factory=list)


class SQLValidateRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 4


class SQLValidateResponse(BaseModel):
    sql: str
    policy_validation: PolicyValidationResult
    critic_analysis: Optional[CriticAnalysisResult] = None
    analysis: Optional[Dict[str, Any]] = None


class SQLCriticRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 1
    query_id: Optional[str] = None


class SQLCriticResponse(BaseModel):
    sql: str
    critic_analysis: CriticAnalysisResult


class ErrorTaxonomyType(str, Enum):
    E1_SYNTAX = "E1"
    E2_SCHEMA_REFERENCE = "E2"
    E3_TYPE_MISMATCH = "E3"
    E4_SEMANTIC_LOGIC = "E4"
    E5_AUTHORIZATION = "E5"
    E6_TIMEOUT_RESOURCE = "E6"
    E7_EMPTY_RESULT_AMBIGUITY = "E7"


class CorrectionAttempt(BaseModel):
    attempt_number: int
    candidate_sql: str
    error_type: ErrorTaxonomyType
    error_message: str
    diff_summary: Optional[str] = None
    policy_approved: bool = False
    execution_success: bool = False


class SelfCorrectionRequest(BaseModel):
    original_question: str
    failing_sql: str
    error_message: str
    data_source_id: int = 1
    role_id: int = 4
    query_id: Optional[str] = None
    max_retries: int = 3


class SelfCorrectionResult(BaseModel):
    recovered: bool
    final_sql: str
    error_type: ErrorTaxonomyType
    retries_used: int
    attempts: List[CorrectionAttempt] = Field(default_factory=list)
    routed_as_policy_rejection: bool = False
    message: str


class ResultValidationType(str, Enum):
    ZERO_ROW = "zero_row"
    CARDINALITY_OUTLIER = "cardinality_outlier"
    JOIN_MULTIPLICATION = "join_multiplication"
    NULL_EXPLOSION = "null_explosion"


class ResultValidationFinding(BaseModel):
    check_type: ResultValidationType
    severity: str = "info"  # "info" | "warning" | "critical"
    expected_range: Optional[str] = None
    observed_value: Optional[str] = None
    message: str


class ResultValidationReport(BaseModel):
    has_anomalies: bool
    findings_count: int = 0
    findings: List[ResultValidationFinding] = Field(default_factory=list)


class ResultValidationRequest(BaseModel):
    sql: str
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    data_source_id: int = 1
    query_id: Optional[str] = None


class SQLExecuteRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 4
    timeout_seconds: float = 10.0
    max_rows: int = 10000
    auto_correct: bool = True
    question: Optional[str] = None
    query_id: Optional[str] = None


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
    critic_analysis: Optional[CriticAnalysisResult] = None
    error: Optional[str] = None
    error_type: Optional[ErrorTaxonomyType] = None
    correction_result: Optional[SelfCorrectionResult] = None
    result_validation: Optional[ResultValidationReport] = None
    reliability_breakdown: Optional[ReliabilityBreakdown] = None


