import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.session import QueryHistory
from app.models.policy import SchemaSnapshot, SemanticCatalog, DataSource
from app.models.trust import SqlCriticFinding, ResultValidation
from app.schemas.replay import (
    SchemaDriftReport,
    ProvenancePackage,
    QueryReplayResponse,
)
from app.schemas.query import SQLExecuteResponse
from app.services.policy_engine import PolicyEngine
from app.services.execution_sandbox import ExecutionSandboxService
from app.services.sql_critic import SQLCriticService
from app.services.result_validator import ResultValidatorService
from app.services.reliability_scorer import ReliabilityScorerService
from app.services.chart_engine import ChartEngineService
from app.db.session import business_engine


class QueryReplayService:
    """
    Query Replay & Reproducibility Provenance Engine (REQ-REPLAY-01 / Day 81-82 / Milestone M3).
    Captures full execution provenance, detects schema drift, and verifies result reproducibility.
    """

    @staticmethod
    def introspect_full_schema(db: Session, data_source_id: int = 1) -> Dict[str, Any]:
        """
        Builds a canonical structured schema dictionary from the Semantic Catalog.
        """
        catalog_entries = (
            db.query(SemanticCatalog)
            .filter(SemanticCatalog.data_source_id == data_source_id)
            .all()
        )

        schema_dict: Dict[str, Any] = {"tables": {}}
        for entry in catalog_entries:
            tbl = entry.table_name
            if tbl not in schema_dict["tables"]:
                schema_dict["tables"][tbl] = {"columns": {}}
            schema_dict["tables"][tbl]["columns"][entry.column_name] = {
                "data_type": entry.data_type or "TEXT",
                "semantic_type": entry.semantic_type or "text",
                "sensitivity": entry.sensitivity or "NONE",
                "default_aggregation": entry.default_aggregation,
            }
        return schema_dict

    @staticmethod
    def capture_current_schema_snapshot(db: Session, data_source_id: int = 1) -> SchemaSnapshot:
        """
        Captures or retrieves the active schema snapshot for the given data source.
        """
        schema_dict = QueryReplayService.introspect_full_schema(db, data_source_id)

        # Check if there is an existing snapshot with the same hash/structure
        latest_snapshot = (
            db.query(SchemaSnapshot)
            .filter(SchemaSnapshot.data_source_id == data_source_id)
            .order_by(SchemaSnapshot.captured_at.desc())
            .first()
        )

        if latest_snapshot and latest_snapshot.schema_json == schema_dict:
            return latest_snapshot

        new_snapshot = SchemaSnapshot(
            schema_snapshot_id=str(uuid.uuid4()),
            data_source_id=data_source_id,
            schema_json=schema_dict,
        )
        db.add(new_snapshot)
        db.commit()
        db.refresh(new_snapshot)
        return new_snapshot

    @staticmethod
    def compute_result_hash(columns: List[str], rows: List[Dict[str, Any]]) -> str:
        """
        Calculates a deterministic SHA-256 fingerprint for query results (REQ-REPLAY-01).
        """
        data_representation = {
            "columns": sorted(columns),
            "rows": rows,
            "row_count": len(rows),
        }
        serialized = json.dumps(data_representation, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def detect_schema_drift(
        historical_schema: Optional[Dict[str, Any]],
        current_schema: Dict[str, Any],
        historical_snapshot_id: Optional[str] = None,
        captured_at: Optional[datetime] = None,
    ) -> SchemaDriftReport:
        """
        Detects structural or sensitivity differences between the historical run's schema snapshot
        and the active live schema (REQ-REPLAY-01 / Day 82).
        """
        if not historical_schema or not isinstance(historical_schema, dict) or "tables" not in historical_schema:
            return SchemaDriftReport(
                has_drift=False,
                drift_warning=None,
                historical_snapshot_id=historical_snapshot_id,
                historical_captured_at=captured_at,
                added_tables=[],
                removed_tables=[],
                modified_columns=[],
                sensitivity_changes=[],
                summary="No prior schema snapshot available for comparison (replaying against live schema).",
            )

        hist_tables = historical_schema.get("tables", {})
        curr_tables = current_schema.get("tables", {})

        added_tables = [t for t in curr_tables if t not in hist_tables]
        removed_tables = [t for t in hist_tables if t not in curr_tables]
        modified_columns = []
        sensitivity_changes = []

        for tbl_name, tbl_data in hist_tables.items():
            if tbl_name in curr_tables:
                hist_cols = tbl_data.get("columns", {})
                curr_cols = curr_tables[tbl_name].get("columns", {})

                for col_name, hist_col in hist_cols.items():
                    if col_name in curr_cols:
                        curr_col = curr_cols[col_name]
                        # Check data type change
                        if hist_col.get("data_type") != curr_col.get("data_type"):
                            modified_columns.append({
                                "table": tbl_name,
                                "column": col_name,
                                "old_type": hist_col.get("data_type"),
                                "new_type": curr_col.get("data_type"),
                            })
                        # Check sensitivity tag change
                        if hist_col.get("sensitivity") != curr_col.get("sensitivity"):
                            sensitivity_changes.append({
                                "table": tbl_name,
                                "column": col_name,
                                "old_sensitivity": hist_col.get("sensitivity"),
                                "new_sensitivity": curr_col.get("sensitivity"),
                            })
                    else:
                        modified_columns.append({
                            "table": tbl_name,
                            "column": col_name,
                            "change": "column_removed_in_live_schema",
                        })

        for tbl_name, tbl_data in curr_tables.items():
            if tbl_name in hist_tables:
                hist_cols = hist_tables[tbl_name].get("columns", {})
                curr_cols = tbl_data.get("columns", {})
                for col_name in curr_cols:
                    if col_name not in hist_cols:
                        modified_columns.append({
                            "table": tbl_name,
                            "column": col_name,
                            "change": "column_added_in_live_schema",
                        })

        has_drift = bool(added_tables or removed_tables or modified_columns or sensitivity_changes)
        
        warning_msg = None
        if has_drift:
            date_str = captured_at.strftime("%Y-%m-%d") if captured_at else "prior version"
            warning_msg = f"⚠ Schema has changed since this run ({date_str} → current) — results or authorization may differ."

        summary_parts = []
        if added_tables:
            summary_parts.append(f"+{len(added_tables)} tables added")
        if removed_tables:
            summary_parts.append(f"-{len(removed_tables)} tables removed")
        if modified_columns:
            summary_parts.append(f"{len(modified_columns)} columns modified/added/removed")
        if sensitivity_changes:
            summary_parts.append(f"{len(sensitivity_changes)} column sensitivity tags modified")

        summary_text = "; ".join(summary_parts) if summary_parts else "Live schema is identical to snapshot."

        return SchemaDriftReport(
            has_drift=has_drift,
            drift_warning=warning_msg,
            historical_snapshot_id=historical_snapshot_id,
            historical_captured_at=captured_at,
            added_tables=added_tables,
            removed_tables=removed_tables,
            modified_columns=modified_columns,
            sensitivity_changes=sensitivity_changes,
            summary=summary_text,
        )

    @staticmethod
    def get_provenance_package(db: Session, query_id: str, data_source_id: int = 1) -> ProvenancePackage:
        """
        Gathers full reproducibility package for a query run.
        """
        query_row = db.query(QueryHistory).filter(QueryHistory.query_id == query_id).first()
        if not query_row:
            raise ValueError(f"Query record {query_id} not found")

        # Fetch snapshot if exists
        snapshot = None
        if query_row.schema_snapshot_id:
            snapshot = (
                db.query(SchemaSnapshot)
                .filter(SchemaSnapshot.schema_snapshot_id == query_row.schema_snapshot_id)
                .first()
            )

        current_schema = QueryReplayService.introspect_full_schema(db, data_source_id)
        drift_report = QueryReplayService.detect_schema_drift(
            historical_schema=snapshot.schema_json if snapshot else None,
            current_schema=current_schema,
            historical_snapshot_id=snapshot.schema_snapshot_id if snapshot else None,
            captured_at=snapshot.captured_at if snapshot else None,
        )

        critic_findings = (
            db.query(SqlCriticFinding).filter(SqlCriticFinding.query_id == query_id).all()
        )
        validations = (
            db.query(ResultValidation).filter(ResultValidation.query_id == query_id).all()
        )

        return ProvenancePackage(
            query_id=query_row.query_id,
            nl_question=query_row.nl_question,
            final_sql=query_row.final_sql or query_row.initial_sql,
            dialect=query_row.dialect or "postgresql",
            schema_snapshot_id=query_row.schema_snapshot_id or (snapshot.schema_snapshot_id if snapshot else None),
            prompt_version=query_row.prompt_version or "v1.4",
            model_name=query_row.model_name or "gpt-4o-mini",
            model_params=query_row.model_params or {"temperature": 0.0, "max_tokens": 512},
            result_hash=query_row.result_hash,
            execution_ms=query_row.execution_ms,
            row_count=query_row.row_count,
            reliability_breakdown=query_row.reliability_breakdown,
            critic_summary=[
                {"finding_type": f.finding_type, "detail": f.detail, "user_action": f.user_action}
                for f in critic_findings
            ],
            validation_summary=[
                {"check_type": v.check_type, "severity": v.severity, "observed_value": v.observed_value}
                for v in validations
            ],
            created_at=query_row.created_at,
            drift_report=drift_report,
        )

    @staticmethod
    def replay_and_verify(
        db: Session,
        query_id: str,
        role_id: int = 1,
        data_source_id: int = 1,
        timeout_seconds: int = 10,
        max_rows: int = 1000,
    ) -> QueryReplayResponse:
        """
        Performs a full replayed execution and verifies exact result reproducibility (REQ-REPLAY-01).
        """
        provenance = QueryReplayService.get_provenance_package(db, query_id, data_source_id)
        sql_to_run = provenance.final_sql
        if not sql_to_run:
            raise ValueError(f"Query {query_id} has no executable SQL to replay")

        # Validate against Policy Engine
        policy_res = PolicyEngine.validate_sql(
            db=db,
            role_id=role_id,
            data_source_id=data_source_id,
            sql=sql_to_run,
        )

        if not policy_res.is_allowed:
            rel = ReliabilityScorerService.compute_reliability_score(
                db=db,
                sql=sql_to_run,
                role_id=role_id,
                data_source_id=data_source_id,
                policy_validation=policy_res,
                execution_success=False,
                row_count=0,
                latency_ms=0,
            )
            return QueryReplayResponse(
                query_id=query_id,
                provenance=provenance,
                replayed_execution=SQLExecuteResponse(
                    success=False,
                    sql=sql_to_run,
                    injected_sql=None,
                    columns=[],
                    rows=[],
                    row_count=0,
                    latency_ms=0,
                    truncated=False,
                    policy_validation=policy_res,
                    error=f"Replay rejected by Policy Engine: {'; '.join([v.message for v in policy_res.violations])}",
                    reliability_breakdown=rel,
                ),
                replayed_result_hash=None,
                is_reproducible=False,
                reproducibility_message="Replay failed: query is no longer authorized under current policy rules.",
            )

        exec_sql = policy_res.injected_sql or sql_to_run
        critic_res = SQLCriticService.critique_sql(
            db=db,
            data_source_id=data_source_id,
            sql=exec_sql,
        )

        sandbox_res = ExecutionSandboxService.execute_query(
            engine=business_engine,
            sql=exec_sql,
            timeout_seconds=timeout_seconds,
            max_rows=max_rows,
        )

        if sandbox_res.success:
            validation_report = ResultValidatorService.validate_results(
                db=db,
                sql=exec_sql,
                columns=sandbox_res.columns,
                rows=sandbox_res.rows,
                row_count=sandbox_res.row_count,
                query_id=query_id,
            )
            reliability = ReliabilityScorerService.compute_reliability_score(
                db=db,
                sql=exec_sql,
                role_id=role_id,
                data_source_id=data_source_id,
                policy_validation=policy_res,
                critic_analysis=critic_res,
                result_validation=validation_report,
                row_count=sandbox_res.row_count,
                latency_ms=sandbox_res.latency_ms,
                execution_success=True,
            )
            chart_spec = ChartEngineService.infer_chart_spec(
                columns=sandbox_res.columns,
                rows=sandbox_res.rows,
                question=provenance.nl_question,
            )

            new_result_hash = QueryReplayService.compute_result_hash(
                sandbox_res.columns, sandbox_res.rows
            )
            is_reproducible = (
                provenance.result_hash == new_result_hash
                if provenance.result_hash
                else True
            )

            if is_reproducible:
                msg = f"✓ Perfect reproducibility: result hash {new_result_hash[:8]} matches original run."
            else:
                msg = f"⚠ Result divergence: original hash ({provenance.result_hash[:8] if provenance.result_hash else 'N/A'}) differs from replayed hash ({new_result_hash[:8]})."

            return QueryReplayResponse(
                query_id=query_id,
                provenance=provenance,
                replayed_execution=SQLExecuteResponse(
                    success=True,
                    sql=sql_to_run,
                    injected_sql=exec_sql,
                    columns=sandbox_res.columns,
                    rows=sandbox_res.rows,
                    row_count=sandbox_res.row_count,
                    latency_ms=sandbox_res.latency_ms,
                    truncated=sandbox_res.truncated,
                    policy_validation=policy_res,
                    critic_analysis=critic_res,
                    result_validation=validation_report,
                    reliability_breakdown=reliability,
                    chart_spec=chart_spec,
                ),
                replayed_result_hash=new_result_hash,
                is_reproducible=is_reproducible,
                reproducibility_message=msg,
            )

        reliability = ReliabilityScorerService.compute_reliability_score(
            db=db,
            sql=exec_sql,
            role_id=role_id,
            data_source_id=data_source_id,
            policy_validation=policy_res,
            critic_analysis=critic_res,
            row_count=0,
            latency_ms=sandbox_res.latency_ms,
            execution_success=False,
        )
        return QueryReplayResponse(
            query_id=query_id,
            provenance=provenance,
            replayed_execution=SQLExecuteResponse(
                success=False,
                sql=sql_to_run,
                injected_sql=exec_sql,
                columns=[],
                rows=[],
                row_count=0,
                latency_ms=sandbox_res.latency_ms,
                truncated=False,
                policy_validation=policy_res,
                critic_analysis=critic_res,
                error=sandbox_res.error,
                reliability_breakdown=reliability,
            ),
            replayed_result_hash=None,
            is_reproducible=False,
            reproducibility_message=f"Replay execution failed: {sandbox_res.error}",
        )
