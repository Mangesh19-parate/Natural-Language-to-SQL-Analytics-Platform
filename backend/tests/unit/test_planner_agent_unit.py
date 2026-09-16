import pytest
from app.schemas.agent import PlanSubTask, PlanStepResult
from app.services.planner_agent import PlannerAgentService


def test_planner_agent_compound_query_detection():
    assert PlannerAgentService.is_compound_query("Compare 2023 vs 2024 revenue") is True
    assert PlannerAgentService.is_compound_query("Show top and bottom customers") is True
    assert PlannerAgentService.is_compound_query("Difference between East and West regions") is True
    assert PlannerAgentService.is_compound_query("List all employees") is False


def test_planner_agent_dynamic_yoy_synthesis():
    task = PlanSubTask(
        step_id=3,
        task_name="Compute 2023 vs 2024 Growth Variance",
        description="Synthesize YoY percentage change and growth variance",
        sql_intent="",
        dependencies=[1, 2],
    )

    step1_result = PlanStepResult(
        step_id=1,
        task_name="Extract 2023 Baseline Metrics",
        generated_sql="SELECT total_revenue FROM orders",
        policy_allowed=True,
        execution_success=True,
        row_count=1,
        columns=["total_revenue", "total_orders"],
        rows=[{"total_revenue": 100000.0, "total_orders": 50}],
    )

    step2_result = PlanStepResult(
        step_id=2,
        task_name="Extract 2024 Comparison Metrics",
        generated_sql="SELECT total_revenue FROM orders",
        policy_allowed=True,
        execution_success=True,
        row_count=1,
        columns=["total_revenue", "total_orders"],
        rows=[{"total_revenue": 125000.0, "total_orders": 65}],
    )

    synthesis = PlannerAgentService._perform_dynamic_synthesis(
        task=task,
        step_results=[step1_result, step2_result],
        question="Compare 2023 vs 2024 revenue",
    )

    assert synthesis.execution_success is True
    assert synthesis.policy_allowed is True
    assert len(synthesis.rows) == 2

    rev_row = next(r for r in synthesis.rows if r["metric"] == "Revenue")
    assert rev_row["baseline_value"] == "$100,000.00"
    assert rev_row["comparison_value"] == "$125,000.00"
    assert rev_row["absolute_delta"] == "+$25,000.00"
    assert rev_row["percentage_change"] == "+25.00%"

    ord_row = next(r for r in synthesis.rows if r["metric"] == "Order Volume")
    assert ord_row["baseline_value"] == "50"
    assert ord_row["comparison_value"] == "65"
    assert ord_row["percentage_change"] == "+30.00%"


def test_planner_agent_dynamic_cohort_spread_synthesis():
    task = PlanSubTask(
        step_id=3,
        task_name="Synthesize Cohort Spread",
        description="Synthesize top vs bottom cohort delta",
        sql_intent="",
        dependencies=[1, 2],
    )

    step1 = PlanStepResult(
        step_id=1,
        task_name="Extract Top 5 Entities",
        generated_sql="SELECT customer_name, total_spent FROM customers",
        policy_allowed=True,
        execution_success=True,
        row_count=2,
        columns=["customer_name", "total_spent"],
        rows=[{"customer_name": "Cust A", "total_spent": 10000.0}, {"customer_name": "Cust B", "total_spent": 8000.0}],
    )

    step2 = PlanStepResult(
        step_id=2,
        task_name="Extract Bottom 5 Entities",
        generated_sql="SELECT customer_name, total_spent FROM customers",
        policy_allowed=True,
        execution_success=True,
        row_count=2,
        columns=["customer_name", "total_spent"],
        rows=[{"customer_name": "Cust Y", "total_spent": 1000.0}, {"customer_name": "Cust Z", "total_spent": 800.0}],
    )

    synthesis = PlannerAgentService._perform_dynamic_synthesis(
        task=task,
        step_results=[step1, step2],
        question="Compare top and bottom customers",
    )

    assert synthesis.execution_success is True
    row_map = {r["metric"]: r["value"] for r in synthesis.rows}
    assert row_map["Top 5 Total Spend"] == "$18,000.00"
    assert row_map["Bottom 5 Total Spend"] == "$1,800.00"
    assert row_map["Cohort Spread"] == "$16,200.00"
    assert row_map["Spending Multiplier"] == "10.00x"
