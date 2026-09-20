import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.services.data_source_manager import DataSourceManager, DataSourceUnavailableError
from app.services.storage_service import StorageService
from app.services.report_generator import ReportGeneratorService
from app.services.optimizer.stats_provider import TableStatsProvider
from app.services.evaluation_lab import EvaluationLabService
from app.schemas.report import ReportExportRequest, ReportQueryItem
from app.config import settings


def test_datasource_fail_closed_invariant(db_session: Session):
    """
    P0 Invariant: Requesting an unknown, inactive, or unresolvable data_source_id
    MUST raise DataSourceUnavailableError and NEVER fallback to business_engine.
    """
    # 1. Non-existent data source ID
    with pytest.raises(DataSourceUnavailableError) as exc_info:
        DataSourceManager.get_engine(db_session, data_source_id=99999)
    assert "99999" in str(exc_info.value)

    # 2. Non-default data source with no db session
    with pytest.raises(DataSourceUnavailableError):
        DataSourceManager.get_engine(None, data_source_id=42)

    # 3. Default business engine (ID 1) resolves correctly
    engine_1 = DataSourceManager.get_engine(db_session, data_source_id=1)
    assert engine_1 is not None


def test_report_storage_unification_invariant():
    """
    P0 Invariant: Report generator must persist artifacts via StorageService
    and return verifiable SHA-256 content hashes.
    """
    report_svc = ReportGeneratorService()
    req = ReportExportRequest(
        title="P0 Invariant Audit Report",
        scope="single",
        queries=[
            ReportQueryItem(
                question="List departments",
                executed_sql="SELECT * FROM departments;",
                status="success",
                reliability_score=95,
                columns=["department_id", "department_name"],
                rows=[{"department_id": 1, "department_name": "Engineering"}],
            )
        ],
    )
    report_id, file_path, content_hash = report_svc.generate_pdf(req, user_id=1)
    assert report_id is not None
    assert len(content_hash) == 64  # Valid SHA-256 hex string

    # Verify retrieval through StorageService
    storage = StorageService()
    artifact_bytes = storage.retrieve_artifact(f"reports/report_{report_id}.pdf")
    assert artifact_bytes is not None and len(artifact_bytes) > 0


def test_optimizer_stats_sha256_cache_key():
    """
    P0 Invariant: TableStatsProvider uses deterministic SHA-256 hashing
    for connection cache keys rather than Python process hash().
    """
    test_engine = create_engine("sqlite:///:memory:")
    key_1 = TableStatsProvider._get_cache_key(1, test_engine)
    key_2 = TableStatsProvider._get_cache_key(1, test_engine)
    assert key_1 == key_2
    assert key_1.startswith("ds_1:")
    assert len(key_1.split(":")[1]) == 16


def test_evaluation_benchmark_taxonomy_metadata():
    """
    P0 Invariant: Benchmark questions and metadata explicitly declare 100 ground-truth cases
    within the 165-case total evaluation suite.
    """
    questions = EvaluationLabService.get_benchmark_questions(full_suite=True)
    assert len(questions) == 165
    gt_cases = [q for q in questions if q.ground_truth_sql and q.ground_truth_sql.strip()]
    assert len(gt_cases) == 100


def test_optimizer_or_predicate_safety():
    """
    P0 Invariant: Optimizer MUST reject queries containing cross-table predicates inside OR/NOT
    and never extract them as independent join edges.
    """
    from app.services.optimizer.join_graph import JoinGraph
    
    # Query with cross-table condition inside OR branch
    sql = "SELECT * FROM customers c, orders o WHERE (c.customer_id = o.customer_id OR c.city = 'London')"
    graph = JoinGraph(sql)
    assert not graph.is_shape_supported
    assert graph.unsupported_reason == "CROSS_TABLE_OR_PREDICATE_UNSUPPORTED"
    assert len(graph.edges) == 0

    # Query with clean conjunctive equi-join is supported
    valid_sql = "SELECT * FROM customers c, orders o WHERE c.customer_id = o.customer_id AND c.city = 'London'"
    valid_graph = JoinGraph(valid_sql)
    assert valid_graph.is_shape_supported
    assert len(valid_graph.edges) == 1

