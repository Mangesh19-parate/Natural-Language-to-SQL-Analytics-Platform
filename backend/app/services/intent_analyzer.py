import re
from typing import Dict, List, Optional, Set, Tuple
from app.schemas.catalog import SemanticCatalogResponse
from app.schemas.intent import IntentClassification, IntentAnalysisResult, ClarificationOption
from app.services.ambiguity_engine import AmbiguityEngineService


class IntentAnalyzerService:
    """
    Intent Analyzer Service (REQ-UNSUPP-01 / REQ-AUTH-03 / Tasks T-10, T-11, T-12 / Rules R2.1, R2.2, R2.3, R2.4).
    Classifies questions into Answerable / Ambiguous / Unsupported / Unauthorized before SQL generation.
    """

    # Known domain keywords mapping to business tables
    KNOWN_TABLE_KEYWORDS = {
        "departments": {"department", "departments", "dept", "depts", "division", "divisions", "team", "teams"},
        "employees": {"employee", "employees", "staff", "worker", "workers", "hire", "hires", "personnel", "hired", "headcount", "salary", "salaries", "compensation", "wage", "wages", "pay", "payroll", "workforce"},
        "customers": {"customer", "customers", "client", "clients", "buyer", "buyers", "account", "accounts", "city", "cities", "location", "locations", "spend", "spent", "spending"},
        "products": {"product", "products", "item", "items", "sku", "skus", "category", "categories", "price", "prices", "catalog", "merchandise"},
        "orders": {"order", "orders", "purchase", "purchases", "invoice", "invoices", "transaction", "transactions", "bought", "placed", "date", "dates"},
        "sales": {"sale", "sales", "revenue", "revenues", "quantity", "quantities", "units", "sold", "volume", "turnover"},
    }

    # High sensitivity / restricted attribute tokens
    SENSITIVE_ATTRIBUTES = {
        "salary": {"salary", "compensation", "wage", "pay", "bonus", "earnings", "payroll"},
        "ssn": {"ssn", "social security", "tax id"},
        "pii": {"password", "secret", "token", "credit card", "bank account"},
    }

    # Known impossible / external domain keywords (evidence gap triggers)
    UNSUPPORTED_DOMAINS: Dict[str, List[str]] = {
        "supplier logistics and shipping": ["supplier", "shipping carrier", "freight", "logistics", "delivery tracking", "warehouse shelf", "vessel", "customs"],
        "marketing analytics": ["click-through rate", "ctr", "ad impressions", "marketing campaign", "google ads", "social media", "followers", "bounce rate"],
        "customer churn and lifetime value predictions": ["churn prediction", "churn probability", "risk of leaving", "lifetime value forecast", "propensity score"],
        "employee performance ratings": ["performance review", "kpi rating", "okr score", "disciplinary record", "appraisal score", "promotion eligibility"],
        "external financial markets": ["stock ticker", "market cap", "nasdaq", "sp500", "competitor market share", "share price", "crypto", "bitcoin"],
        "weather and environmental conditions": ["weather", "rainfall", "temperature", "climate", "humidity"],
        "customer support tickets": ["ticket response time", "helpdesk", "zendesk", "support resolution", "csat rating"],
        "cloud infrastructure telemetry": ["cpu utilization", "server latency", "memory leak", "aws billing", "docker container stats"]
    }

    @classmethod
    def check_unauthorized(
        cls,
        question: str,
        catalog: SemanticCatalogResponse
    ) -> Optional[Tuple[str, str]]:
        """
        Pre-check: Detects if the question targets tables/columns denied to the caller's role (Rule R2.3 / T-11).
        Returns (reasoning, denied_item) if unauthorized, else None.
        """
        # If the user has 0 accessible tables (e.g. unconfigured role)
        if not catalog.tables:
            return (
                "Access Denied: Your role has no permissions to query any data tables in this system.",
                "all_tables"
            )

        q_lower = question.lower()
        accessible_table_names = {t.table_name for t in catalog.tables}
        accessible_columns_by_table = {
            t.table_name: {c.column_name for c in t.columns}
            for t in catalog.tables
        }

        # 1. Check for table-level unauthorized access
        for tbl_name, keywords in cls.KNOWN_TABLE_KEYWORDS.items():
            if tbl_name not in accessible_table_names:
                for kw in keywords:
                    # Match whole words only
                    if re.search(r'\b' + re.escape(kw) + r'\b', q_lower):
                        return (
                            f"Access Denied: Your role does not have authorization to query the '{tbl_name}' table.",
                            tbl_name
                        )

        # 2. Check for column-level sensitivity denial (e.g. salary on employees)
        for sens_type, sens_keywords in cls.SENSITIVE_ATTRIBUTES.items():
            for skw in sens_keywords:
                if re.search(r'\b' + re.escape(skw) + r'\b', q_lower):
                    # Check if salary/compensation is accessible in any allowed table
                    has_salary_access = False
                    if "employees" in accessible_columns_by_table:
                        if "salary" in accessible_columns_by_table["employees"]:
                            has_salary_access = True
                    if not has_salary_access:
                        return (
                            f"Access Denied: Your role does not have permission to query sensitive '{sens_type}' data.",
                            sens_type
                        )

        return None

    @classmethod
    def check_unsupported(
        cls,
        question: str,
        catalog: SemanticCatalogResponse
    ) -> Optional[Tuple[str, str]]:
        """
        Detects if the question requests concepts outside the authorized schema (Rule R2.2 / T-10).
        Returns (reasoning, evidence_gap) if unsupported, else None.
        """
        q_lower = question.lower()
        available_tables_list = [t.table_name for t in catalog.tables]

        # 1. Match against known unsupported domain keywords
        for domain_name, triggers in cls.UNSUPPORTED_DOMAINS.items():
            for trig in triggers:
                if trig in q_lower:
                    return (
                        f"Cannot answer this question from the available database schema. Missing required evidence: {domain_name}.",
                        domain_name
                    )

        # 2. General out-of-domain heuristic: If no known entity keywords are matched
        matched_any_known = False
        for tbl_name, keywords in cls.KNOWN_TABLE_KEYWORDS.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', q_lower):
                    matched_any_known = True
                    break
            if matched_any_known:
                break

        # If question contains non-schema concepts like "CEO of Google", "weather in Paris", etc.
        out_of_scope_patterns = [
            r"\bwho is the (ceo|president|founder)\b",
            r"\bwhat is the (weather|capital|population|stock price)\b",
            r"\bhow to (cook|bake|fix|install)\b"
        ]
        for pattern in out_of_scope_patterns:
            if re.search(pattern, q_lower):
                return (
                    "Cannot answer this question from the business database. Missing required external entity knowledge.",
                    "external general knowledge"
                )

        if not matched_any_known and len(q_lower.split()) > 3:
            # Question has words but references zero known business concepts
            return (
                "Cannot answer this question. None of the requested concepts exist in the authorized business schema.",
                "unrecognized business domain entity"
            )

        return None

    @classmethod
    def classify_question(
        cls,
        question: str,
        catalog: SemanticCatalogResponse
    ) -> IntentAnalysisResult:
        available_tables = [t.table_name for t in catalog.tables]

        # Stage 1: Unauthorized Pre-Check (Rule R2.3 / T-11)
        unauth_check = cls.check_unauthorized(question, catalog)
        if unauth_check:
            reasoning, denied_item = unauth_check
            return IntentAnalysisResult(
                classification=IntentClassification.UNAUTHORIZED,
                confidence=1.0,
                reasoning=reasoning,
                evidence_gap=None,
                available_tables=available_tables,
                clarification_prompt=None,
                clarification_options=[],
                resolved_question=None
            )

        # Stage 2: Unsupported Domain Pre-Check (Rule R2.2 / T-10)
        unsupp_check = cls.check_unsupported(question, catalog)
        if unsupp_check:
            reasoning, evidence_gap = unsupp_check
            return IntentAnalysisResult(
                classification=IntentClassification.UNSUPPORTED,
                confidence=1.0,
                reasoning=reasoning,
                evidence_gap=evidence_gap,
                available_tables=available_tables,
                clarification_prompt=None,
                clarification_options=[],
                resolved_question=None
            )

        # Stage 3: Ambiguity Check (Rule R2.4 / T-12)
        ambig_check = AmbiguityEngineService.detect_ambiguity(question, catalog)
        if ambig_check:
            prompt, options = ambig_check
            return IntentAnalysisResult(
                classification=IntentClassification.AMBIGUOUS,
                confidence=0.85,
                reasoning="The query contains ambiguous metric or timeframe definitions. Clarification requested.",
                evidence_gap=None,
                available_tables=available_tables,
                clarification_prompt=prompt,
                clarification_options=options,
                resolved_question=None
            )

        # Stage 4: Answerable
        return IntentAnalysisResult(
            classification=IntentClassification.ANSWERABLE,
            confidence=1.0,
            reasoning="The question is unambiguous, authorized, and answerable from the Semantic Catalog.",
            evidence_gap=None,
            available_tables=available_tables,
            clarification_prompt=None,
            clarification_options=[],
            resolved_question=question.strip()
        )

    @classmethod
    def resolve_ambiguity(
        cls,
        original_question: str,
        selected_option: ClarificationOption
    ) -> str:
        """
        Resolves an ambiguous question into a clear, unambiguous natural-language prompt for the SQL Generator.
        """
        return f"{original_question.strip()} (Clarification: Calculate using '{selected_option.table_name}.{selected_option.column_name}' - {selected_option.label})"

