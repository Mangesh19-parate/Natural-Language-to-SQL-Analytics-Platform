import pytest
from app.schemas.visualization import ChartType
from app.services.chart_engine import ChartEngineService


def test_single_scalar_kpi_detection():
    """Single scalar numerical metric (1 row) -> KPI_METRIC"""
    cols = ["total_revenue"]
    rows = [{"total_revenue": 142500.50}]
    spec = ChartEngineService.infer_chart_spec(cols, rows, question="What is the total revenue?")

    assert spec.chart_type == ChartType.KPI_METRIC
    assert spec.is_visualizable is True
    assert spec.kpi_value == "142,500.5"
    assert spec.kpi_subtext == "Total Revenue"
    assert ChartType.KPI_METRIC in spec.suggested_chart_types


def test_temporal_series_line_detection():
    """Time series with date column and numerical metric -> LINE"""
    cols = ["order_date", "daily_sales"]
    rows = [
        {"order_date": "2025-01-01", "daily_sales": 1200},
        {"order_date": "2025-01-02", "daily_sales": 1550},
        {"order_date": "2025-01-03", "daily_sales": 900},
        {"order_date": "2025-01-04", "daily_sales": 2100},
    ]
    spec = ChartEngineService.infer_chart_spec(cols, rows, question="Daily sales trend in January")

    assert spec.chart_type == ChartType.LINE
    assert spec.x_column == "order_date"
    assert spec.y_columns == ["daily_sales"]
    assert len(spec.series) == 1
    assert spec.series[0].data == [1200.0, 1550.0, 900.0, 2100.0]
    assert ChartType.LINE in spec.suggested_chart_types
    assert ChartType.AREA in spec.suggested_chart_types


def test_categorical_breakdown_bar_and_donut_detection():
    """Categorical column (department) with numerical count/metric -> BAR / DONUT"""
    cols = ["department_name", "employee_count"]
    rows = [
        {"department_name": "Engineering", "employee_count": 45},
        {"department_name": "Sales", "employee_count": 30},
        {"department_name": "Marketing", "employee_count": 15},
        {"department_name": "Human Resources", "employee_count": 10},
    ]
    spec = ChartEngineService.infer_chart_spec(cols, rows, question="Employees by department")

    assert spec.chart_type == ChartType.BAR
    assert spec.x_column == "department_name"
    assert len(spec.labels) == 4
    assert spec.labels[0] == "Engineering"
    assert ChartType.BAR in spec.suggested_chart_types
    assert ChartType.DONUT in spec.suggested_chart_types


def test_manual_chart_type_override():
    """User requests DONUT chart explicitly for categorical data"""
    cols = ["category", "sales_count"]
    rows = [
        {"category": "Electronics", "sales_count": 500},
        {"category": "Apparel", "sales_count": 350},
        {"category": "Home", "sales_count": 150},
    ]
    spec = ChartEngineService.infer_chart_spec(
        cols, rows, question="Sales share by category", requested_chart_type=ChartType.DONUT
    )

    assert spec.chart_type == ChartType.DONUT
    assert len(spec.data_points) == 3
    assert spec.data_points[0].value == 500.0


def test_scatter_distribution_detection():
    """Two continuous numeric columns without categorical text -> SCATTER"""
    cols = ["experience_years", "salary"]
    rows = [
        {"experience_years": 1, "salary": 50000},
        {"experience_years": 3, "salary": 70000},
        {"experience_years": 5, "salary": 95000},
        {"experience_years": 10, "salary": 140000},
    ]
    spec = ChartEngineService.infer_chart_spec(cols, rows, question="Experience vs Salary")

    assert spec.chart_type == ChartType.SCATTER
    assert len(spec.data_points) == 4
    assert spec.data_points[0].extra["x"] == 1.0
    assert spec.data_points[0].extra["y"] == 50000.0


def test_empty_or_raw_records_table_fallback():
    """Raw unaggregated data with multiple string columns -> TABLE"""
    cols = ["customer_name", "city", "email", "status"]
    rows = [
        {"customer_name": "Alice", "city": "New York", "email": "alice@ex.com", "status": "active"},
        {"customer_name": "Bob", "city": "London", "email": "bob@ex.com", "status": "active"},
    ]
    spec = ChartEngineService.infer_chart_spec(cols, rows, question="List all customer details")

    assert spec.chart_type == ChartType.TABLE
    assert spec.is_visualizable is False
    assert ChartType.TABLE in spec.suggested_chart_types
