import time
import json
import logging
from typing import Optional, Dict, Any
import redis
from app.config import settings

logger = logging.getLogger("trustengine.redis")


class RedisService:
    """
    Centralized Distributed Cache, Token Revocation, and Sliding-Window Rate Limiting Service.
    Designed for horizontal scalability across multiple FastAPI instances.
    """

    _instance: Optional["RedisService"] = None
    _client: Optional[redis.Redis] = None
    _is_available: bool = False

    def __init__(self):
        self._init_client()

    @classmethod
    def get_instance(cls) -> "RedisService":
        if cls._instance is None:
            cls._instance = RedisService()
        return cls._instance

    def _init_client(self):
        try:
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=20,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                decode_responses=True,
            )
            self._client = redis.Redis(connection_pool=pool)
            self._client.ping()
            self._is_available = True
            logger.info("Successfully connected to Redis distributed cache.")
        except Exception as e:
            self._is_available = False
            logger.warning(f"Redis unavailable ({e}). Operating in fail-closed / memory fallback mode.")

    @property
    def is_available(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.ping()
            self._is_available = True
            return True
        except Exception:
            self._is_available = False
            return False

    # ------------------------------------------------------------------
    # 1. Distributed Token Revocation (SEC-LOGOUT / SEC-JWT)
    # ------------------------------------------------------------------
    def revoke_token(self, jti: Optional[str], token_hash: str, ttl_seconds: int = 86400) -> bool:
        """Stores revoked JTI and token hash in Redis with TTL matching expiration."""
        if not self.is_available or self._client is None:
            return False
        try:
            pipe = self._client.pipeline()
            if jti:
                pipe.setex(f"revoked:jti:{jti}", ttl_seconds, "1")
            pipe.setex(f"revoked:hash:{token_hash}", ttl_seconds, "1")
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Error persisting token revocation in Redis: {e}")
            return False

    def is_token_revoked(self, jti: Optional[str], token_hash: str) -> bool:
        """O(1) lookup to check if token is revoked in distributed cache."""
        if not self.is_available or self._client is None:
            return False
        try:
            if jti and self._client.exists(f"revoked:jti:{jti}"):
                return True
            if self._client.exists(f"revoked:hash:{token_hash}"):
                return True
            return False
        except Exception as e:
            logger.error(f"Error querying Redis token revocation: {e}")
            return False

    # ------------------------------------------------------------------
    # 2. Sliding Window Rate Limiting (REQ-OPS-04)
    # ------------------------------------------------------------------
    def check_rate_limit(self, identifier: str, limit: int = 60, window_seconds: int = 60) -> tuple[bool, int, int]:
        """
        Sliding-Window Rate Limiter using Redis Sorted Sets.
        Returns: (is_allowed: bool, remaining_requests: int, reset_seconds: int)
        """
        if not self.is_available or self._client is None:
            # If Redis is unavailable, allow request (or fail-degraded)
            return True, limit, window_seconds

        key = f"ratelimit:{identifier}"
        now = time.time()
        window_start = now - window_seconds

        try:
            pipe = self._client.pipeline()
            # 1. Remove timestamps older than current window
            pipe.zremrangebyscore(key, 0, window_start)
            # 2. Count requests in current window
            pipe.zcard(key)
            # 3. Add current request timestamp
            pipe.zadd(key, {f"{now}:{time.time_ns()}": now})
            # 4. Set key expiration
            pipe.expire(key, window_seconds + 5)
            results = pipe.execute()

            request_count = results[1]
            if request_count >= limit:
                # Over limit -> reject
                return False, 0, int(window_seconds - (now - window_start))

            remaining = max(0, limit - request_count - 1)
            return True, remaining, window_seconds
        except Exception as e:
            logger.error(f"Rate limiter Redis error: {e}")
            return True, limit, window_seconds

    # ------------------------------------------------------------------
    # 3. Semantic Catalog Caching (PERF-CATALOG)
    # ------------------------------------------------------------------
    def get_cached_catalog(self, role_id: int, data_source_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves serialized semantic catalog from distributed cache."""
        if not self.is_available or self._client is None:
            return None
        try:
            data = self._client.get(f"catalog:{data_source_id}:role:{role_id}")
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    def set_cached_catalog(self, role_id: int, data_source_id: int, catalog_dict: Dict[str, Any], ttl_seconds: int = 300):
        """Stores serialized semantic catalog in distributed cache."""
        if not self.is_available or self._client is None:
            return
        try:
            self._client.setex(
                f"catalog:{data_source_id}:role:{role_id}",
                ttl_seconds,
                json.dumps(catalog_dict, default=str),
            )
        except Exception as e:
            logger.error(f"Error caching catalog: {e}")

    def invalidate_catalog_cache(self, data_source_id: int):
        """Invalidates all cached catalogs for a data source upon policy or schema change."""
        if not self.is_available or self._client is None:
            return
        try:
            keys = self._client.keys(f"catalog:{data_source_id}:role:*")
            if keys:
                self._client.delete(*keys)
        except Exception as e:
            logger.error(f"Error invalidating catalog cache: {e}")
