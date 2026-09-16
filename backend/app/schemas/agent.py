from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class PlanSubTask(BaseModel):
    step_id: int
    task_name: str
    description: str
    sql_intent: str
    dependencies: List[int] = Field(default_factory=list)


class PlanStepResult(BaseModel):
    step_id: int
    task_name: str
    generated_sql: str
    policy_allowed: bool
    execution_success: bool
    row_count: int
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    execution_ms: int = 0


class PlanCompoundAnalysisRequest(BaseModel):
    question: str
    role_id: int = 1
    data_source_id: int = 1


class PlanCompoundAnalysisResponse(BaseModel):
    question: str
    is_compound: bool
    plan_explanation: str
    sub_tasks: List[PlanSubTask] = Field(default_factory=list)
    step_results: List[PlanStepResult] = Field(default_factory=list)
    synthesized_answer: str
    total_execution_ms: int
    all_steps_authorized: bool
    overall_status: str  # 'COMPLETED' | 'POLICY_BLOCKED' | 'EXECUTION_FAILED'

    model_config = ConfigDict(from_attributes=True)
