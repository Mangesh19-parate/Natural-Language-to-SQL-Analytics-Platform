import json
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.schemas.query import SQLProposal, SQLGenerateResponse
from app.services.semantic_catalog_service import SemanticCatalogService
from app.services.prompt_builder import CatalogPromptBuilder
from app.services.llm_provider import LLMProviderService
from app.services.policy_engine import PolicyEngine
from app.services.sql_critic import SQLCriticService
from app.services.reliability_scorer import ReliabilityScorerService


class SQLGeneratorService:
    """
    SQL Generator Service (REQ-NLSQL-04 / Task T-14 / Principle R0).
    
    Principle:
    "The LLM proposes. Deterministic infrastructure authorizes, critiques, executes, and verifies."
    
    Generates a candidate SQL proposal via the LLM provider using exclusively the
    policy-filtered Semantic Catalog, passes the proposal through the deterministic
    Policy Enforcement Engine, and evaluates semantic smells with the SQL Critic.
    """

    def __init__(self, llm_provider: Optional[LLMProviderService] = None):
        self.llm_provider = llm_provider or LLMProviderService(provider="mock")

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Safely extracts JSON object from LLM output string or markdown block."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                text = match.group(1)

        try:
            return json.loads(text)
        except Exception:
            return {
                "sql": text.strip().strip('"').strip("'"),
                "rationale": "Direct SQL response"
            }

    async def generate_sql_proposal(
        self,
        db: Session,
        question: str,
        role_id: int,
        data_source_id: int = 1,
        clarifications: Optional[Dict[str, Any]] = None,
    ) -> SQLGenerateResponse:
        """
        1. Retrieves role-scoped Semantic Catalog.
        2. Builds prompt.
        3. Invokes LLM.
        4. Validates proposed SQL against deterministic Policy Engine.
        5. Evaluates semantic smells with SQL Critic.
        6. Computes initial pre-execution Reliability Score (REQ-TRUST-01).
        """
        # Step 1: Policy-filtered catalog
        catalog = SemanticCatalogService.get_catalog_for_role(db, data_source_id=data_source_id, role_id=role_id)

        # Step 2: Build prompts
        system_prompt = CatalogPromptBuilder.build_system_prompt(catalog, dialect="PostgreSQL")
        user_prompt = CatalogPromptBuilder.build_user_prompt(question)
        if clarifications:
            user_prompt += f"\nClarifications Applied: {json.dumps(clarifications)}"

        # Step 3: LLM Generation
        llm_resp = await self.llm_provider.generate(system_prompt, user_prompt)
        parsed = self._extract_json(llm_resp.content)

        proposed_sql = parsed.get("sql", "").strip()
        rationale = parsed.get("rationale", "")

        proposal = SQLProposal(
            sql=proposed_sql,
            rationale=rationale,
            is_proposal=True
        )

        # Step 4: Deterministic Policy Validation Gate (Weeks 4-5)
        policy_result = PolicyEngine.validate_sql(
            db=db,
            role_id=role_id,
            data_source_id=data_source_id,
            sql=proposed_sql
        )

        # Step 5: SQL Critic Semantic-Smell Analysis (Week 6 / Task T-24 / Rule R3.1)
        critic_analysis = None
        if policy_result.is_allowed:
            critic_analysis = SQLCriticService.critique_sql(
                db=db,
                data_source_id=data_source_id,
                sql=policy_result.injected_sql or proposed_sql,
            )

        # Step 6: Initial Pre-execution Reliability Scoring (Week 8 / Task T-29 / Rule R3.3)
        reliability = ReliabilityScorerService.compute_reliability_score(
            db=db,
            sql=proposed_sql,
            role_id=role_id,
            data_source_id=data_source_id,
            policy_validation=policy_result,
            critic_analysis=critic_analysis,
            clarifications=clarifications,
            execution_success=policy_result.is_allowed,
            row_count=0,
            latency_ms=0,
        )

        rejection_reasons = [v.message for v in policy_result.violations]

        return SQLGenerateResponse(
            question=question,
            proposal=proposal,
            policy_validation=policy_result,
            critic_analysis=critic_analysis,
            reliability_breakdown=reliability,
            can_execute=policy_result.is_allowed,
            rejection_reasons=rejection_reasons,
        )
