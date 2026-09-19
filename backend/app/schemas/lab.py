from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AttackClassType(str, Enum):
    STRUCTURAL = "structural"
    UNION_ESCALATION = "union_escalation"
    UNAUTHORIZED_TABLE = "unauthorized_table"
    UNAUTHORIZED_COLUMN = "unauthorized_column"
    AGGREGATE_BYPASS = "aggregate_bypass"
    DANGEROUS_FUNCTION = "dangerous_function"
    CARTESIAN_EXHAUSTION = "cartesian_exhaustion"
    PROMPT_INJECTION = "prompt_injection"
    CTE_BYPASS = "cte_bypass"
    SUBQUERY_LEAKAGE = "subquery_leakage"
    JOIN_LEAKAGE = "join_leakage"
    AGGREGATE_INFERENCE = "aggregate_inference"


class BlockedStageType(str, Enum):
    AST = "ast"
    SCHEMA_AUTH = "schema_auth"
    COLUMN_AUTH = "column_auth"
    AGGREGATE_GUARD = "aggregate_guard"
    FUNCTION_ALLOWLIST = "function_allowlist"
    RESOURCE_LIMIT = "resource_limit"
    INTENT_PRECHECK = "intent_precheck"
    POLICY_ENGINE = "policy_engine"


class SecurityAttackCase(BaseModel):
    attack_id: int
    attack_name: str
    attack_class: AttackClassType
    input_payload: str
    target_role_id: int = 3  # Viewer or Analyst role
    description: str


class SecurityAttackResultItem(BaseModel):
    attack_id: int
    attack_name: str
    attack_class: AttackClassType
    input_payload: str
    blocked: bool
    blocked_at_stage: BlockedStageType
    violation_message: str


class SecurityAttackRunRequest(BaseModel):
    data_source_id: int = 1
    custom_attacks: Optional[List[SecurityAttackCase]] = None


class SecurityAttackRunResponse(BaseModel):
    run_id: str
    total_attacks: int
    total_blocked: int
    total_unblocked: int
    safety_violation_rate: float = Field(ge=0.0, le=100.0)
    status: str  # "PASSED" | "FAILED_SAFETY_GATE"
    results: List[SecurityAttackResultItem] = Field(default_factory=list)
    stage_breakdown: Dict[str, int] = Field(default_factory=dict)
    executed_at: str


class BaselineVariantType(str, Enum):
    A_PLAIN_LLM = "A_plain_llm"
    B_SCHEMA_AWARE = "B_schema_aware"
    C_SCHEMA_AND_CORRECTION = "C_schema_and_correction"
    D_POLICY_ENGINE = "D_policy_engine"
    E_SQL_CRITIC = "E_sql_critic"
    F_RESULT_VALIDATOR = "F_result_validator"
    G_FULL_TRUST_ENGINE = "G_full_trust_engine"
    D_PROPOSED = "D_proposed"  # Compatibility alias for G_FULL_TRUST_ENGINE


class BenchmarkQuestion(BaseModel):
    question_id: str
    question: str
    category: str  # simple/temporal/join/nested/ambiguous/adversarial/invalid/unauthorized/optimization
    role_id: int = 1
    expected_behavior: str = "ANSWER"  # 'ANSWER' | 'CLARIFY' | 'UNSUPPORTED' | 'UNAUTHORIZED'
    expected_tables: List[str] = Field(default_factory=list)
    is_safe: bool = True
    ground_truth_sql: Optional[str] = None
    reference_result_hash: Optional[str] = None


class EvaluationResultItem(BaseModel):
    question_id: str
    question: str
    category: str
    baseline_variant: BaselineVariantType
    generated_sql: Optional[str] = None
    execution_success: bool
    result_correct: bool
    safety_violation: bool
    unauthorized_exposure: bool
    error_type: Optional[str] = None
    latency_ms: int
    reliability_score: Optional[int] = None


class CategoryMetricRow(BaseModel):
    category: str
    question_count: int
    baseline_a_success: float = 0.0
    baseline_b_success: float = 0.0
    baseline_c_success: float = 0.0
    baseline_d_success: float = 0.0
    baseline_e_success: float = 0.0
    baseline_f_success: float = 0.0
    baseline_g_success: float = 0.0
    baseline_d_safety_violation: float = 0.0
    baseline_d_avg_latency_ms: int = 0
    variant_metrics: Optional[Dict[str, float]] = Field(default_factory=dict)


class EvaluationBenchmarkRequest(BaseModel):
    baseline_variants: Optional[List[BaselineVariantType]] = None
    categories: Optional[List[str]] = None
    data_source_id: int = 1


class EvaluationBenchmarkResponse(BaseModel):
    run_id: str
    total_questions: int
    tested_baselines: List[BaselineVariantType]
    overall_metrics: Dict[str, Any]
    category_breakdown: List[CategoryMetricRow]
    detailed_results: List[EvaluationResultItem]
    executed_at: str


class EvaluationJobAcceptedResponse(BaseModel):
    job_id: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    message: str = "Benchmark evaluation job enqueued successfully"
    status_url: str


class EvaluationJobStatusResponse(BaseModel):
    job_id: str
    created_by_user_id: Optional[int] = None
    status: str  # "pending" | "running" | "completed" | "failed"
    progress_pct: float = 0.0
    error: Optional[str] = None
    result: Optional[EvaluationBenchmarkResponse] = None
    created_at: str
    completed_at: Optional[str] = None

