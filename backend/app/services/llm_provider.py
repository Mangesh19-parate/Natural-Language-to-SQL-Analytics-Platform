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
        elif "failing sql query" in prompt_lower:
            # Self-correction repair prompt handler
            failing_sql_match = re.search(r"failing sql query.*?\n(.*?)\n\n", user_prompt, re.DOTALL | re.IGNORECASE)
            failing_sql = failing_sql_match.group(1).strip() if failing_sql_match else user_prompt
            
            # Common repair heuristics for mock mode across E1..E6
            repaired = re.sub(r"\bform\b", "FROM", failing_sql, flags=re.IGNORECASE)
            repaired = re.sub(r"\bselect\s+name\s+from\s+customers\b", "SELECT customer_name FROM customers", repaired, flags=re.IGNORECASE)
            repaired = re.sub(r"\bselect\s+emp_salary\b", "SELECT salary", repaired, flags=re.IGNORECASE)
            repaired = re.sub(r"\bselect\s+dept_name\b", "SELECT department_name", repaired, flags=re.IGNORECASE)
            repaired = re.sub(r"\bselect\s+product_cost\b", "SELECT unit_price", repaired, flags=re.IGNORECASE)
            
            # E3 Type mismatch repair
            repaired = re.sub(r"where\s+department_id\s*=\s*'abc'", "WHERE department_id = 1", repaired, flags=re.IGNORECASE)
            
            # E4 Semantic/Logic repair (e.g. missing GROUP BY)
            if "group by" in user_prompt.lower() and "group by" not in repaired.lower():
                if "department_name" in repaired:
                    repaired = repaired.rstrip(";") + " GROUP BY department_name;"
            
            # E6 Resource/Timeout repair (e.g. unconstrained Cartesian join or missing limit)
            if "cartesian" in user_prompt.lower() or "timeout" in user_prompt.lower():
                if "cross join" in repaired.lower():
                    repaired = re.sub(r"\bcross join\s+employees\b", "JOIN employees ON departments.department_id = employees.department_id", repaired, flags=re.IGNORECASE)
                elif "limit" not in repaired.lower():
                    repaired = repaired.rstrip(";") + " LIMIT 100;"

            return f"```sql\n{repaired}\n```"
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

    @classmethod
    def generate_completion(cls, prompt: str, system_prompt: str = "", temperature: float = 0.0) -> str:
        """Synchronous completion helper for prompt repair loops."""
        service = cls(provider="mock")
        return service._generate_mock_response(prompt)


LLMProvider = LLMProviderService

