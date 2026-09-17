import random
from locust import HttpUser, task, between


class SQLAnalyticsUser(HttpUser):
    """
    Simulates high-concurrency analyst workflows against the Trust Engine API.
    Used for Locust load testing across 10, 25, 50, 100, and 250 concurrent virtual users.
    """
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Logs in or uses pre-generated test Bearer token."""
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test_load_token",
        }

    @task(4)
    def validate_sql_query(self):
        """Simulates SQL AST validation and Policy Gate check."""
        queries = [
            "SELECT employee_id, first_name, department_id FROM employees WHERE department_id = 1",
            "SELECT customer_id, customer_name, country FROM customers WHERE country = 'USA'",
            "SELECT product_id, product_name, unit_price FROM products WHERE unit_price > 50",
        ]
        payload = {
            "sql": random.choice(queries),
            "data_source_id": 1,
            "role_id": 4,
        }
        self.client.post("/api/sql/validate", json=payload, headers=self.headers, name="POST /api/sql/validate")

    @task(3)
    def optimize_join_plan(self):
        """Simulates Bitmask DP and Greedy Cost-Based Join Optimizer requests."""
        queries = [
            "SELECT * FROM employees e JOIN departments d ON e.department_id = d.department_id JOIN sales s ON e.employee_id = s.employee_id",
            "SELECT c.customer_name, o.order_date, p.product_name FROM customers c JOIN orders o ON c.customer_id = o.customer_id JOIN products p ON o.order_id = p.product_id",
        ]
        payload = {
            "sql": random.choice(queries),
            "data_source_id": 1,
            "max_allowed_cost": 500000.0,
        }
        self.client.post("/api/optimize/join-plan", json=payload, headers=self.headers, name="POST /api/optimize/join-plan")

    @task(2)
    def check_health(self):
        """Simulates lightweight health and metrics polling."""
        self.client.get("/api/health", name="GET /api/health")

    @task(1)
    def get_policies(self):
        """Simulates policy matrix inspection."""
        self.client.get("/api/policy", headers=self.headers, name="GET /api/policy")
