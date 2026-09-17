# ADR-005: Ground-Truth Tuple-Equality Benchmarking vs. Surface String Comparison

## Status
Accepted

## Date
2026-09-17

## Context and Problem Statement
Evaluating the accuracy of Natural Language to SQL (NL→SQL) systems is notoriously difficult. Common simplistic approaches evaluate either:
1. **Exact SQL String Matching**: Compares generated SQL against a reference query string. This is deeply flawed because multiple valid SQL representations exist for any semantic question (e.g. `WHERE a = 1 AND b = 2` vs `WHERE b = 2 AND a = 1`, subquery vs. CTE, implicit join vs. explicit `INNER JOIN`).
2. **LLM-as-a-Judge Evaluation**: Asks an LLM whether the query or result "looks correct". This introduces subjective hallucinations, non-reproducibility, and circular dependency.

We need a mathematically rigorous, fully reproducible ground-truth execution evaluation framework.

## Decision Drivers
- **Execution Accuracy (EX)**: Comparing actual dataset output sets rather than surface syntax strings.
- **Multiset Tuple Equality**: Comparing rows independent of column ordering or row ordering (unless explicit `ORDER BY` is semantically specified).
- **Floating-Point Tolerance**: Robust comparison of numerical aggregates (e.g., averages, ratios) within $\epsilon = 10^{-4}$ tolerance.
- **Complete Test Fixture Coverage**: 100% of benchmark queries must have verified PostgreSQL ground-truth SQL and expected behavior specifications.

## Decision Outcome
Chosen Solution: **Multiset Tuple-Equality Result Comparison on a Standard PostgreSQL Benchmark Fixture Set**.

### Architectural Design:
1. **Complete 165-Query Ground-Truth Suite**:
   - Spanning Simple (Filter, Sort, Limit), Medium (Single/Multi-table Joins, Aggregates, Group By), Hard (HAVING, Subqueries, Multi-Joins), and Extra Hard (CTEs, Window Functions, Self-Joins).
   - Each query in `EvaluationLabService.STANDING_BENCHMARK_CASES` defines: `case_id`, `category`, `difficulty`, `question`, `ground_truth_sql`, and `expected_behavior`.
2. **Key-Aligned Multiset Normalization**:
   - Both candidate output rows and ground-truth output rows are normalized into multisets of sorted tuple values.
   - For numerical fields, values are rounded to 4 decimal places (`round(float(v), 4)`) or compared with `math.isclose(v1, v2, abs_tol=1e-4)`.
   - Result comparison checks:
     $$\text{Multiset}(\text{CandidateRows}) \equiv \text{Multiset}(\text{GroundTruthRows})$$
3. **Multi-Variant Comparative Matrix**:
   - Executes 4 baseline architectures across every category:
     - **Baseline A**: Naive prompt (zero schema context, no AST validation).
     - **Baseline B**: Schema-conditioned prompt (raw DDL context).
     - **Baseline C**: Policy-filtered semantic catalog (role-scoped).
     - **Baseline D (Full Platform)**: Policy-filtered catalog + AST validation + SQL Critic + Self-Correction loop.
   - Metrics computed: Exact Execution Match Rate (%), Syntax Validity Rate (%), Safety/Policy Block Rate (%), Mean Latency (ms).

### Consequences
- **Positive**:
  - Zero synthetic or manufactured evaluation metrics.
  - Objective, mathematically verified execution accuracy.
  - Reproducible benchmark comparisons across LLM models and prompt iterations.
- **Negative**:
  - Requires executing queries against a populated sandbox database engine.
