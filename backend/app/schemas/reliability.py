from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class SubScoreTier(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SubScoreDetail(BaseModel):
    name: str
    key: str
    score: int = Field(ge=0, le=100, description="Deterministic sub-score from 0 to 100")
    tier: SubScoreTier
    weight: float = Field(ge=0.0, le=1.0, description="Relative weight in composite calculation")
    status_icon: str = "✓"  # "✓" | "⚠" | "✗"
    summary: str
    evidence_items: List[str] = Field(default_factory=list)


class ReliabilityBreakdown(BaseModel):
    composite_score: int = Field(ge=0, le=100, description="Weighted composite score")
    tier: SubScoreTier
    status_label: str  # e.g., "✓ HIGH (92/100)"
    is_deterministic: bool = True
    is_calibrated: bool = False
    rule_reference: str = "Rule R3.3 (Traceable to 5 Deterministic Sub-scores, Deterministic Heuristic)"
    
    # 5 Sub-scores
    schema_grounding: SubScoreDetail
    join_confidence: SubScoreDetail
    filter_interpretation: SubScoreDetail
    execution_validation: SubScoreDetail
    result_sanity: SubScoreDetail
    
    # Diagnostic summary
    confidence_summary: str
    anomalies_detected: List[str] = Field(default_factory=list)
