from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class FailureClassCount(BaseModel):
    failure_class: str
    count: int
    percentage: float
    description: str
    severity: str  # 'low' | 'medium' | 'high' | 'critical'


class ProblematicPhraseItem(BaseModel):
    phrase: str
    occurrences: int
    affected_categories: List[str] = Field(default_factory=list)
    recommended_intervention: str


class FailureLogItem(BaseModel):
    failure_id: int
    query_id: Optional[str] = None
    failure_class: str
    problematic_phrase: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FailureObservatoryStatsResponse(BaseModel):
    total_failures: int
    time_window: str = "Last 30 days"
    failure_classes: List[FailureClassCount] = Field(default_factory=list)
    top_problematic_phrases: List[ProblematicPhraseItem] = Field(default_factory=list)
    top_recommended_intervention: str
    failure_rate: float
