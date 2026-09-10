import json
from typing import Optional
from app.schemas.catalog import SemanticCatalogResponse


class CatalogPromptBuilder:
    """
    Catalog-Only Prompt Builder (REQ-CATALOG-01 / Task T-09 / Rule R2.5).
    Builds system and user prompts exclusively from the policy-filtered Semantic Catalog.
    """

    SYSTEM_PROMPT_TEMPLATE = """You are an Intelligent SQL Assistant specialized in generating precise, safe SQL queries for business analytics.

DATABASE DIALECT: {dialect}

AVAILABLE SCHEMA CONTRACT (POLICY-FILTERED SEMANTIC CATALOG):
The following tables and columns are authorized for this session:
{catalog_schema_text}

RELATIONSHIP GRAPH:
{relationships_text}

BINDING CONSTRAINTS:
1. Generate only a valid SQL query using the tables and columns explicitly listed in the schema contract above.
2. Never invent tables or columns that do not appear in the catalog.
3. If an aggregation is required on a metric/monetary column, use appropriate SQL aggregates (SUM, AVG, COUNT, MIN, MAX).
4. Return your output strictly as a JSON object with this contract:
   {{
     "sql": "SELECT ...",
     "rationale": "Brief explanation of joins and filters chosen"
   }}
"""

    @classmethod
    def format_catalog_text(cls, catalog: SemanticCatalogResponse) -> str:
        lines = []
        if not catalog.tables:
            return "No tables authorized for this role."

        for t in catalog.tables:
            lines.append(f"Table: {t.table_name}")
            if t.description:
                lines.append(f"  Description: {t.description}")
            lines.append("  Columns:")
            for c in t.columns:
                col_desc = f"    - {c.column_name} ({c.data_type or 'TEXT'})"
                annotations = []
                if c.semantic_type:
                    annotations.append(f"type: {c.semantic_type}")
                if c.default_aggregation:
                    annotations.append(f"default_agg: {c.default_aggregation}")
                if c.sanitized_examples:
                    annotations.append(f"examples: {json.dumps(c.sanitized_examples)}")
                if c.description:
                    annotations.append(f"note: {c.description}")
                
                if annotations:
                    col_desc += f" [{', '.join(annotations)}]"
                lines.append(col_desc)
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def format_relationships_text(cls, catalog: SemanticCatalogResponse) -> str:
        lines = []
        found_fk = False
        for t in catalog.tables:
            for fk in t.foreign_keys:
                found_fk = True
                constrained = ", ".join(fk.get("constrained_columns", []))
                referred_tbl = fk.get("referred_table", "")
                referred_cols = ", ".join(fk.get("referred_columns", []))
                lines.append(f"- {t.table_name}.({constrained}) -> {referred_tbl}.({referred_cols})")
        if not found_fk:
            return "None documented."
        return "\n".join(lines)

    @classmethod
    def build_system_prompt(cls, catalog: SemanticCatalogResponse, dialect: str = "PostgreSQL") -> str:
        schema_text = cls.format_catalog_text(catalog)
        rel_text = cls.format_relationships_text(catalog)
        return cls.SYSTEM_PROMPT_TEMPLATE.format(
            dialect=dialect,
            catalog_schema_text=schema_text,
            relationships_text=rel_text
        )

    @classmethod
    def build_user_prompt(cls, nl_question: str) -> str:
        return f"User Question: {nl_question.strip()}"
