import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

# Compatibility helper for JSON column across Postgres and SQLite
JsonColumn = JSON().with_variant(JSONB, "postgresql")
UUIDColumn = String(36)  # Store as string in SQLite, or UUID in Postgres


class DataSource(Base):
    __tablename__ = "data_sources"

    data_source_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    db_type = Column(String(20), nullable=False)  # 'postgresql' | 'mysql' | 'sqlite'
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    database_name = Column(String(150), nullable=True)
    connection_role = Column(String(100), default="readonly_app_user")
    secret_ref = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    policies = relationship("DataPolicy", back_populates="data_source")
    catalog_entries = relationship("SemanticCatalog", back_populates="data_source")
    snapshots = relationship("SchemaSnapshot", back_populates="data_source")
    sessions = relationship("SessionModel", back_populates="data_source")


class DataPolicy(Base):
    """
    DATA POLICY — fail-closed replacement for v1.1's dataset_access.
    No row for a given (role, table) = ZERO ACCESS.
    """
    __tablename__ = "data_policy"

    policy_id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.data_source_id"), nullable=False)
    table_name = Column(String(150), nullable=False)
    column_name = Column(String(150), nullable=True)  # NULL = applies to all columns of the table
    access_level = Column(String(20), nullable=False, default="denied")  # 'denied' | 'read' | 'read_aggregate_only'
    aggregate_allowed = Column(Boolean, default=False)
    row_filter_sql = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("role_id", "data_source_id", "table_name", "column_name", name="uq_data_policy"),
        Index("idx_data_policy_lookup", "role_id", "data_source_id", "table_name"),
    )

    role = relationship("Role", back_populates="policies")
    data_source = relationship("DataSource", back_populates="policies")


class SemanticCatalog(Base):
    """
    SEMANTIC CATALOG — typed, sensitivity-tagged schema representation.
    This is the ONLY schema view ever sent to the LLM (REQ-CATALOG-01).
    """
    __tablename__ = "semantic_catalog"

    catalog_id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.data_source_id"), nullable=False)
    table_name = Column(String(150), nullable=False)
    column_name = Column(String(150), nullable=False)
    data_type = Column(String(50), nullable=True)
    semantic_type = Column(String(50), nullable=True)  # 'monetary' | 'identifier' | 'categorical' | 'temporal' | 'metric' | 'text'
    sensitivity = Column(String(20), default="NONE")  # 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'
    default_aggregation = Column(String(20), nullable=True)  # 'SUM' | 'AVG' | 'COUNT' | NULL
    sanitized_examples = Column(JsonColumn, nullable=True)
    description = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("data_source_id", "table_name", "column_name", name="uq_semantic_catalog"),
    )

    data_source = relationship("DataSource", back_populates="catalog_entries")


class SchemaSnapshot(Base):
    """
    SCHEMA SNAPSHOTS — reproducibility (REQ-VER-01 / REQ-REPLAY-01).
    """
    __tablename__ = "schema_snapshot"

    schema_snapshot_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    data_source_id = Column(Integer, ForeignKey("data_sources.data_source_id"), nullable=False)
    captured_at = Column(DateTime, server_default=func.now())
    schema_json = Column(JsonColumn, nullable=False)

    data_source = relationship("DataSource", back_populates="snapshots")
    queries = relationship("QueryHistory", back_populates="schema_snapshot")
    evaluation_runs = relationship("EvaluationRun", back_populates="schema_snapshot")
