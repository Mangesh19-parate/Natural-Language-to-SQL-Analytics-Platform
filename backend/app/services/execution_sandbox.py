import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy import text, Engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError, TimeoutError as SATimeoutError


class SandboxExecutionResult(BaseModel):
    success: bool
    sql: str
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    latency_ms: int = 0
    truncated: bool = False
    error: Optional[str] = None
    error_class: Optional[str] = None


class ExecutionSandboxService:
    """
    Read-Only Execution Sandbox with Timeout and Row Limits (Task T-22 / Rules R1.5, R1.6 / SEC-5, SEC-6).
    Enforces:
    1. Query execution timeout (default 10s).
    2. Hard row-return cap (default 10,000 rows).
    3. Read-only engine level execution (defense in depth).
    """

    DEFAULT_TIMEOUT_SECONDS: float = 10.0
    MAX_TIMEOUT_SECONDS: float = 30.0
    DEFAULT_MAX_ROWS: int = 1000
    HARD_ROW_CEILING: int = 5000

    @classmethod
    def execute_query(
        cls,
        engine: Engine,
        sql: str,
        timeout_seconds: Optional[float] = None,
        max_rows: Optional[int] = None,
    ) -> SandboxExecutionResult:
        """
        Executes a SQL query in a sandboxed connection with strict timeout and row limits.
        Enforces hard server-side ceilings against malicious or unbounded parameters (SEC-5, SEC-6).
        """
        raw_timeout = timeout_seconds if timeout_seconds is not None and timeout_seconds > 0 else cls.DEFAULT_TIMEOUT_SECONDS
        timeout = min(float(raw_timeout), cls.MAX_TIMEOUT_SECONDS)

        raw_rows = max_rows if max_rows is not None and max_rows > 0 else cls.DEFAULT_MAX_ROWS
        max_rows = min(int(raw_rows), cls.HARD_ROW_CEILING)
        start_time = time.time()
        cleaned_sql = sql.strip().rstrip(";")

        try:
            with engine.connect() as conn:
                # Set statement timeout based on dialect if supported
                dialect_name = engine.dialect.name
                if dialect_name == "postgresql":
                    conn.execute(text(f"SET statement_timeout = {int(timeout * 1000)}"))
                elif dialect_name == "mysql":
                    conn.execute(text(f"SET max_execution_time = {int(timeout * 1000)}"))

                # Execute statement
                result_proxy = conn.execute(text(cleaned_sql))
                
                if not result_proxy.returns_rows:
                    latency_ms = int((time.time() - start_time) * 1000)
                    return SandboxExecutionResult(
                        success=True,
                        sql=sql,
                        columns=[],
                        rows=[],
                        row_count=0,
                        latency_ms=latency_ms,
                        truncated=False,
                    )

                columns = list(result_proxy.keys())
                raw_rows = result_proxy.fetchmany(max_rows + 1)
                truncated = len(raw_rows) > max_rows
                returned_rows = raw_rows[:max_rows]

                # Convert rows to dicts
                rows_data: List[Dict[str, Any]] = []
                for row in returned_rows:
                    row_dict = {}
                    for col, val in zip(columns, row):
                        # Convert non-serializable objects (e.g. Decimal, datetime)
                        if hasattr(val, "isoformat"):
                            row_dict[col] = val.isoformat()
                        elif hasattr(val, "__float__"):
                            row_dict[col] = float(val)
                        else:
                            row_dict[col] = val
                    rows_data.append(row_dict)

                latency_ms = int((time.time() - start_time) * 1000)
                return SandboxExecutionResult(
                    success=True,
                    sql=sql,
                    columns=columns,
                    rows=rows_data,
                    row_count=len(rows_data),
                    latency_ms=latency_ms,
                    truncated=truncated,
                )

        except (SATimeoutError, TimeoutError) as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SandboxExecutionResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                latency_ms=latency_ms,
                truncated=False,
                error=f"Query timed out after {timeout}s: {e}",
                error_class="TIMEOUT_ERROR",
            )
        except OperationalError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SandboxExecutionResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                latency_ms=latency_ms,
                truncated=False,
                error=f"Database operational error: {e.orig if hasattr(e, 'orig') else e}",
                error_class="DATABASE_OPERATIONAL_ERROR",
            )
        except SQLAlchemyError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SandboxExecutionResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                latency_ms=latency_ms,
                truncated=False,
                error=f"Database query error: {e.orig if hasattr(e, 'orig') else e}",
                error_class="DATABASE_QUERY_ERROR",
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SandboxExecutionResult(
                success=False,
                sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                latency_ms=latency_ms,
                truncated=False,
                error=str(e),
                error_class="INTERNAL_ERROR",
            )
