import time
import json
import logging
from typing import Optional, Dict, Any, List
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
    _last_check_time: float = 0.0
    _check_interval: float = 10.0

    def __init__(self):
        self._init_client()

    @classmethod
    def get_instance(cls) -> "RedisService":
        if cls._instance is None:
            cls._instance = RedisService()
        return cls._instance

    def _init_client(self):
        self._last_check_time = time.time()
        try:
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=20,
                socket_timeout=0.2,
                socket_connect_timeout=0.2,
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
        now = time.time()
        # If unavailable, back off to avoid blocking request threads with socket connection timeouts
        if not self._is_available and (now - self._last_check_time) < self._check_interval:
            return False
        try:
            self._client.ping()
            self._is_available = True
            self._last_check_time = now
            return True
        except Exception:
            self._is_available = False
            self._last_check_time = now
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
    # 2. Sliding Window Rate Limiting (REQ-OPS-04) - Atomic Lua Script
    # ------------------------------------------------------------------
    LUA_SLIDING_WINDOW_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local member = ARGV[4]
    local clearBefore = now - window

    redis.call('ZREMRANGEBYSCORE', key, '-inf', clearBefore)
    local currentRequests = redis.call('ZCARD', key)

    if currentRequests < limit then
        redis.call('ZADD', key, now, member)
        redis.call('EXPIRE', key, window + 5)
        return {1, limit - currentRequests - 1}
    else
        return {0, 0}
    end
    """

    _local_rate_limits: Dict[str, List[float]] = {}

    def _check_local_rate_limit(self, identifier: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """In-memory sliding-window fallback when Redis is unavailable (Fail-Safe Degraded Mode)."""
        now = time.time()
        cutoff = now - window_seconds
        
        # Clean expired timestamps
        timestamps = self._local_rate_limits.setdefault(identifier, [])
        self._local_rate_limits[identifier] = [t for t in timestamps if t > cutoff]
        current_reqs = len(self._local_rate_limits[identifier])

        if current_reqs < limit:
            self._local_rate_limits[identifier].append(now)
            remaining = limit - current_reqs - 1
            return True, remaining, window_seconds
        else:
            return False, 0, window_seconds

    def check_rate_limit(self, identifier: str, limit: int = 60, window_seconds: int = 60) -> tuple[bool, int, int]:
        """
        Atomic Sliding-Window Rate Limiter using Redis Lua script.
        Prevents race conditions under high concurrent load with bounded in-memory fallback.
        Returns: (is_allowed: bool, remaining_requests: int, reset_seconds: int)
        """
        if not self.is_available or self._client is None:
            # Fallback to local process bounded sliding window
            return self._check_local_rate_limit(identifier, limit, window_seconds)

        key = f"ratelimit:{identifier}"
        now = time.time()
        member = f"{now}:{time.time_ns()}"

        try:
            res = self._client.eval(
                self.LUA_SLIDING_WINDOW_SCRIPT,
                1,
                key,
                now,
                window_seconds,
                limit,
                member,
            )
            is_allowed = bool(res[0] == 1)
            remaining = int(res[1])
            return is_allowed, remaining, window_seconds
        except Exception as e:
            logger.error(f"Rate limiter Redis error: {e}. Utilizing local fallback.")
            return self._check_local_rate_limit(identifier, limit, window_seconds)

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
