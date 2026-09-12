import hashlib
import json
import re
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

    def _generate_mock_response(self, user_prompt: str) -> str:
        """Produces contextual mock SQL based on question content for testing."""
        prompt_lower = user_prompt.lower()

        if "how many employees" in prompt_lower or "count of employees" in prompt_lower:
            return json.dumps({
                "sql": "SELECT COUNT(*) AS total_employees FROM employees;",
                "rationale": "Counting all rows in employees table"
            })
        elif "average salary" in prompt_lower or "avg salary" in prompt_lower:
            return json.dumps({
                "sql": "SELECT AVG(salary) AS avg_salary FROM employees;",
                "rationale": "Computing average salary across employees"
            })
        elif "top 5 customers" in prompt_lower or "top customers" in prompt_lower:
            return json.dumps({
                "sql": "SELECT customer_name, total_spent FROM customers ORDER BY total_spent DESC LIMIT 5;",
                "rationale": "Ordering customers by total_spent descending with limit 5"
            })
        elif "total sales" in prompt_lower or "sum of sales" in prompt_lower:
            return json.dumps({
                "sql": "SELECT SUM(sale_amount) AS total_revenue FROM sales;",
                "rationale": "Summing sale_amount from sales table"
            })
        elif "orders by status" in prompt_lower:
            return json.dumps({
                "sql": "SELECT status, COUNT(*) AS count FROM orders GROUP BY status;",
                "rationale": "Grouping orders by status with count"
            })
        elif "department" in prompt_lower and "employees" in prompt_lower:
            return json.dumps({
                "sql": "SELECT d.department_name, COUNT(e.employee_id) AS emp_count FROM departments d JOIN employees e ON d.department_id = e.department_id GROUP BY d.department_name;",
                "rationale": "Joining departments and employees on department_id and aggregating"
            })
        else:
            return json.dumps({
                "sql": "SELECT COUNT(*) FROM employees;",
                "rationale": "Default proposal for query"
            })

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> LLMResponse:
        """
        Executes generation call and returns content alongside audited hashes and metrics.
        """
        full_input = f"{system_prompt}\n---\n{user_prompt}"
        prompt_hash = self.hash_text(full_input)
        start_time = time.time()

        if self.provider == "mock":
            content = self._generate_mock_response(user_prompt)
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
