from enum import Enum
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class ChartType(str, Enum):
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    KPI_METRIC = "kpi_metric"
    TABLE = "table"


class DataPoint(BaseModel):
    label: str
    value: Union[float, int, str, None] = None
    extra: Optional[Dict[str, Any]] = None


class ChartSeries(BaseModel):
    name: str
    data: List[Union[float, int, None]] = []
    color: Optional[str] = None


class ChartSpec(BaseModel):
    chart_type: ChartType
    title: str
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    x_column: Optional[str] = None
    y_columns: List[str] = []
    labels: List[str] = []
    series: List[ChartSeries] = []
    data_points: List[DataPoint] = []
    suggested_chart_types: List[ChartType] = []
    confidence: float = 1.0
    reasoning: str = ""
    is_visualizable: bool = True
    kpi_value: Optional[Union[float, int, str]] = None
    kpi_subtext: Optional[str] = None


class ChartGenerateRequest(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    question: Optional[str] = None
    requested_chart_type: Optional[ChartType] = None


class ChartGenerateResponse(BaseModel):
    success: bool = True
    chart_spec: ChartSpec
