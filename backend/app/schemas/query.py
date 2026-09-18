from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from app.schemas.policy import PolicyValidationResult
from app.schemas.reliability import ReliabilityBreakdown
from app.schemas.visualization import ChartSpec
from app.schemas.optimize import JoinPlanResponse


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
    generation_mode: str = "live"  # 'live' | 'deterministic_fallback' | 'mock'
    fallback_used: bool = False
    provider_error: Optional[str] = None
    model_name: Optional[str] = None
    provider: Optional[str] = None
    prompt_template_version: Optional[str] = "v1.2-catalog"



class SQLGenerateRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    data_source_id: int = Field(default=1, ge=1)
    role_id: int = Field(default=4, ge=1)  # Default to viewer/analyst role
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
    sql: str = Field(..., min_length=1, max_length=20000)
    data_source_id: int = Field(default=1, ge=1)
    role_id: int = Field(default=4, ge=1)


class SQLValidateResponse(BaseModel):
    sql: str
    policy_validation: PolicyValidationResult
    critic_analysis: Optional[CriticAnalysisResult] = None
    analysis: Optional[Dict[str, Any]] = None


class SQLCriticRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=20000)
    data_source_id: int = Field(default=1, ge=1)
    role_id: int = Field(default=1, ge=1)
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
    original_question: str = Field(..., min_length=1, max_length=2000)
    failing_sql: str = Field(..., min_length=1, max_length=20000)
    error_message: str
    data_source_id: int = Field(default=1, ge=1)
    role_id: int = Field(default=4, ge=1)
    query_id: Optional[str] = None
    max_retries: int = Field(default=3, ge=1, le=5)


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
    sql: str = Field(..., min_length=1, max_length=20000)
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    data_source_id: int = Field(default=1, ge=1)
    query_id: Optional[str] = None


class SQLExecuteRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=20000)
    data_source_id: int = Field(default=1, ge=1)
    role_id: int = Field(default=4, ge=1)
    timeout_seconds: float = Field(default=10.0, ge=0.5, le=30.0)
    max_rows: int = Field(default=1000, ge=1, le=10000)
    auto_correct: bool = True
    question: Optional[str] = Field(default=None, max_length=2000)
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
    chart_spec: Optional[ChartSpec] = None
    optimization_plan: Optional[JoinPlanResponse] = None


