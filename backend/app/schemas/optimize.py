from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class JoinAlgorithmEnum(str, Enum):
    TABLE_SCAN = "TABLE_SCAN"
    INDEX_SCAN = "INDEX_SCAN"
    HASH_JOIN = "HASH_JOIN"
    NESTED_LOOP_JOIN = "NESTED_LOOP_JOIN"
    SORT_MERGE_JOIN = "SORT_MERGE_JOIN"


class GateDecisionEnum(str, Enum):
    ALLOW = "ALLOW"
    WARN_EXPENSIVE = "WARN_EXPENSIVE"
    BLOCK_EXPENSIVE = "BLOCK_EXPENSIVE"
    BLOCK_RUNAWAY_CARTESIAN = "BLOCK_RUNAWAY_CARTESIAN"


class OptimizeExplainRequest(BaseModel):
    sql: str
    query_id: Optional[str] = None
    dialect: str = "sqlite"
    role_name: str = "analyst"


class OptimizeAnalyzeRequest(BaseModel):
    sql: str
    query_id: Optional[str] = None
    dialect: str = "sqlite"
    role_name: str = "admin"


class OptimizationEvidence(BaseModel):
    observed: str
    estimated_rows: Optional[float] = None
    actual_rows: Optional[float] = None
    filter_condition: Optional[str] = None
    existing_indexes: List[str] = Field(default_factory=list)
    cost: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class OptimizationItem(BaseModel):
    suggestion_id: Optional[int] = None
    issue_type: str
    detail: str
    evidence_json: Dict[str, Any]
    confidence: str = "medium"  # 'low' | 'medium' | 'high'
    suggested_ddl: Optional[str] = None


class OptimizeResponse(BaseModel):
    mode: str = "explain"  # 'explain' | 'explain_analyze'
    plan_raw: Any
    plan_summary: Dict[str, Any]
    suggestions: List[OptimizationItem]
    execution_stats: Optional[Dict[str, Any]] = None
    query_id: Optional[str] = None
    created_at: str


# =========================================================================
# COST-BASED JOIN OPTIMIZER SCHEMAS (DSA / Bitmask DP Planner)
# =========================================================================

class CostBreakdown(BaseModel):
    io_cost: float
    cpu_cost: float
    total_cost: float
    estimated_rows: float


class JoinNodePlan(BaseModel):
    node_id: str
    operator: JoinAlgorithmEnum
    table_name: Optional[str] = None
    alias: Optional[str] = None
    join_predicate: Optional[str] = None
    cardinality: float
    cost: float
    left_child: Optional[Dict[str, Any]] = None
    right_child: Optional[Dict[str, Any]] = None


class ExecutionBenchmarkResult(BaseModel):
    original_exec_ms: float
    optimized_exec_ms: float
    speedup_ratio: float
    results_equivalent: bool
    row_count: int
    validation_status: str


class JoinPlanRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 1
    max_allowed_cost: float = 50000.0
    benchmark: bool = False
    strict_admission: bool = True


class JoinPlanResponse(BaseModel):
    original_sql: str
    optimized_sql: str
    tables: List[str]
    join_edges_count: int
    search_strategy: str  # "BITMASK_DYNAMIC_PROGRAMMING" | "GREEDY_MIN_SELECTIVITY" | "SINGLE_TABLE"
    subsets_evaluated: int
    naive_cost: float
    optimal_cost: float
    cost_reduction_pct: float
    gate_decision: GateDecisionEnum
    gate_reason: str
    plan_tree: Dict[str, Any]
    indexes_used: List[str] = Field(default_factory=list)
    stats_source: str = "catalog"  # "live_engine" | "calibrated_cache" | "fallback_schema"
    execution_benchmark: Optional[ExecutionBenchmarkResult] = None
    execution_recommendation: str
    created_at: str
