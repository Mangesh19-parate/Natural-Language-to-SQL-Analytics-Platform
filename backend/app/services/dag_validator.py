from collections import deque
from typing import List, Dict, Tuple, Optional
from app.schemas.agent import PlanSubTask


class DAGValidationError(Exception):
    """Raised when an analytical DAG has cycles, invalid dependencies, or bad step contracts."""
    pass


class DAGValidator:
    """
    STRICT ANALYTICAL DAG VALIDATOR (Rule R6.1 / Task T-44).
    Validates analytical query decomposition DAGs before execution:
    - Cycle Detection (Topological sort using Kahn's algorithm)
    - Dependency Resolution (Ensures every dependency references a valid preceding step_id)
    - Structural Integrity (Non-empty steps, positive step IDs)
    """

    @classmethod
    def validate_and_order_dag(cls, sub_tasks: List[PlanSubTask]) -> List[PlanSubTask]:
        """
        Validates the DAG structure and returns the subtasks in topological execution order.
        Raises DAGValidationError if the graph is invalid or contains cycles.
        """
        if not sub_tasks:
            raise DAGValidationError("DAG is empty: At least one analytical sub-task required.")

        step_ids = {task.step_id for task in sub_tasks}
        if len(step_ids) != len(sub_tasks):
            raise DAGValidationError("Duplicate step_ids detected in DAG definition.")

        # Build adjacency graph and in-degree counts
        in_degree: Dict[int, int] = {task.step_id: 0 for task in sub_tasks}
        adj_list: Dict[int, List[int]] = {task.step_id: [] for task in sub_tasks}
        task_map: Dict[int, PlanSubTask] = {task.step_id: task for task in sub_tasks}

        for task in sub_tasks:
            for dep_id in task.dependencies:
                if dep_id not in step_ids:
                    raise DAGValidationError(
                        f"Step {task.step_id} ('{task.task_name}') references unknown dependency step_id {dep_id}."
                    )
                if dep_id == task.step_id:
                    raise DAGValidationError(f"Step {task.step_id} has a self-referential dependency.")
                adj_list[dep_id].append(task.step_id)
                in_degree[task.step_id] += 1

        # Kahn's algorithm for topological sorting and cycle detection (True O(V + E))
        queue: deque[int] = deque([step_id for step_id, deg in in_degree.items() if deg == 0])
        topological_order: List[PlanSubTask] = []

        while queue:
            curr = queue.popleft()
            topological_order.append(task_map[curr])

            for neighbor in adj_list[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(topological_order) != len(sub_tasks):
            raise DAGValidationError(
                "Cyclic dependency detected in Analytical DAG. Execution rejected by DAG safety gate."
            )

        return topological_order
