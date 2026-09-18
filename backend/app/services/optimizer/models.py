from typing import List, Dict, Any, Optional
from app.schemas.optimize import JoinAlgorithmEnum


class CalibratedTableStats:
    """
    Table Statistics calibrated for cost-based query optimization.
    Stores live tuple counts, page estimates, PK/FK relationships, and exact indexed column sets.
    """
    def __init__(
        self,
        table_name: str,
        tuple_count: float,
        page_count: float,
        primary_key: str,
        indexes: List[str],
        index_columns: Optional[Dict[str, List[str]]] = None,
        foreign_keys: Optional[List[Dict[str, Any]]] = None,
        ndv_map: Optional[Dict[str, float]] = None,
        is_live: bool = True,
    ):
        self.table_name = table_name.lower()
        self.tuple_count = max(1.0, float(tuple_count))
        self.page_count = max(1.0, float(page_count))
        self.primary_key = primary_key.lower() if primary_key else "id"
        self.indexes = [idx.lower() for idx in indexes]
        self.index_columns = {
            idx.lower(): [c.lower() for c in cols]
            for idx, cols in (index_columns or {}).items()
        }
        self.foreign_keys = foreign_keys or []
        self.ndv_map = {k.lower(): max(1.0, float(v)) for k, v in (ndv_map or {}).items()}
        self.is_live = is_live


DEFAULT_TABLE_STATS: Dict[str, CalibratedTableStats] = {
    "customers": CalibratedTableStats(
        table_name="customers",
        tuple_count=150,
        page_count=2,
        primary_key="customer_id",
        indexes=["customers_pkey", "idx_customers_city"],
        index_columns={
            "customers_pkey": ["customer_id"],
            "idx_customers_city": ["city"],
        },
        ndv_map={"customer_id": 150.0, "city": 12.0, "total_spent": 140.0},
        is_live=False,
    ),
    "departments": CalibratedTableStats(
        table_name="departments",
        tuple_count=10,
        page_count=1,
        primary_key="department_id",
        indexes=["departments_pkey"],
        index_columns={"departments_pkey": ["department_id"]},
        ndv_map={"department_id": 10.0, "department_name": 10.0},
        is_live=False,
    ),
    "employees": CalibratedTableStats(
        table_name="employees",
        tuple_count=120,
        page_count=2,
        primary_key="employee_id",
        indexes=["employees_pkey", "idx_employees_dept"],
        index_columns={
            "employees_pkey": ["employee_id"],
            "idx_employees_dept": ["department_id"],
        },
        foreign_keys=[
            {"constrained_columns": ["department_id"], "referred_table": "departments", "referred_columns": ["department_id"]}
        ],
        ndv_map={"employee_id": 120.0, "department_id": 10.0, "salary": 95.0},
        is_live=False,
    ),
    "products": CalibratedTableStats(
        table_name="products",
        tuple_count=100,
        page_count=2,
        primary_key="product_id",
        indexes=["products_pkey", "idx_products_cat"],
        index_columns={
            "products_pkey": ["product_id"],
            "idx_products_cat": ["category"],
        },
        ndv_map={"product_id": 100.0, "category": 6.0, "price": 80.0},
        is_live=False,
    ),
    "orders": CalibratedTableStats(
        table_name="orders",
        tuple_count=200,
        page_count=3,
        primary_key="order_id",
        indexes=["orders_pkey", "idx_orders_customer"],
        index_columns={
            "orders_pkey": ["order_id"],
            "idx_orders_customer": ["customer_id"],
        },
        foreign_keys=[
            {"constrained_columns": ["customer_id"], "referred_table": "customers", "referred_columns": ["customer_id"]}
        ],
        ndv_map={"order_id": 200.0, "customer_id": 85.0, "total_amount": 180.0},
        is_live=False,
    ),
    "sales": CalibratedTableStats(
        table_name="sales",
        tuple_count=500,
        page_count=5,
        primary_key="sale_id",
        indexes=["sales_pkey", "idx_sales_order", "idx_sales_product"],
        index_columns={
            "sales_pkey": ["sale_id"],
            "idx_sales_order": ["order_id"],
            "idx_sales_product": ["product_id"],
        },
        foreign_keys=[
            {"constrained_columns": ["order_id"], "referred_table": "orders", "referred_columns": ["order_id"]},
            {"constrained_columns": ["product_id"], "referred_table": "products", "referred_columns": ["product_id"]},
        ],
        ndv_map={"sale_id": 500.0, "order_id": 200.0, "product_id": 100.0, "revenue": 420.0},
        is_live=False,
    ),
}


class JoinEdge:
    """Represents a join predicate between two table aliases."""
    def __init__(
        self,
        table1: str,
        col1: str,
        table2: str,
        col2: str,
        operator: str = "=",
        raw_predicate: str = "",
    ):
        self.table1 = table1.lower()
        self.col1 = col1.lower()
        self.table2 = table2.lower()
        self.col2 = col2.lower()
        self.operator = operator
        self.raw_predicate = raw_predicate

    def connects(self, t1: str, t2: str) -> bool:
        t1_l, t2_l = t1.lower(), t2.lower()
        return (self.table1 == t1_l and self.table2 == t2_l) or (self.table1 == t2_l and self.table2 == t1_l)


class PhysicalPlanNode:
    """An estimated physical plan node (Scan or Join) in the educational cost model."""
    def __init__(
        self,
        operator: JoinAlgorithmEnum,
        cardinality: float,
        cost: float,
        tables_mask: int,
        table_name: Optional[str] = None,
        alias: Optional[str] = None,
        join_predicate: Optional[str] = None,
        left_child: Optional['PhysicalPlanNode'] = None,
        right_child: Optional['PhysicalPlanNode'] = None,
    ):
        self.operator = operator
        self.cardinality = max(1.0, float(cardinality))
        self.cost = max(0.1, float(cost))
        self.tables_mask = tables_mask
        self.table_name = table_name
        self.alias = alias
        self.join_predicate = join_predicate
        self.left_child = left_child
        self.right_child = right_child

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator": self.operator.value,
            "table_name": self.table_name,
            "alias": self.alias,
            "join_predicate": self.join_predicate,
            "estimated_cardinality": round(self.cardinality, 1),
            "estimated_cost": round(self.cost, 2),
            "left": self.left_child.to_dict() if self.left_child else None,
            "right": self.right_child.to_dict() if self.right_child else None,
        }
