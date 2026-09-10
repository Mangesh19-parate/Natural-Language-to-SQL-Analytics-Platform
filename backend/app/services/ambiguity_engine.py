import re
from typing import List, Optional, Dict, Tuple
from app.schemas.catalog import SemanticCatalogResponse
from app.schemas.intent import ClarificationOption


class AmbiguityEngineService:
    """
    Ambiguity Engine Service (REQ-NLSQL-02 / Task T-12 / Rules R2.1, R2.4, R5.5).
    Detects metric, dimensional, and temporal ambiguities in natural-language queries.
    Phrases targeted clarifying questions using concrete Semantic Catalog columns.
    """

    # Ambiguity pattern rules and their corresponding clarification options
    AMBIGUITY_RULES = [
        # 1. Revenue Ambiguity (orders.total_amount vs sales.revenue)
        {
            "id": "revenue_metric",
            "pattern": r"(revenue|turnover|sales figure|sales figures|sales amount)",
            "prompt": "We have two distinct revenue metrics available. Which metric would you like to calculate?",
            "options": [
                {
                    "option_id": "orders_total_amount",
                    "label": "Gross Order Total (orders.total_amount)",
                    "table_name": "orders",
                    "column_name": "total_amount",
                    "description": "Calculates revenue based on overall completed purchase invoice totals."
                },
                {
                    "option_id": "sales_revenue",
                    "label": "Net Item Revenue (sales.revenue)",
                    "table_name": "sales",
                    "column_name": "revenue",
                    "description": "Calculates revenue based on individual line-item product sales."
                }
            ]
        },
        # 2. Customer Spending Ambiguity (customers.total_spent vs orders.total_amount)
        {
            "id": "customer_spend_metric",
            "pattern": r"(top customer|biggest customer|best customer|customer spend|customer spending|customer purchases|spent the most|customer accounts)",
            "prompt": "How would you like to measure customer spend?",
            "options": [
                {
                    "option_id": "customers_total_spent",
                    "label": "Lifetime Spend (customers.total_spent)",
                    "table_name": "customers",
                    "column_name": "total_spent",
                    "description": "Uses the pre-aggregated historical customer total spend."
                },
                {
                    "option_id": "orders_sum_amount",
                    "label": "Sum of Orders (SUM(orders.total_amount))",
                    "table_name": "orders",
                    "column_name": "total_amount",
                    "description": "Aggregates specific order transaction values."
                }
            ]
        },
        # 3. Temporal Ambiguity ("recent", "latest", "past few months")
        {
            "id": "temporal_timeframe",
            "pattern": r"(recent|recently|latest|newest|past few days|past few weeks)",
            "prompt": "What specific timeframe should be considered for 'recent' data?",
            "options": [
                {
                    "option_id": "last_7_days",
                    "label": "Last 7 Days",
                    "table_name": "orders",
                    "column_name": "order_date",
                    "description": "Filters transactions placed within the past 7 days."
                },
                {
                    "option_id": "last_30_days",
                    "label": "Last 30 Days",
                    "table_name": "orders",
                    "column_name": "order_date",
                    "description": "Filters transactions placed within the past 30 days."
                },
                {
                    "option_id": "last_90_days",
                    "label": "Last Quarter (90 Days)",
                    "table_name": "orders",
                    "column_name": "order_date",
                    "description": "Filters transactions placed within the past 90 days."
                }
            ]
        },
        # 4. Product Value Ambiguity (products.price vs sales.revenue)
        {
            "id": "product_value",
            "pattern": r"(most expensive|highest price|expensive product|product value|top product by value|highest product price)",
            "prompt": "Would you like to analyze catalog unit price or total sales performance?",
            "options": [
                {
                    "option_id": "products_price",
                    "label": "Catalog Unit Price (products.price)",
                    "table_name": "products",
                    "column_name": "price",
                    "description": "Examines standard unit price in the product catalog."
                },
                {
                    "option_id": "sales_product_revenue",
                    "label": "Total Sales Revenue (sales.revenue)",
                    "table_name": "sales",
                    "column_name": "revenue",
                    "description": "Examines actual historical revenue generated by this product."
                }
            ]
        }
    ]

    @classmethod
    def detect_ambiguity(
        cls,
        question: str,
        catalog: SemanticCatalogResponse
    ) -> Optional[Tuple[str, List[ClarificationOption]]]:
        """
        Detects if a question has metric/temporal ambiguity that needs user disambiguation (Rule R2.4 / T-12).
        Returns (clarification_prompt, clarification_options) if ambiguous, else None.
        """
        q_lower = question.lower().strip()
        accessible_tables = {t.table_name for t in catalog.tables}

        for rule in cls.AMBIGUITY_RULES:
            if re.search(rule["pattern"], q_lower):
                # Filter options to ensure only options on authorized tables are offered
                valid_options = []
                for opt in rule["options"]:
                    if opt["table_name"] in accessible_tables:
                        valid_options.append(
                            ClarificationOption(
                                option_id=opt["option_id"],
                                label=opt["label"],
                                table_name=opt["table_name"],
                                column_name=opt["column_name"],
                                description=opt["description"]
                            )
                        )
                # If at least 2 valid alternative options exist for the authorized role, trigger clarification
                if len(valid_options) >= 2:
                    return rule["prompt"], valid_options

        return None
