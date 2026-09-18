import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import Engine, inspect, text
from app.services.optimizer.models import CalibratedTableStats, DEFAULT_TABLE_STATS


class TableStatsProvider:
    """
    Introspects and caches live database statistics (tuple counts, pages, exact index columns, PK/FK, NDVs)
    from SQLAlchemy Engine, partitioned strictly per data source identity / engine to prevent cross-tenant cache contamination.
    """
    _cache: Dict[str, Dict[str, CalibratedTableStats]] = {}
    _cache_source: Dict[str, str] = {}
    _last_refresh: Dict[str, datetime] = {}
    _ttl_seconds: int = 300

    @classmethod
    def _get_cache_key(cls, data_source_id: int, engine: Optional[Engine]) -> str:
        if engine is not None:
            engine_str = str(engine.url)
            return f"ds_{data_source_id}:{hash(engine_str)}"
        return f"ds_{data_source_id}:fallback"

    @classmethod
    def _estimate_row_width(cls, inspector, table_name: str) -> float:
        """
        Estimates average row width in bytes based on column types and tuple header overhead,
        replacing arbitrary static 128-byte assumptions.
        """
        try:
            columns = inspector.get_columns(table_name)
            total_bytes = 24.0  # Tuple header + null bitmap baseline overhead
            for col in columns:
                col_type = str(col.get("type", "")).upper()
                if "INT" in col_type or "INTEGER" in col_type:
                    total_bytes += 4.0
                elif "BIGINT" in col_type:
                    total_bytes += 8.0
                elif "FLOAT" in col_type or "DOUBLE" in col_type or "NUMERIC" in col_type or "DECIMAL" in col_type:
                    total_bytes += 8.0
                elif "DATE" in col_type or "TIME" in col_type:
                    total_bytes += 8.0
                elif "BOOL" in col_type:
                    total_bytes += 1.0
                elif "VARCHAR" in col_type or "TEXT" in col_type:
                    total_bytes += 32.0  # Estimated average variable text width
                else:
                    total_bytes += 8.0
            return max(32.0, total_bytes)
        except Exception:
            return 64.0

    @classmethod
    def get_stats_map(
        cls,
        engine: Optional[Engine] = None,
        data_source_id: int = 1,
        force_refresh: bool = False,
    ) -> Tuple[Dict[str, CalibratedTableStats], str]:
        now = datetime.now(timezone.utc)
        cache_key = cls._get_cache_key(data_source_id, engine)

        if (
            not force_refresh
            and cache_key in cls._cache
            and cache_key in cls._last_refresh
            and (now - cls._last_refresh[cache_key]).total_seconds() < cls._ttl_seconds
        ):
            return cls._cache[cache_key], cls._cache_source.get(cache_key, "calibrated_cache")

        if engine is None:
            cls._cache[cache_key] = dict(DEFAULT_TABLE_STATS)
            cls._cache_source[cache_key] = "calibrated_cache"
            cls._last_refresh[cache_key] = now
            return cls._cache[cache_key], cls._cache_source[cache_key]

        try:
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            stats_map: Dict[str, CalibratedTableStats] = {}

            with engine.connect() as conn:
                for t_name in table_names:
                    t_lower = t_name.lower()
                    # 1. Live row count
                    try:
                        res = conn.execute(text(f'SELECT COUNT(*) FROM "{t_name}"'))
                        tuple_count = float(res.scalar() or 0)
                    except Exception:
                        tuple_count = 100.0

                    # 2. Primary key constraint
                    try:
                        pk_constraint = inspector.get_pk_constraint(t_name)
                        pk_cols = pk_constraint.get("constrained_columns", []) if pk_constraint else []
                        pk_name = pk_cols[0].lower() if pk_cols else "id"
                    except Exception:
                        pk_name = "id"
                        pk_cols = ["id"]

                    # 3. Secondary indexes with actual column introspection
                    index_names: List[str] = []
                    index_columns_map: Dict[str, List[str]] = {}
                    if pk_cols:
                        pk_idx_name = f"{t_lower}_pkey"
                        index_names.append(pk_idx_name)
                        index_columns_map[pk_idx_name] = [c.lower() for c in pk_cols]

                    try:
                        indexes_raw = inspector.get_indexes(t_name)
                        for idx in indexes_raw:
                            idx_n = idx.get("name")
                            if idx_n:
                                idx_n_lower = idx_n.lower()
                                index_names.append(idx_n_lower)
                                cols = [c.lower() for c in idx.get("column_names", []) if c]
                                index_columns_map[idx_n_lower] = cols
                    except Exception:
                        pass

                    # 4. Foreign key constraints
                    foreign_keys: List[Dict[str, Any]] = []
                    try:
                        fks_raw = inspector.get_foreign_keys(t_name)
                        for fk in fks_raw:
                            foreign_keys.append({
                                "constrained_columns": [c.lower() for c in fk.get("constrained_columns", [])],
                                "referred_table": fk.get("referred_table", "").lower(),
                                "referred_columns": [c.lower() for c in fk.get("referred_columns", [])],
                            })
                    except Exception:
                        pass

                    # 5. Schema-derived row width and page count estimation (8KB pages)
                    row_width = cls._estimate_row_width(inspector, t_name)
                    page_count = max(1.0, math.ceil((tuple_count * row_width) / 8192.0))

                    # 6. NDV estimations for indexed / PK columns
                    ndv_map: Dict[str, float] = {}
                    for col_list in index_columns_map.values():
                        for col in col_list:
                            if col not in ndv_map:
                                try:
                                    ndv_res = conn.execute(text(f'SELECT COUNT(DISTINCT "{col}") FROM "{t_name}"'))
                                    ndv_map[col] = float(ndv_res.scalar() or 1.0)
                                except Exception:
                                    ndv_map[col] = min(tuple_count, 10.0)

                    stats_map[t_lower] = CalibratedTableStats(
                        table_name=t_lower,
                        tuple_count=tuple_count,
                        page_count=page_count,
                        primary_key=pk_name,
                        indexes=index_names,
                        index_columns=index_columns_map,
                        foreign_keys=foreign_keys,
                        ndv_map=ndv_map,
                        is_live=True,
                    )

            if stats_map:
                cls._cache[cache_key] = stats_map
                cls._cache_source[cache_key] = "live_engine"
                cls._last_refresh[cache_key] = now
                return cls._cache[cache_key], cls._cache_source[cache_key]

        except Exception:
            pass

        cls._cache[cache_key] = dict(DEFAULT_TABLE_STATS)
        cls._cache_source[cache_key] = "fallback_schema"
        cls._last_refresh[cache_key] = now
        return cls._cache[cache_key], cls._cache_source[cache_key]
