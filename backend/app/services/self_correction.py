import difflib
import re
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.db.session import business_engine
from app.schemas.query import (
    ErrorTaxonomyType,
    CorrectionAttempt,
    SelfCorrectionResult,
)
from app.services.llm_provider import LLMProvider
from app.services.policy_engine import PolicyEngine
from app.services.execution_sandbox import ExecutionSandboxService
from app.services.prompt_builder import CatalogPromptBuilder
from app.services.semantic_catalog_service import SemanticCatalogService
from app.services.sql_critic import SQLCriticService


class SelfCorrectionService:
    """
    Self-Correction Loop & E1–E7 Error Taxonomy Engine (REQ-CORR-01, REQ-CORR-02, Rule R4.2).
    
    Taxonomy:
      E1: Syntax error
      E2: Schema-reference error
      E3: Type mismatch
      E4: Semantic / Logic error
      E5: Authorization error -> Rule R4.2: NEVER retried by regenerating SQL.
      E6: Timeout / Resource limit
      E7: Empty-result ambiguity
    """

    @classmethod
    def classify_error(
        cls,
        error_message: str,
        is_policy_rejection: bool = False,
        is_timeout: bool = False,
        is_empty_result: bool = False,
    ) -> ErrorTaxonomyType:
        """Deterministically classifies any error string or condition into E1..E7."""
        msg = (error_message or "").strip().lower()

        # E5: Authorization (Rule R4.2)
        if is_policy_rejection or any(
            k in msg
            for k in [
                "policy denied",
                "unauthorized",
                "aggregate not allowed",
                "not authorized",
                "row-level security",
                "permission denied",
                "access denied",
                "schema authorization",
                "column authorization",
                "high sensitivity",
            ]
        ):
            return ErrorTaxonomyType.E5_AUTHORIZATION

        # E6: Timeout / Resource Limit
        if is_timeout or any(
            k in msg
            for k in [
                "statement timeout",
                "querycancelederror",
                "canceling statement due to statement timeout",
                "timeout",
                "cartesian product",
                "resource limit",
                "cost threshold",
            ]
        ):
            return ErrorTaxonomyType.E6_TIMEOUT_RESOURCE

        # E7: Empty Result Ambiguity
        if is_empty_result or "empty result" in msg or "0 rows" in msg:
            return ErrorTaxonomyType.E7_EMPTY_RESULT_AMBIGUITY

        # E1: Syntax Error
        if any(
            k in msg
            for k in [
                "syntax error",
                "syntaxerror",
                "parseerror",
                "unexpected token",
                "unterminated quoted string",
                "token error",
                "invalid token",
                "mismatched parentheses",
            ]
        ):
            return ErrorTaxonomyType.E1_SYNTAX

        # E2: Schema-reference Error
        if any(
            k in msg
            for k in [
                "does not exist",
                "undefinedtable",
                "undefinedcolumn",
                "undefined_table",
                "undefined_column",
                "no such table",
                "no such column",
                "unknown column",
                "relation",
                "invalid reference",
            ]
        ):
            return ErrorTaxonomyType.E2_SCHEMA_REFERENCE

        # E3: Type Mismatch
        if any(
            k in msg
            for k in [
                "datatypemismatch",
                "cannot cast",
                "invalid input syntax",
                "operator does not exist",
                "type mismatch",
                "incompatible types",
                "cannot be cast to",
            ]
        ):
            return ErrorTaxonomyType.E3_TYPE_MISMATCH

        # E4: Semantic / Logic Error (GROUP BY missing, aggregate placement, etc.)
        if any(
            k in msg
            for k in [
                "group by",
                "groupingerror",
                "must appear in the group by",
                "aggregate functions are not allowed",
                "subquery must return only one column",
                "window function",
                "ambiguous column",
            ]
        ):
            return ErrorTaxonomyType.E4_SEMANTIC_LOGIC

        # Default to E4 Semantic/Logic
        return ErrorTaxonomyType.E4_SEMANTIC_LOGIC

    @classmethod
    def compute_sql_diff(cls, original_sql: str, repaired_sql: str) -> str:
        """Computes a unified line-by-line diff between original and repaired SQL."""
        orig_lines = original_sql.strip().splitlines(keepends=True)
        repaired_lines = repaired_sql.strip().splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            repaired_lines,
            fromfile="original.sql",
            tofile="repaired.sql",
            n=2,
        )
        return "".join(diff).strip() or "No textual diff detected"

    @classmethod
    def attempt_correction(
        cls,
        db: Session,
        original_question: str,
        failing_sql: str,
        error_message: str,
        data_source_id: int = 1,
        role_id: int = 4,
        max_retries: int = 3,
        is_policy_rejection: bool = False,
    ) -> SelfCorrectionResult:
        """
        Executes self-correction retry loop up to max_retries (REQ-CORR-01, REQ-CORR-02).
        Enforces Rule R4.2: E5 (authorization error) is NEVER retried.
        """
        error_type = cls.classify_error(error_message, is_policy_rejection=is_policy_rejection)

        # Rule R4.2: E5 (authorization) is NEVER retried by regenerating SQL
        if error_type == ErrorTaxonomyType.E5_AUTHORIZATION:
            return SelfCorrectionResult(
                recovered=False,
                final_sql=failing_sql,
                error_type=ErrorTaxonomyType.E5_AUTHORIZATION,
                retries_used=0,
                attempts=[],
                routed_as_policy_rejection=True,
                message=(
                    "Rule R4.2 Enforced: Authorization failures (E5) are never retried via SQL "
                    "regeneration. Routed back to user as a deterministic policy rejection."
                ),
            )

        attempts: List[CorrectionAttempt] = []
        current_sql = failing_sql
        current_error = error_message
        current_error_type = error_type

        # Build schema context for LLM repair
        catalog_obj = SemanticCatalogService.get_catalog_for_role(db, data_source_id=data_source_id, role_id=role_id)
        catalog_prompt = CatalogPromptBuilder.format_catalog_text(catalog_obj)

        for attempt_idx in range(1, max_retries + 1):
            # Prompt LLM for repair
            system_prompt = (
                "You are an expert SQL engineer performing automated self-correction.\n"
                "Your task is to fix a failing SQL query against the authorized database schema.\n\n"
                f"AUTHORIZED SCHEMA CONTEXT:\n{catalog_prompt}\n\n"
                "REPAIR RULES:\n"
                "1. Return ONLY the valid, corrected SELECT SQL query inside a ```sql ... ``` code block.\n"
                "2. Do NOT hallucinate tables or columns not present in the authorized schema.\n"
                "3. Ensure the fix directly resolves the specified error class."
            )

            user_prompt = (
                f"ORIGINAL NATURAL LANGUAGE QUESTION: {original_question}\n\n"
                f"FAILING SQL QUERY (Attempt {attempt_idx - 1 if attempt_idx > 1 else 'initial'}):\n"
                f"{current_sql}\n\n"
                f"ERROR TAXONOMY CLASS: {current_error_type.value}\n"
                f"DATABASE ERROR MESSAGE:\n{current_error}\n\n"
                "Please fix this SQL query to resolve the error and correctly answer the question."
            )

            try:
                raw_response = LLMProvider.generate_completion(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.0,
                )
                
                # Extract SQL from code block or raw string
                match = re.search(r"```sql\s*(.*?)\s*```", raw_response, re.DOTALL | re.IGNORECASE)
                candidate_sql = match.group(1).strip() if match else raw_response.strip()
                # Clean any stray markdown
                candidate_sql = candidate_sql.replace("```", "").strip()
            except Exception as e:
                candidate_sql = current_sql
                current_error = f"LLM generation failure: {str(e)}"

            diff_summary = cls.compute_sql_diff(current_sql, candidate_sql)

            # Re-validate candidate SQL through full Policy Engine
            policy_res = PolicyEngine.validate_sql(
                db=db,
                role_id=role_id,
                data_source_id=data_source_id,
                sql=candidate_sql,
            )

            if not policy_res.is_allowed:
                # Check if repair created an authorization error (E5)
                violation_msgs = [v.message for v in policy_res.violations]
                violation_str = "; ".join(violation_msgs) or "Policy validation failed"
                new_err_type = cls.classify_error(
                    violation_str,
                    is_policy_rejection=True,
                )
                attempt_record = CorrectionAttempt(
                    attempt_number=attempt_idx,
                    candidate_sql=candidate_sql,
                    error_type=new_err_type,
                    error_message=f"Policy rejection on retry: {violation_str}",
                    diff_summary=diff_summary,
                    policy_approved=False,
                    execution_success=False,
                )
                attempts.append(attempt_record)

                if new_err_type == ErrorTaxonomyType.E5_AUTHORIZATION:
                    # Halt on authorization breach
                    return SelfCorrectionResult(
                        recovered=False,
                        final_sql=candidate_sql,
                        error_type=ErrorTaxonomyType.E5_AUTHORIZATION,
                        retries_used=attempt_idx,
                        attempts=attempts,
                        routed_as_policy_rejection=True,
                        message="Self-correction attempt produced an unauthorized query (E5). Retries halted.",
                    )

                current_sql = candidate_sql
                current_error = violation_str
                current_error_type = new_err_type
                continue

            # Re-validate candidate SQL through full Policy Engine and SQL Critic
            target_sql = policy_res.injected_sql or candidate_sql
            critic_analysis = SQLCriticService.critique_sql(
                db=db,
                data_source_id=data_source_id,
                sql=target_sql,
            )

            # Policy approved -> Test candidate in sandbox execution
            exec_res = ExecutionSandboxService.execute_query(
                engine=business_engine,
                sql=target_sql,
                timeout_seconds=10.0,
                max_rows=10000,
            )

            if exec_res.success:
                # Successfully repaired and executed!
                attempts.append(
                    CorrectionAttempt(
                        attempt_number=attempt_idx,
                        candidate_sql=candidate_sql,
                        error_type=current_error_type,
                        error_message="Execution succeeded without errors.",
                        diff_summary=diff_summary,
                        policy_approved=True,
                        execution_success=True,
                    )
                )
                return SelfCorrectionResult(
                    recovered=True,
                    final_sql=candidate_sql,
                    error_type=error_type,
                    retries_used=attempt_idx,
                    attempts=attempts,
                    routed_as_policy_rejection=False,
                    message=f"Successfully repaired SQL on attempt {attempt_idx} ({error_type.value} resolved).",
                )
            else:
                # Execution failed -> re-classify and iterate
                exec_error = exec_res.error or "Unknown execution failure"
                new_err_type = cls.classify_error(exec_error)
                attempts.append(
                    CorrectionAttempt(
                        attempt_number=attempt_idx,
                        candidate_sql=candidate_sql,
                        error_type=new_err_type,
                        error_message=exec_error,
                        diff_summary=diff_summary,
                        policy_approved=True,
                        execution_success=False,
                    )
                )
                current_sql = candidate_sql
                current_error = exec_error
                current_error_type = new_err_type

        # Exhausted retries
        return SelfCorrectionResult(
            recovered=False,
            final_sql=current_sql,
            error_type=error_type,
            retries_used=max_retries,
            attempts=attempts,
            routed_as_policy_rejection=False,
            message=f"Self-correction exhausted max retries ({max_retries}) without successful execution.",
        )
