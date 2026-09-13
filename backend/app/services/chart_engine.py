import re
from typing import List, Dict, Any, Optional, Tuple, Union
from app.schemas.visualization import (
    ChartType,
    ChartSpec,
    ChartSeries,
    DataPoint,
)


class ChartEngineService:
    """
    VISUALIZATION ENGINE SERVICE (REQ-VIS-01 / Task T-33 / Rule R8.2).
    Deterministic chart-type selection heuristic and data extractor.
    Always pairs every chart with a tabular representation.
    """

    COLOR_PALETTE = [
        "#6366f1",  # Indigo
        "#38bdf8",  # Sky
        "#10b981",  # Emerald
        "#f59e0b",  # Amber
        "#ec4899",  # Pink
        "#8b5cf6",  # Violet
        "#14b8a6",  # Teal
        "#f43f5e",  # Rose
    ]

    TEMPORAL_EXACT = {
        "date", "time", "year", "month", "day", "week", "quarter",
        "created_at", "updated_at", "order_date", "sale_date", "hire_date",
        "timestamp", "period", "datetime"
    }

    TEMPORAL_SUFFIXES = ("_date", "_time", "_timestamp", "_month", "_year", "_day", "_quarter", "_at")

    ID_KEYWORDS = {"id", "uuid", "pk", "fk", "ssn", "code", "key"}

    @classmethod
    def is_numeric(cls, val: Any) -> bool:
        """Check if a value is numeric (int or float)."""
        if val is None:
            return False
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return True
        if isinstance(val, str):
            try:
                float(val.replace(",", "").replace("$", "").replace("%", ""))
                return True
            except ValueError:
                return False
        return False

    @classmethod
    def to_float(cls, val: Any) -> Optional[float]:
        """Convert a value safely to float."""
        if val is None:
            return None
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val.replace(",", "").replace("$", "").replace("%", "").strip())
            except ValueError:
                return None
        return None

    @classmethod
    def is_temporal_column(cls, col_name: str, sample_values: List[Any]) -> bool:
        """Detects if a column represents a time dimension."""
        c_lower = col_name.lower().strip()
        if c_lower in cls.TEMPORAL_EXACT or c_lower.endswith(cls.TEMPORAL_SUFFIXES):
            return True
        # Check string patterns (e.g. YYYY-MM-DD, YYYY/MM, etc.)
        date_pattern = re.compile(r"^\d{4}[-/]\d{1,2}([-/]\d{1,2})?")
        for val in sample_values[:5]:
            if val and isinstance(val, str) and date_pattern.match(val.strip()):
                return True
        return False

    @classmethod
    def classify_columns(
        cls,
        columns: List[str],
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Classifies columns into (temporal_cols, categorical_cols, numeric_cols).
        """
        temporal_cols: List[str] = []
        categorical_cols: List[str] = []
        numeric_cols: List[str] = []

        for col in columns:
            sample_vals = [r.get(col) for r in rows if r.get(col) is not None]
            
            # 1. Temporal Check
            if cls.is_temporal_column(col, sample_vals):
                temporal_cols.append(col)
                continue

            # 2. Numeric Check
            num_count = sum(1 for v in sample_vals if cls.is_numeric(v))
            is_mostly_numeric = len(sample_vals) > 0 and (num_count / len(sample_vals)) >= 0.8

            # Column name looks like an ID / identifier
            is_id_col = any(col.lower().endswith(k) or col.lower() == k for k in cls.ID_KEYWORDS)

            if is_mostly_numeric and not is_id_col:
                numeric_cols.append(col)
            else:
                categorical_cols.append(col)

        return temporal_cols, categorical_cols, numeric_cols

    @classmethod
    def infer_chart_spec(
        cls,
        columns: List[str],
        rows: List[Dict[str, Any]],
        question: Optional[str] = None,
        requested_chart_type: Optional[ChartType] = None,
    ) -> ChartSpec:
        """
        Infers the optimal chart type and compiles the full ChartSpec from execution results.
        """
        if not columns or not rows:
            return ChartSpec(
                chart_type=ChartType.TABLE,
                title=question or "Data Table",
                is_visualizable=False,
                confidence=1.0,
                reasoning="Empty result set rendered as tabular view.",
            )

        row_count = len(rows)
        col_count = len(columns)
        temporal_cols, categorical_cols, numeric_cols = cls.classify_columns(columns, rows)

        # -------------------------------------------------------------------------
        # Case 1: Single Scalar Metric (e.g. COUNT(*), SUM(revenue), 1 row x 1 metric)
        # -------------------------------------------------------------------------
        if row_count == 1 and (len(numeric_cols) >= 1 or col_count <= 2):
            metric_col = numeric_cols[0] if numeric_cols else columns[0]
            val = rows[0].get(metric_col)
            label = metric_col.replace("_", " ").title()
            title = question or f"Total {label}"
            
            # Format KPI value nicely
            num_val = cls.to_float(val)
            formatted_kpi = f"{num_val:,.2f}".rstrip("0").rstrip(".") if num_val is not None else str(val)

            chosen_type = requested_chart_type or ChartType.KPI_METRIC
            return ChartSpec(
                chart_type=chosen_type,
                title=title,
                kpi_value=formatted_kpi,
                kpi_subtext=label,
                labels=[label],
                data_points=[DataPoint(label=label, value=num_val if num_val is not None else val)],
                suggested_chart_types=[ChartType.KPI_METRIC, ChartType.BAR, ChartType.TABLE],
                confidence=1.0,
                reasoning="Single scalar result automatically formatted as KPI metric.",
            )

        # -------------------------------------------------------------------------
        # Case 2: Temporal Series (Temporal X + 1+ Numeric Y)
        # -------------------------------------------------------------------------
        if temporal_cols and numeric_cols:
            x_col = temporal_cols[0]
            y_cols = numeric_cols
            labels = [str(r.get(x_col, "")) for r in rows]

            series: List[ChartSeries] = []
            for i, y_col in enumerate(y_cols):
                color = cls.COLOR_PALETTE[i % len(cls.COLOR_PALETTE)]
                series_data = [cls.to_float(r.get(y_col)) for r in rows]
                series.append(ChartSeries(name=y_col.replace("_", " ").title(), data=series_data, color=color))

            data_points: List[DataPoint] = []
            for r in rows:
                x_val = str(r.get(x_col, ""))
                y_val = cls.to_float(r.get(y_cols[0]))
                data_points.append(DataPoint(label=x_val, value=y_val))

            suggested = [ChartType.LINE, ChartType.AREA, ChartType.BAR, ChartType.TABLE]
            chosen_type = requested_chart_type or ChartType.LINE

            return ChartSpec(
                chart_type=chosen_type,
                title=question or f"{y_cols[0].replace('_', ' ').title()} Over Time",
                x_axis_label=x_col.replace("_", " ").title(),
                y_axis_label=y_cols[0].replace("_", " ").title(),
                x_column=x_col,
                y_columns=y_cols,
                labels=labels,
                series=series,
                data_points=data_points,
                suggested_chart_types=suggested,
                confidence=0.95,
                reasoning=f"Detected temporal axis '{x_col}' with metric(s) '{', '.join(y_cols)}'. Best suited for line trend curve.",
            )

        # -------------------------------------------------------------------------
        # Case 3: Categorical Breakdown (Categorical X + Numeric Y)
        # -------------------------------------------------------------------------
        if categorical_cols and numeric_cols:
            x_col = categorical_cols[0]
            y_cols = numeric_cols
            labels = [str(r.get(x_col, "")) for r in rows]

            series: List[ChartSeries] = []
            for i, y_col in enumerate(y_cols):
                color = cls.COLOR_PALETTE[i % len(cls.COLOR_PALETTE)]
                series_data = [cls.to_float(r.get(y_col)) for r in rows]
                series.append(ChartSeries(name=y_col.replace("_", " ").title(), data=series_data, color=color))

            data_points: List[DataPoint] = []
            for r in rows:
                x_val = str(r.get(x_col, ""))
                y_val = cls.to_float(r.get(y_cols[0]))
                data_points.append(DataPoint(label=x_val, value=y_val))

            # If small category count (2..8), Donut / Pie is a valid alternate
            if 2 <= row_count <= 8 and len(y_cols) == 1:
                suggested = [ChartType.BAR, ChartType.DONUT, ChartType.PIE, ChartType.LINE, ChartType.TABLE]
                chosen_type = requested_chart_type or ChartType.BAR
            elif row_count > 15:
                suggested = [ChartType.HORIZONTAL_BAR, ChartType.BAR, ChartType.TABLE]
                chosen_type = requested_chart_type or ChartType.HORIZONTAL_BAR
            else:
                suggested = [ChartType.BAR, ChartType.LINE, ChartType.DONUT, ChartType.TABLE]
                chosen_type = requested_chart_type or ChartType.BAR

            return ChartSpec(
                chart_type=chosen_type,
                title=question or f"{y_cols[0].replace('_', ' ').title()} by {x_col.replace('_', ' ').title()}",
                x_axis_label=x_col.replace("_", " ").title(),
                y_axis_label=y_cols[0].replace("_", " ").title(),
                x_column=x_col,
                y_columns=y_cols,
                labels=labels,
                series=series,
                data_points=data_points,
                suggested_chart_types=suggested,
                confidence=0.92,
                reasoning=f"Categorical dimension '{x_col}' mapped to {row_count} discrete bars.",
            )

        # -------------------------------------------------------------------------
        # Case 4: Multiple Numeric Dimensions without Categorical (Scatter / Distribution)
        # -------------------------------------------------------------------------
        if len(numeric_cols) >= 2 and not categorical_cols and not temporal_cols:
            x_col = numeric_cols[0]
            y_col = numeric_cols[1]
            labels = [f"Item {i+1}" for i in range(row_count)]

            data_points: List[DataPoint] = []
            for i, r in enumerate(rows):
                x_val = cls.to_float(r.get(x_col))
                y_val = cls.to_float(r.get(y_col))
                data_points.append(DataPoint(label=f"P{i+1}", value=y_val, extra={"x": x_val, "y": y_val}))

            suggested = [ChartType.SCATTER, ChartType.BAR, ChartType.LINE, ChartType.TABLE]
            chosen_type = requested_chart_type or ChartType.SCATTER

            return ChartSpec(
                chart_type=chosen_type,
                title=question or f"{y_col.replace('_', ' ').title()} vs {x_col.replace('_', ' ').title()}",
                x_axis_label=x_col.replace("_", " ").title(),
                y_axis_label=y_col.replace("_", " ").title(),
                x_column=x_col,
                y_columns=[y_col],
                labels=labels,
                data_points=data_points,
                suggested_chart_types=suggested,
                confidence=0.85,
                reasoning="Two continuous numerical variables mapped to 2D scatter distribution.",
            )

        # -------------------------------------------------------------------------
        # Case 5: Raw records or Unaggregated Multi-Column Data (Table Fallback)
        # -------------------------------------------------------------------------
        labels = [str(r.get(columns[0], "")) for r in rows]
        return ChartSpec(
            chart_type=requested_chart_type or ChartType.TABLE,
            title=question or "Tabular Query Results",
            is_visualizable=False,
            labels=labels,
            suggested_chart_types=[ChartType.TABLE],
            confidence=1.0,
            reasoning="Unaggregated multi-attribute dataset formatted in interactive tabular grid (Rule R8.2).",
        )
