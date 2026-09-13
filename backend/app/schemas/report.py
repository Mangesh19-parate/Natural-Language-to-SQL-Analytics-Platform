from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ReportQueryItem(BaseModel):
    query_id: Optional[str] = None
    question: str
    proposed_sql: Optional[str] = None
    executed_sql: str
    status: str = "success"
    latency_ms: int = 0
    row_count: int = 0
    dialect: str = "sqlite"
    timestamp: Optional[str] = None
    reliability_breakdown: Optional[Dict[str, Any]] = None
    critic_analysis: Optional[Dict[str, Any]] = None
    result_validation: Optional[Dict[str, Any]] = None
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)


class ReportExportRequest(BaseModel):
    title: str = "SQL Trust & Reliability Audit Report"
    scope: str = "single_query"  # "single_query" | "session"
    user_id: Optional[int] = 1
    role_name: str = "Admin"
    data_source_name: str = "Northwind Commercial DB"
    queries: List[ReportQueryItem] = Field(default_factory=list)
    include_raw_data: bool = True
    max_data_rows: int = 50


class ReportGenerateResponse(BaseModel):
    report_id: str
    title: str
    format: str
    scope: str
    status: str
    created_at: str
    download_url: Optional[str] = None
