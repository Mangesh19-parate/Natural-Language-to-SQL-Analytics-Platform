import pytest
from hypothesis import given, strategies as st, settings
from app.services.dag_validator import DAGValidator, DAGValidationError
from app.schemas.agent import PlanSubTask


@st.composite
def random_dag_strategy(draw):
    """
    Generates arbitrary valid Directed Acyclic Graphs (DAGs)
    with N nodes (2 to 20) and randomized forward-pointing directed edges.
    """
    n_nodes = draw(st.integers(min_value=2, max_value=20))
    node_ids = list(range(1, n_nodes + 1))
    
    # Forward-pointing directed edges (u -> v where u < v) guarantees acyclicity
    edges = []
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            if draw(st.booleans()):
                edges.append((node_ids[i], node_ids[j]))
    
    # Build PlanSubTask objects
    subtasks = []
    for uid in node_ids:
        deps = [u for (u, v) in edges if v == uid]
        subtasks.append(PlanSubTask(
            step_id=uid,
            task_name=f"Analytical Task {uid}",
            sub_question=f"Compute metric {uid}",
            description=f"Detailed analytical task description {uid}",
            sql_intent=f"SELECT * FROM sales WHERE id = {uid}",
            dependencies=deps,
        ))
    
    return node_ids, edges, subtasks


@settings(max_examples=50, deadline=None)
@given(random_dag_strategy())
def test_property_kahn_topological_sort_validity(dag_data):
    """
    Property 1: For ANY generated DAG, Kahn's algorithm MUST:
    1. Produce a complete topological sort of all nodes without omission.
    2. Satisfy the topological invariant: for every directed edge (u, v),
       index_of(u) < index_of(v) in the output ordering.
    """
    node_ids, edges, subtasks = dag_data
    
    ordered_tasks = DAGValidator.validate_and_order_dag(subtasks)
    ordered_ids = [t.step_id for t in ordered_tasks]
    
    # Invariant 1: All nodes must be present in the output
    assert len(ordered_ids) == len(node_ids)
    assert set(ordered_ids) == set(node_ids)
    
    # Invariant 2: Topological precedence
    pos_map = {step_id: idx for idx, step_id in enumerate(ordered_ids)}
    for u, v in edges:
        assert pos_map[u] < pos_map[v], f"Topological violation: {u} (pos {pos_map[u]}) must precede {v} (pos {pos_map[v]})"


@settings(max_examples=50, deadline=None)
@given(random_dag_strategy())
def test_property_kahn_cycle_detection(dag_data):
    """
    Property 2: Injecting a backward edge (j -> i where i < j) that forms a cycle
    MUST cause Kahn's algorithm to detect the cycle and raise DAGValidationError.
    """
    node_ids, edges, subtasks = dag_data
    if len(subtasks) < 2:
        return

    # Add a direct cycle: step_1 depends on step_{last} while step_{last} depends on step_1
    first_task = subtasks[0]
    last_task = subtasks[-1]
    
    first_task.dependencies.append(last_task.step_id)
    last_task.dependencies.append(first_task.step_id)

    with pytest.raises(DAGValidationError, match=r"Cyclic dependency detected"):
        DAGValidator.validate_and_order_dag(subtasks)
