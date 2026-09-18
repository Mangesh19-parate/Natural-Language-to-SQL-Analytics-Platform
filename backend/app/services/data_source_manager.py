import os
import threading
import logging
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import business_engine, business_admin_engine

logger = logging.getLogger(__name__)


class DataSourceUnavailableError(Exception):
    """Raised when a requested data source cannot be found, is inactive, or fails connection resolution."""
    pass


class DataSourceConnectionManager:
    """
    Multi-Source Database Connection Manager & Engine Registry (Rule R0 / Multi-Tenant Isolation).
    Maintains isolated connection pools per data_source_id, resolves secrets securely,
    and guarantees fail-closed routing across heterogenous data sources.
    """
    _lock = threading.Lock()
    _engine_registry: Dict[int, Engine] = {}
    _admin_engine_registry: Dict[int, Engine] = {}

    @classmethod
    def get_engine(
        cls,
        db: Optional[Session] = None,
        data_source_id: int = 1,
        admin: bool = False,
    ) -> Engine:
        """
        Retrieves or initializes the SQLAlchemy Engine configured for a given data_source_id.
        Guarantees strict fail-closed isolation: never silently substitutes the default database.
        """
        registry = cls._admin_engine_registry if admin else cls._engine_registry

        # 1. Fast-path cached engine lookup
        if data_source_id in registry:
            return registry[data_source_id]

        with cls._lock:
            if data_source_id in registry:
                return registry[data_source_id]

            # 2. Default business data source (ID 1)
            if data_source_id == 1:
                engine = business_admin_engine if admin else business_engine
                registry[data_source_id] = engine
                return engine

            # 3. Fail-closed: DB session required to look up dynamic data sources
            if db is None:
                raise DataSourceUnavailableError(
                    f"Active database session required to resolve non-default data source ID {data_source_id}"
                )

            # 4. Dynamic lookup from DataSource metadata table
            from app.models.policy import DataSource
            ds_row = db.query(DataSource).filter(
                DataSource.data_source_id == data_source_id,
                DataSource.is_active.is_(True),
            ).first()

            if not ds_row:
                raise DataSourceUnavailableError(
                    f"Data source ID {data_source_id} not found or is inactive"
                )

            # Resolve connection string from secret_ref env or fields
            try:
                conn_url = cls._resolve_connection_url(ds_row, admin=admin)
                connect_args = {"check_same_thread": False} if "sqlite" in conn_url else {}
                engine = create_engine(
                    conn_url,
                    pool_pre_ping=True,
                    connect_args=connect_args,
                )
                registry[data_source_id] = engine
                logger.info(f"Initialized isolated engine pool for data_source_id={data_source_id} ({ds_row.name})")
                return engine
            except Exception as e:
                logger.error(f"Failed to initialize engine for data_source_id={data_source_id}: {e}")
                raise DataSourceUnavailableError(
                    f"Failed to initialize connection for data source ID {data_source_id}: {e}"
                ) from e

    @classmethod
    def _resolve_connection_url(cls, ds: Any, admin: bool = False) -> str:
        """Resolves full database URL from environment secrets or metadata record."""
        # 1. If secret_ref exists as environment variable or direct URL
        if ds.secret_ref:
            env_url = os.environ.get(ds.secret_ref)
            if env_url:
                return env_url
            if ds.secret_ref.startswith(("postgresql://", "sqlite://", "mysql://")):
                return ds.secret_ref
            raise DataSourceUnavailableError(
                f"Secret ref '{ds.secret_ref}' for data source {ds.data_source_id} is not configured in environment"
            )

        # 2. Construct from connection fields if specified
        if ds.db_type == "sqlite":
            db_name = ds.database_name or f"datasource_{ds.data_source_id}.db"
            return f"sqlite:///./local_data/{db_name}"
        elif ds.db_type == "postgresql":
            host = ds.host or "localhost"
            port = ds.port or 5432
            db_name = ds.database_name or "business"
            user = "postgres" if admin else (ds.connection_role or "readonly_app_user")
            return f"postgresql://{user}@{host}:{port}/{db_name}"

        raise DataSourceUnavailableError(
            f"Unsupported or unresolvable database type '{ds.db_type}' for data source {ds.data_source_id}"
        )

    @classmethod
    def check_health(cls, db: Optional[Session] = None, data_source_id: int = 1) -> Dict[str, Any]:
        """Performs a live ping against the target data source connection pool."""
        try:
            engine = cls.get_engine(db, data_source_id=data_source_id)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"data_source_id": data_source_id, "status": "healthy", "dialect": engine.dialect.name}
        except Exception as e:
            return {"data_source_id": data_source_id, "status": "unhealthy", "error": str(e)}

    @classmethod
    def reset_registry(cls):
        """Clears cached dynamic engines for testing isolation."""
        with cls._lock:
            cls._engine_registry.clear()
            cls._admin_engine_registry.clear()


# Global convenient alias
DataSourceManager = DataSourceConnectionManager

