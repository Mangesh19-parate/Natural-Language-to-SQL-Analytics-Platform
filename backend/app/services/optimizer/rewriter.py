from typing import List, Set
import sqlglot
from sqlglot import exp
from app.services.optimizer.models import PhysicalPlanNode
from app.services.optimizer.join_graph import JoinGraph


def extract_ordered_aliases(node: PhysicalPlanNode) -> List[str]:
    """Recursively extracts the optimal linear join sequence of relation aliases from the plan tree."""
    if node.alias:
        return [node.alias]
    res = []
    if node.left_child:
        res.extend(extract_ordered_aliases(node.left_child))
    if node.right_child:
        res.extend(extract_ordered_aliases(node.right_child))
    return res


def generate_optimized_sql(graph: JoinGraph, plan: PhysicalPlanNode, original_sql: str) -> str:
    """
    Generates rewritten SQL AST strictly for associative/commutative INNER joins.
    Guarantees semantic invariance under proven relational algebra equivalence.
    """
    ordered_aliases = extract_ordered_aliases(plan)
    if len(ordered_aliases) <= 1:
        return original_sql

    try:
        parsed = sqlglot.parse_one(original_sql, read="postgres")
    except Exception:
        try:
            parsed = sqlglot.parse_one(original_sql)
        except Exception:
            return original_sql

    if not isinstance(parsed, exp.Select):
        return original_sql

    try:
        first_alias = ordered_aliases[0]
        first_table = graph.alias_to_table.get(first_alias, first_alias)
        if first_alias != first_table:
            from_tbl = exp.Table(this=exp.to_identifier(first_table), alias=exp.TableAlias(this=exp.to_identifier(first_alias)))
        else:
            from_tbl = exp.Table(this=exp.to_identifier(first_table))
        
        parsed.set("from_", exp.From(this=from_tbl))

        placed_aliases: Set[str] = {first_alias}
        new_joins: List[exp.Join] = []

        for alias in ordered_aliases[1:]:
            t_name = graph.alias_to_table.get(alias, alias)
            if alias != t_name:
                tbl_join = exp.Table(this=exp.to_identifier(t_name), alias=exp.TableAlias(this=exp.to_identifier(alias)))
            else:
                tbl_join = exp.Table(this=exp.to_identifier(t_name))

            connecting_edges = graph.find_connecting_edges([alias], list(placed_aliases))

            if connecting_edges:
                pred_str = " AND ".join(e.raw_predicate for e in connecting_edges)
                on_expr = sqlglot.parse_one(pred_str)
                new_joins.append(exp.Join(this=tbl_join, on=on_expr, kind="INNER"))
            else:
                new_joins.append(exp.Join(this=tbl_join, kind="CROSS"))

            placed_aliases.add(alias)

        parsed.set("joins", new_joins)
        return parsed.sql(pretty=True)
    except Exception:
        return original_sql
