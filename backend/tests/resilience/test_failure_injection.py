import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.policy import DataSource
from app.services.llm_provider import LLMProviderService, LLMResponse
from app.services.execution_sandbox import ExecutionSandboxService
from app.services.optimizer import CostBasedJoinOptimizer
from app.schemas.optimize import GateDecisionEnum
from app.services.self_correction import SelfCorrectionService, ErrorTaxonomyType
from app.services.auth_service import AuthService
from tests.conftest import create_test_auth_headers


def test_failure_injection_llm_provider_error(db_session: Session):
    """
    Failure Injection 1: Simulates LLM upstream provider timeout / 503 error.
    Verifies that the orchestrator degrades cleanly, returns structured error proposal,
    and does not crash the API or execute empty strings.
    """
    ds = db_session.query(DataSource).filter(DataSource.data_source_id == 1).first()
    if not ds:
        ds = DataSource(data_source_id=1, name="Default DB", db_type="sqlite", secret_ref="local", is_active=True)
        db_session.add(ds)
        db_session.commit()

    headers = create_test_auth_headers(db_session, role_name="viewer", user_id=201)

    class FailingLLMProvider(LLMProviderService):
        async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
            return LLMResponse(
                content="",
                raw_response={},
                generation_mode="error",
                fallback_used=False,
                provider_error="Simulated upstream OpenAI 503 Service Unavailable",
                model_name="gpt-4o-mini",
                provider="mock-failing",
                prompt_hash="mock_p_hash",
                response_hash="mock_r_hash",
                prompt_tokens=10,
                completion_tokens=0,
                latency_ms=15,
            )

    from app.services.sql_generator import SQLGeneratorService
    generator = SQLGeneratorService(llm_provider=FailingLLMProvider())

    import asyncio
    resp = asyncio.run(generator.generate_sql_proposal(
        db=db_session,
        question="Show total revenue by department",
        role_id=4,
        data_source_id=1,
    ))

    assert resp.can_execute is False
    assert "LLM Provider Error" in resp.rejection_reasons[0]
    assert resp.proposal.is_proposal is False


def test_failure_injection_sandbox_query_timeout(db_session: Session):
    """
    Failure Injection 2: Simulates long-running query exceeding the sandbox timeout.
    Verifies that error classification maps timeout phrases to E6_TIMEOUT_RESOURCE.
    """
    err_type = SelfCorrectionService.classify_error("statement execution time exceeded timeout limit of 10.0s")
    assert err_type == ErrorTaxonomyType.E6_TIMEOUT_RESOURCE


def test_failure_injection_cartesian_runaway_query():
    """
    Failure Injection 3: Simulates malicious runaway Cartesian product query.
    Verifies that CostBasedJoinOptimizer intercepts the disconnected graph
    and assigns GateDecisionEnum.BLOCK_RUNAWAY_CARTESIAN before execution.
    """
    malicious_cartesian_sql = "SELECT * FROM employees e, departments d, sales s, customers c, orders o;"
    res = CostBasedJoinOptimizer.optimize_query(malicious_cartesian_sql)

    assert res.gate_decision == GateDecisionEnum.BLOCK_RUNAWAY_CARTESIAN
    assert "Cross join" in res.gate_reason or "Cartesian" in res.execution_recommendation
    assert res.naive_cost > 10000.0


def test_failure_injection_revoked_token_authentication(db_session: Session):
    """
    Failure Injection 4: Simulates presenting an explicitly revoked JWT token.
    Verifies that authentication fails closed with HTTP 401 Unauthorized.
    """
    client = TestClient(app)
    headers = create_test_auth_headers(db_session, role_name="admin", user_id=202)
    raw_token = headers["Authorization"].split("Bearer ")[1]

    # Explicitly revoke token
    AuthService.revoke_token(raw_token, db=db_session)

    # Calling authenticated endpoint must be denied
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 401
    assert "revoked" in resp.json()["detail"].lower() or "credentials" in resp.json()["detail"].lower()


def test_failure_injection_tampered_jwt_token(db_session: Session):
    """
    Failure Injection 5: Simulates presenting a tampered cryptographic signature.
    """
    client = TestClient(app)
    headers = create_test_auth_headers(db_session, role_name="admin", user_id=203)
    raw_token = headers["Authorization"].split("Bearer ")[1]
    
    tampered_token = raw_token[:-5] + "XXXXX"
    tampered_headers = {"Authorization": f"Bearer {tampered_token}"}

    resp = client.get("/api/auth/me", headers=tampered_headers)
    assert resp.status_code == 401
