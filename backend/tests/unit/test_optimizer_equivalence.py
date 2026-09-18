import pytest
from collections import Counter
from sqlalchemy import create_engine, text
from app.services.optimizer import CostBasedJoinOptimizer
from app.services.execution_sandbox import ExecutionSandboxService


@pytest.fixture
def memory_db_engine():
    """Provides an isolated in-memory SQLite engine seeded with multi-table relational schema."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE t_depts (dept_id INT PRIMARY KEY, name TEXT);"))
        conn.execute(text("CREATE TABLE t_emps (emp_id INT PRIMARY KEY, dept_id INT, emp_name TEXT);"))
        conn.execute(text("CREATE TABLE t_custs (cust_id INT PRIMARY KEY, city TEXT, rating INT);"))
        conn.execute(text("CREATE TABLE t_prods (prod_id INT PRIMARY KEY, title TEXT, price REAL);"))
        conn.execute(text("CREATE TABLE t_orders (order_id INT PRIMARY KEY, cust_id INT, emp_id INT, prod_id INT, amount REAL);"))

        # Seed data
        conn.execute(text("INSERT INTO t_depts VALUES (1, 'Sales'), (2, 'Tech'), (3, 'HR');"))
        conn.execute(text("INSERT INTO t_emps VALUES (10, 1, 'Alice'), (20, 2, 'Bob'), (30, 1, 'Charlie');"))
        conn.execute(text("INSERT INTO t_custs VALUES (100, 'NY', 5), (200, 'SF', 4), (300, 'Chicago', 3);"))
        conn.execute(text("INSERT INTO t_prods VALUES (1000, 'Laptop', 1200.0), (2000, 'Mouse', 25.0), (3000, 'Monitor', 300.0);"))
        conn.execute(text("INSERT INTO t_orders VALUES (1, 100, 10, 1000, 1200.0), (2, 200, 20, 2000, 50.0), (3, 300, 30, 3000, 600.0), (4, 100, 10, 2000, 25.0);"))
        conn.commit()
    return engine


def test_star_join_multiset_equivalence(memory_db_engine):
    """
    Test Star Join topology: Central fact table `t_orders` joined with `t_custs`, `t_emps`, and `t_prods`.
    Asserts exact relational multiset equality of rows before and after optimization.
    """
    sql = (
        "SELECT o.order_id, c.city, e.emp_name, p.title, o.amount "
        "FROM t_orders o "
        "JOIN t_custs c ON o.cust_id = c.cust_id "
        "JOIN t_emps e ON o.emp_id = e.emp_id "
        "JOIN t_prods p ON o.prod_id = p.prod_id "
        "WHERE o.amount > 30.0;"
    )
    plan = CostBasedJoinOptimizer.optimize_query(sql, engine=memory_db_engine)
    opt_sql = plan.optimized_sql or sql

    res_orig = ExecutionSandboxService.execute_query(memory_db_engine, sql)
    res_opt = ExecutionSandboxService.execute_query(memory_db_engine, opt_sql)

    assert res_orig.success and res_opt.success
    assert res_orig.row_count == res_opt.row_count

    orig_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in res_orig.rows]
    opt_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in res_opt.rows]
    assert Counter(orig_tuples) == Counter(opt_tuples)


def test_chain_join_multiset_equivalence(memory_db_engine):
    """
    Test Chain Join topology: `t_depts` -> `t_emps` -> `t_orders` -> `t_custs`.
    Asserts exact relational multiset equality of rows before and after optimization.
    """
    sql = (
        "SELECT d.name, e.emp_name, o.amount, c.city "
        "FROM t_depts d "
        "JOIN t_emps e ON d.dept_id = e.dept_id "
        "JOIN t_orders o ON e.emp_id = o.emp_id "
        "JOIN t_custs c ON o.cust_id = c.cust_id;"
    )
    plan = CostBasedJoinOptimizer.optimize_query(sql, engine=memory_db_engine)
    opt_sql = plan.optimized_sql or sql

    res_orig = ExecutionSandboxService.execute_query(memory_db_engine, sql)
    res_opt = ExecutionSandboxService.execute_query(memory_db_engine, opt_sql)

    assert res_orig.success and res_opt.success
    orig_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in res_orig.rows]
    opt_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in res_opt.rows]
    assert Counter(orig_tuples) == Counter(opt_tuples)


def test_filtered_join_multiset_equivalence(memory_db_engine):
    """
    Test Filtered Join with selective predicate pushdown compatibility.
    """
    sql = (
        "SELECT c.cust_id, c.city, p.title "
        "FROM t_custs c "
        "JOIN t_orders o ON c.cust_id = o.cust_id "
        "JOIN t_prods p ON o.prod_id = p.prod_id "
        "WHERE c.city = 'NY' AND p.price >= 500.0;"
    )
    plan = CostBasedJoinOptimizer.optimize_query(sql, engine=memory_db_engine)
    opt_sql = plan.optimized_sql or sql

    res_orig = ExecutionSandboxService.execute_query(memory_db_engine, sql)
    res_opt = ExecutionSandboxService.execute_query(memory_db_engine, opt_sql)

    assert res_orig.success and res_opt.success
    assert res_orig.row_count == 1
    assert res_opt.row_count == 1
    assert res_orig.rows[0]["title"] == res_opt.rows[0]["title"]
