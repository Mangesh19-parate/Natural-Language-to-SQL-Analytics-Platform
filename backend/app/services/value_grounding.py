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

        # Sanitize identifiers against injection
        clean_table = table_name.replace('"', '').replace("'", "").replace(";", "").strip()
        clean_column = column_name.replace('"', '').replace("'", "").replace(";", "").strip()

        query_str = f'SELECT DISTINCT "{clean_column}" FROM "{clean_table}" WHERE "{clean_column}" IS NOT NULL LIMIT {max_examples}'
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(query_str))
                examples = []
                for row in result:
                    val = row[0]
                    if val is not None:
                        str_val = str(val).strip()
                        if str_val and str_val not in examples:
                            examples.append(str_val)
                return examples if examples else None
        except Exception:
            # On any DB error or unsupported dialect quotes, fallback safely to None
            return None
