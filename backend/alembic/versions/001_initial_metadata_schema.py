"""Initial app metadata schema

Revision ID: 001_initial_metadata_schema
Revises: 
Create Date: 2026-09-10 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "001_initial_metadata_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. roles
    op.create_table(
        "roles",
        sa.Column("role_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_name", sa.String(50), nullable=False, unique=True),
    )

    # 2. users
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.role_id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 3. data_sources
    op.create_table(
        "data_sources",
        sa.Column("data_source_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("db_type", sa.String(20), nullable=False),
        sa.Column("host", sa.String(255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("database_name", sa.String(150), nullable=True),
        sa.Column("connection_role", sa.String(100), default="readonly_app_user"),
        sa.Column("secret_ref", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 4. data_policy
    op.create_table(
        "data_policy",
        sa.Column("policy_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.role_id"), nullable=False),
        sa.Column("data_source_id", sa.Integer(), sa.ForeignKey("data_sources.data_source_id"), nullable=False),
        sa.Column("table_name", sa.String(150), nullable=False),
        sa.Column("column_name", sa.String(150), nullable=True),
        sa.Column("access_level", sa.String(20), nullable=False, default="denied"),
        sa.Column("aggregate_allowed", sa.Boolean(), default=False),
        sa.Column("row_filter_sql", sa.Text(), nullable=True),
        sa.UniqueConstraint("role_id", "data_source_id", "table_name", "column_name", name="uq_data_policy"),
    )
    op.create_index("idx_data_policy_lookup", "data_policy", ["role_id", "data_source_id", "table_name"])

    # 5. semantic_catalog
    op.create_table(
        "semantic_catalog",
        sa.Column("catalog_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("data_source_id", sa.Integer(), sa.ForeignKey("data_sources.data_source_id"), nullable=False),
        sa.Column("table_name", sa.String(150), nullable=False),
        sa.Column("column_name", sa.String(150), nullable=False),
        sa.Column("data_type", sa.String(50), nullable=True),
        sa.Column("semantic_type", sa.String(50), nullable=True),
        sa.Column("sensitivity", sa.String(20), default="NONE"),
        sa.Column("default_aggregation", sa.String(20), nullable=True),
        sa.Column("sanitized_examples", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("data_source_id", "table_name", "column_name", name="uq_semantic_catalog"),
    )

    # 6. schema_snapshot
    op.create_table(
        "schema_snapshot",
        sa.Column("schema_snapshot_id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.Integer(), sa.ForeignKey("data_sources.data_source_id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("schema_json", sa.JSON(), nullable=False),
    )

    # 7. sessions
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("data_source_id", sa.Integer(), sa.ForeignKey("data_sources.data_source_id"), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("active_dataset", sa.String(150), nullable=True),
        sa.Column("active_filters", sa.JSON(), nullable=True),
        sa.Column("time_context", sa.JSON(), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=True),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("turn_count", sa.Integer(), default=0),
        sa.Column("context_version", sa.Integer(), default=1),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )

    # 8. query_history
    op.create_table(
        "query_history",
        sa.Column("query_id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.session_id"), nullable=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True, index=True),
        sa.Column("nl_question", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=True),
        sa.Column("ambiguity_flag", sa.Boolean(), default=False),
        sa.Column("clarification_asked", sa.Text(), nullable=True),
        sa.Column("initial_sql", sa.Text(), nullable=True),
        sa.Column("final_sql", sa.Text(), nullable=True),
        sa.Column("dialect", sa.String(20), nullable=True),
        sa.Column("correction_count", sa.Integer(), default=0),
        sa.Column("error_type", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("execution_ms", sa.Integer(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("chart_type", sa.String(20), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("result_hash", sa.String(64), nullable=True),
        sa.Column("schema_snapshot_id", sa.String(36), sa.ForeignKey("schema_snapshot.schema_snapshot_id"), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("model_params", sa.JSON(), nullable=True),
        sa.Column("reliability_breakdown", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 9. sql_critic_findings
    op.create_table(
        "sql_critic_findings",
        sa.Column("finding_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_id", sa.String(36), sa.ForeignKey("query_history.query_id"), nullable=False),
        sa.Column("finding_type", sa.String(50), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("user_action", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 10. result_validation
    op.create_table(
        "result_validation",
        sa.Column("validation_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_id", sa.String(36), sa.ForeignKey("query_history.query_id"), nullable=False),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("expected_range", sa.String(100), nullable=True),
        sa.Column("observed_value", sa.String(100), nullable=True),
        sa.Column("severity", sa.String(10), default="info"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 11. optimization_suggestions
    op.create_table(
        "optimization_suggestions",
        sa.Column("suggestion_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_id", sa.String(36), sa.ForeignKey("query_history.query_id"), nullable=False),
        sa.Column("mode", sa.String(10), default="explain"),
        sa.Column("issue_type", sa.String(50), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(10), default="medium"),
        sa.Column("suggested_ddl", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 12. reports
    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.session_id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(20), default="single_query"),
        sa.Column("status", sa.String(20), default="ready"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 13. feedback
    op.create_table(
        "feedback",
        sa.Column("feedback_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_id", sa.String(36), sa.ForeignKey("query_history.query_id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("feedback_type", sa.String(30), nullable=True),
        sa.Column("expected_behavior", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 14. llm_call_log & encrypted_trace_store
    op.create_table(
        "llm_call_log",
        sa.Column("call_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_id", sa.String(36), sa.ForeignKey("query_history.query_id"), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("retry_number", sa.Integer(), default=0),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "encrypted_trace_store",
        sa.Column("trace_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("call_id", sa.Integer(), sa.ForeignKey("llm_call_log.call_id"), nullable=False),
        sa.Column("prompt_enc", sa.LargeBinary(), nullable=True),
        sa.Column("response_enc", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 15. security_attack_log
    op.create_table(
        "security_attack_log",
        sa.Column("attack_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False, index=True),
        sa.Column("attack_name", sa.String(150), nullable=False),
        sa.Column("attack_class", sa.String(30), nullable=False),
        sa.Column("input_payload", sa.Text(), nullable=True),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("blocked_at_stage", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 16. failure_log
    op.create_table(
        "failure_log",
        sa.Column("failure_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("query_id", sa.String(36), sa.ForeignKey("query_history.query_id"), nullable=True),
        sa.Column("failure_class", sa.String(30), nullable=False, index=True),
        sa.Column("problematic_phrase", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 17. evaluation_run & evaluation_result
    op.create_table(
        "evaluation_run",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("baseline_variant", sa.String(30), nullable=False),
        sa.Column("schema_snapshot_id", sa.String(36), sa.ForeignKey("schema_snapshot.schema_snapshot_id"), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "evaluation_result",
        sa.Column("result_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("evaluation_run.run_id"), nullable=False, index=True),
        sa.Column("question_id", sa.String(20), nullable=False),
        sa.Column("category", sa.String(30), nullable=False, index=True),
        sa.Column("execution_success", sa.Boolean(), default=False),
        sa.Column("result_correct", sa.Boolean(), default=False),
        sa.Column("error_type", sa.String(10), nullable=True),
        sa.Column("safety_violation", sa.Boolean(), default=False),
        sa.Column("unauthorized_exposure", sa.Boolean(), default=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_cost", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("evaluation_result")
    op.drop_table("evaluation_run")
    op.drop_table("failure_log")
    op.drop_table("security_attack_log")
    op.drop_table("encrypted_trace_store")
    op.drop_table("llm_call_log")
    op.drop_table("feedback")
    op.drop_table("reports")
    op.drop_table("optimization_suggestions")
    op.drop_table("result_validation")
    op.drop_table("sql_critic_findings")
    op.drop_table("query_history")
    op.drop_table("sessions")
    op.drop_table("schema_snapshot")
    op.drop_table("semantic_catalog")
    op.drop_table("data_policy")
    op.drop_table("data_sources")
    op.drop_table("users")
    op.drop_table("roles")
