from locust import HttpUser, task, between


class SQLAssistantUser(HttpUser):
    """
    Locust Load Test Scenario (Task T-46 / REQ-PERF-01 / Week 14 P1).
    Simulates 50 concurrent analytical users executing real workloads against the API.
    """
    wait_time = between(0.5, 2.0)

    @task(3)
    def test_health_check(self):
        self.client.get("/api/health")

    @task(5)
    def test_intent_classification(self):
        payload = {
            "question": "Show top 5 customers by revenue",
            "role_id": 1,
            "data_source_id": 1
        }
        self.client.post("/api/intent/classify", json=payload)

    @task(4)
    def test_sql_generation_and_policy(self):
        payload = {
            "question": "What is total sales revenue?",
            "role_id": 1,
            "data_source_id": 1
        }
        self.client.post("/api/sql/generate", json=payload)

    @task(2)
    def test_failure_observatory_stats(self):
        self.client.get("/api/observatory/stats")

    @task(2)
    def test_query_history(self):
        self.client.get("/api/history?limit=10")

    @task(1)
    def test_compound_planner_agent(self):
        payload = {
            "question": "Compare revenue from 2023 vs 2024 and calculate growth",
            "role_id": 1,
            "data_source_id": 1
        }
        self.client.post("/api/agent/execute", json=payload)
