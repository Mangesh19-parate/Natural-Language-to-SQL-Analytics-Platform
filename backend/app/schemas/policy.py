from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class PolicyViolationType(str, Enum):
    STATEMENT_NOT_ALLOWED = "STATEMENT_NOT_ALLOWED"
    MULTIPLE_STATEMENTS = "MULTIPLE_STATEMENTS"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    UNAUTHORIZED_TABLE = "UNAUTHORIZED_TABLE"
    UNAUTHORIZED_COLUMN = "UNAUTHORIZED_COLUMN"
    UNAUTHORIZED_AGGREGATE = "UNAUTHORIZED_AGGREGATE"
    DISALLOWED_FUNCTION = "DISALLOWED_FUNCTION"
    CARTESIAN_PRODUCT_BLOCKED = "CARTESIAN_PRODUCT_BLOCKED"
    ROW_FILTER_REQUIRED = "ROW_FILTER_REQUIRED"
    COST_LIMIT_EXCEEDED = "COST_LIMIT_EXCEEDED"


class PolicyViolation(BaseModel):
    violation_type: PolicyViolationType
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    function_name: Optional[str] = None
    message: str


class SQLAnalysisResult(BaseModel):
    is_valid_syntax: bool
    is_select_only: bool
    syntax_error: Optional[str] = None
    tables: List[str] = Field(default_factory=list)
    # Map table_name -> list of columns referenced
    table_columns: Dict[str, List[str]] = Field(default_factory=dict)
    # Map table_name -> list of (func_name, col_name)
    aggregates: List[Dict[str, str]] = Field(default_factory=list)
    functions: List[str] = Field(default_factory=list)
    disallowed_functions: List[str] = Field(default_factory=list)
    has_cartesian_join: bool = False


class PolicyValidationResult(BaseModel):
    is_allowed: bool
    status: str = "APPROVED"  # "APPROVED" | "REJECTED"
    violations: List[PolicyViolation] = Field(default_factory=list)
    effective_tables: List[str] = Field(default_factory=list)
    applied_row_filters: Dict[str, str] = Field(default_factory=dict)
    injected_sql: Optional[str] = None
    estimated_cost: Optional[float] = None


class DataPolicyCreate(BaseModel):
    role_id: int
    data_source_id: int
    table_name: str
    column_name: Optional[str] = None
    access_level: str = "read"  # 'denied' | 'read' | 'read_aggregate_only'
    aggregate_allowed: bool = False
    row_filter_sql: Optional[str] = None


class DataPolicyUpdate(BaseModel):
    access_level: Optional[str] = None  # 'denied' | 'read' | 'read_aggregate_only'
    aggregate_allowed: Optional[bool] = None
    row_filter_sql: Optional[str] = None


class DataPolicyOut(BaseModel):
    policy_id: int
    role_id: int
    role_name: Optional[str] = None
    data_source_id: int
    table_name: str
    column_name: Optional[str] = None
    access_level: str
    aggregate_allowed: bool
    row_filter_sql: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PolicyMatrixColumnItem(BaseModel):
    column_name: str
    access_level: str
    aggregate_allowed: bool
    is_explicit: bool
    is_fail_closed_denied: bool
    sensitivity: Optional[str] = "NONE"
    semantic_type: Optional[str] = None
    policy_id: Optional[int] = None


class PolicyMatrixTableItem(BaseModel):
    table_name: str
    access_level: str
    aggregate_allowed: bool
    row_filter_sql: Optional[str] = None
    is_explicit: bool
    is_fail_closed_denied: bool
    policy_id: Optional[int] = None
    columns: List[PolicyMatrixColumnItem] = Field(default_factory=list)


class DataPolicyMatrixResponse(BaseModel):
    role_id: int
    role_name: str
    data_source_id: int
    tables: List[PolicyMatrixTableItem] = Field(default_factory=list)


class EffectiveTablePolicy(BaseModel):
    table_name: str
    accessible: bool = False
    access_level: str = "denied"
    allowed_columns: List[str] = []
    denied_columns: List[str] = []
    aggregate_allowed_columns: List[str] = []
    row_filter_sql: Optional[str] = None


class EffectivePolicySummary(BaseModel):
    role_id: int
    data_source_id: int
    accessible_tables: Dict[str, EffectiveTablePolicy] = {}

