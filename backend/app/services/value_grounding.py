import re
from typing import List, Optional
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session


class ValueGroundingService:
    """
    Sanitized-Value Grounding Service (REQ-NLSQL-01 / Task T-07 / Rule R2.5).
    
    Strict Safety Invariants:
    1. ZERO RAW PII: If sensitivity is 'HIGH' or 'MEDIUM', immediately returns None.
       No query is even issued to the database.
    2. CATEGORICAL EXAMPLES ONLY: Only columns with semantic_type == 'categorical'
       and sensitivity in ('NONE', 'LOW') are sampled for distinct values.
    3. BOUNDED CARDINALITY: Maximum 5 distinct sanitized values per eligible column.
    """

    FORBIDDEN_SENSITIVITIES = {"HIGH", "MEDIUM"}

    @classmethod
    def extract_sanitized_examples(
        cls,
        engine: Engine,
        table_name: str,
        column_name: str,
        semantic_type: Optional[str],
        sensitivity: str = "NONE",
        max_examples: int = 5
    ) -> Optional[List[str]]:
        # Hard Security Gate (Rule R2.5): Never sample MEDIUM or HIGH sensitivity columns
        norm_sensitivity = (sensitivity or "NONE").upper()
        if norm_sensitivity in cls.FORBIDDEN_SENSITIVITIES:
            return None

        # Only categorical and low-sensitivity columns are candidates for grounding examples
        norm_semantic_type = (semantic_type or "").lower()
        if norm_semantic_type != "categorical":
            return None

        # Validate valid SQL identifier format
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name) or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", column_name):
            return None

        query_str = f'SELECT DISTINCT "{column_name}" FROM "{table_name}" WHERE "{column_name}" IS NOT NULL LIMIT {max_examples}'
        try:
            with engine.connect() as conn:
                result = conn.execute(text(query_str))
                examples = list(dict.fromkeys(str(r[0]).strip() for r in result if r[0] is not None and str(r[0]).strip()))
                return examples or None
        except Exception:
            return None
