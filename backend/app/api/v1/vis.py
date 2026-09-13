from fastapi import APIRouter, HTTPException, status
from app.schemas.visualization import (
    ChartGenerateRequest,
    ChartGenerateResponse,
    ChartType,
)
from app.services.chart_engine import ChartEngineService

router = APIRouter(prefix="", tags=["Visualization"])


@router.post(
    "/generate-chart",
    response_model=ChartGenerateResponse,
    summary="Generate or Switch Chart Specification from Execution Results (REQ-VIS-01)",
)
def generate_chart(request: ChartGenerateRequest):
    """
    Evaluates dataset shape and types using deterministic heuristic and returns a rich ChartSpec.
    Supports user chart-type override via requested_chart_type.
    """
    try:
        spec = ChartEngineService.infer_chart_spec(
            columns=request.columns,
            rows=request.rows,
            question=request.question,
            requested_chart_type=request.requested_chart_type,
        )
        return ChartGenerateResponse(success=True, chart_spec=spec)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chart generation failed: {str(e)}",
        )


@router.get(
    "/types",
    summary="Get supported chart types and descriptions",
)
def get_supported_chart_types():
    """Returns all available chart formats supported by the Visualization Engine."""
    return {
        "success": True,
        "types": [
            {"type": ChartType.BAR.value, "label": "Vertical Bar Chart", "best_for": "Categorical comparisons (2–15 items)"},
            {"type": ChartType.HORIZONTAL_BAR.value, "label": "Horizontal Bar Chart", "best_for": "Rankings / Large category lists"},
            {"type": ChartType.LINE.value, "label": "Line Trend Curve", "best_for": "Time series / Temporal progression"},
            {"type": ChartType.AREA.value, "label": "Area Chart", "best_for": "Cumulative trends / Volume over time"},
            {"type": ChartType.DONUT.value, "label": "Donut Chart", "best_for": "Proportions / Composition (2–8 categories)"},
            {"type": ChartType.PIE.value, "label": "Pie Chart", "best_for": "Part-to-whole share breakdown"},
            {"type": ChartType.SCATTER.value, "label": "Scatter Distribution", "best_for": "Correlation between two metrics"},
            {"type": ChartType.KPI_METRIC.value, "label": "KPI Hero Card", "best_for": "Single scalar totals / averages"},
            {"type": ChartType.TABLE.value, "label": "Interactive Data Grid", "best_for": "Multi-column raw details (Rule R8.2)"},
        ],
    }
