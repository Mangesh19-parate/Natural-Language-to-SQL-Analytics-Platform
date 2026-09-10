import pytest
from app.services.llm_provider import LLMProviderService


@pytest.mark.asyncio
async def test_llm_provider_hashed_auditing():
    """
    Verifies Rule R5.3: LLM logs contain SHA-256 prompt and response hashes, not raw PII text.
    """
    provider = LLMProviderService(provider="mock", model_name="gpt-4o-mini")
    
    system_prompt = "You are a secure SQL assistant."
    user_prompt = "How many employees are in Engineering?"

    response = await provider.generate(system_prompt=system_prompt, user_prompt=user_prompt)

    # 1. Hashes must be valid 64-char SHA256 hex strings
    assert len(response.prompt_hash) == 64
    assert len(response.response_hash) == 64
    assert response.prompt_tokens > 0
    assert response.completion_tokens > 0
    assert response.latency_ms >= 0
    assert response.model_name == "gpt-4o-mini"

    # 2. Re-computing hash on identical input must yield exact match
    expected_prompt_hash = LLMProviderService.hash_text(f"{system_prompt}\n---\n{user_prompt}")
    assert response.prompt_hash == expected_prompt_hash
