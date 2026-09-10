from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import Engine
from app.schemas.catalog import SemanticCatalogResponse
from app.schemas.intent import IntentClassification, IntentAnalysisResult, ClarificationOption
from app.services.semantic_catalog_service import SemanticCatalogService
from app.services.intent_analyzer import IntentAnalyzerService
from app.services.ambiguity_engine import AmbiguityEngineService


class QueryClassifierService:
    """
    Query Classifier Orchestrator (Rules R2.1, R2.2, R2.3, R2.4 / Tasks T-10, T-11, T-12).
    Classifies every question into Answerable / Ambiguous / Unsupported / Unauthorized before SQL generation.
    """

    @classmethod
    def classify_question(
        cls,
        question: str,
        catalog: SemanticCatalogResponse
    ) -> IntentAnalysisResult:
        available_tables = [t.table_name for t in catalog.tables]

        # Stage 1: Unauthorized Pre-Check (Rule R2.3 / T-11)
        unauth_check = IntentAnalyzerService.check_unauthorized(question, catalog)
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
        unsupp_check = IntentAnalyzerService.check_unsupported(question, catalog)
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
