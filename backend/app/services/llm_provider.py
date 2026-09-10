import hashlib
import json
import time
from typing import Dict, Any, Optional
from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    prompt_hash: str
    response_hash: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model_name: str

    model_config = {"protected_namespaces": ()}


class LLMProviderService:
    """
    LLM Client Provider Interface with SHA-256 Hashed Auditing (Rule R5.3 / SEC-12).
    Never logs raw prompts/completions into main audit records.
    """

    def __init__(self, provider: str = "mock", model_name: str = "gpt-4o-mini", api_key: Optional[str] = None):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key

    @staticmethod
    def hash_text(text: str) -> str:
        """Computes SHA-256 hash for privacy-safe storage."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> LLMResponse:
        """
        Executes generation call and returns content alongside audited hashes and metrics.
        """
        full_input = f"{system_prompt}\n---\n{user_prompt}"
        prompt_hash = self.hash_text(full_input)
        start_time = time.time()

        if self.provider == "mock":
            # Deterministic mock response for offline development and testing
            content = json.dumps({
                "sql": "SELECT COUNT(*) FROM employees;",
                "rationale": "Mock SQL generated for smoke test."
            })
            prompt_tokens = len(full_input.split())
            completion_tokens = len(content.split())
            latency_ms = int((time.time() - start_time) * 1000)
            response_hash = self.hash_text(content)

            return LLMResponse(
                content=content,
                prompt_hash=prompt_hash,
                response_hash=response_hash,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                model_name=self.model_name
            )

        # For OpenAI / Groq / Gemini (future live providers)
        raise NotImplementedError(f"Provider '{self.provider}' not initialized with live credentials. Use 'mock' for testing.")
