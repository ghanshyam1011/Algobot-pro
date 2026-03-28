"""
database/redis_config.py
==========================
Redis cache configuration for AlgoBot Pro.

Redis is used for:
    1. Live price cache    — latest price per coin (expires in 5 min)
    2. Signal cache        — latest signal per coin (expires in 2 hours)
    3. Session store       — user session data for the web dashboard
    4. Rate limiting       — prevent API abuse (max N requests/minute)
    5. Job deduplication   — prevent duplicate signal generations

WHY REDIS?
    Some data needs to be fast and temporary.
    PostgreSQL is great for permanent storage, but slow for
    high-frequency reads like "what's the current BTC price?".
    Redis stores data in memory — reads are ~10,000x faster.

SETUP (optional):
    Redis is only needed in production.
    In development, we use simple Python dicts as fallback.

    Install Redis:
        Windows : https://github.com/microsoftarchive/redis/releases
        Mac     : brew install redis
        Linux   : sudo apt-get install redis-server

    Start Redis:
        redis-server

    Add to .env:
        REDIS_URL=redis://localhost:6379/0

DEPENDENCIES:
    pip install redis
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")

# Cache expiry times (seconds)
PRICE_TTL   = 5 * 60       # 5 minutes
SIGNAL_TTL  = 2 * 60 * 60  # 2 hours
SESSION_TTL = 24 * 60 * 60 # 24 hours

# Key prefixes
PREFIX_PRICE   = "algobot:price:"
PREFIX_SIGNAL  = "algobot:signal:"
PREFIX_SESSION = "algobot:session:"
PREFIX_RATELIM = "algobot:ratelimit:"


# ── Try connecting to Redis ────────────────────────────────────────────────────
_redis_client = None
REDIS_AVAILABLE = False

if REDIS_URL:
    try:
        import redis
        _redis_client   = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        REDIS_AVAILABLE = True
        log.info("Redis connected successfully.")
    except ImportError:
        log.warning(
            "redis library not installed.\n"
            "Run: pip install redis\n"
            "Using in-memory dict as fallback."
        )
    except Exception as e:
        log.warning(f"Redis connection failed: {e}\nUsing in-memory dict as fallback.")
else:
    log.debug("REDIS_URL not set — using in-memory dict as fallback.")

# In-memory fallback when Redis is not available
_memory_cache: dict = {}


# ── Generic cache operations ───────────────────────────────────────────────────

def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """
    Store a value in cache.

    Args:
        key:   Cache key string
        value: Any JSON-serialisable value
        ttl:   Time-to-live in seconds (default 5 minutes)

    Returns:
        bool: True if stored successfully

    Example:
        >>> from database.redis_config import cache_set
        >>> cache_set("algobot:price:BTC_USD", 66500.0, ttl=300)
    """
    serialised = json.dumps(value, default=str)

    if REDIS_AVAILABLE and _redis_client:
        try:
            _redis_client.setex(key, ttl, serialised)
            return True
        except Exception as e:
            log.error(f"Redis set failed: {e}")

    # Fallback to memory
    _memory_cache[key] = {
        "value":      serialised,
        "expires_at": datetime.now(timezone.utc).timestamp() + ttl,
    }
    return True


def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve a value from cache.

    Args:
        key: Cache key string

    Returns:
        Deserialised value, or None if not found / expired

    Example:
        >>> from database.redis_config import cache_get
        >>> price = cache_get("algobot:price:BTC_USD")
    """
    if REDIS_AVAILABLE and _redis_client:
        try:
            raw = _redis_client.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception as e:
            log.error(f"Redis get failed: {e}")

    # Fallback to memory
    entry = _memory_cache.get(key)
    if not entry:
        return None

    if datetime.now(timezone.utc).timestamp() > entry["expires_at"]:
        del _memory_cache[key]
        return None

    return json.loads(entry["value"])


def cache_delete(key: str) -> bool:
    """Delete a key from cache."""
    if REDIS_AVAILABLE and _redis_client:
        try:
            _redis_client.delete(key)
        except Exception:
            pass

    _memory_cache.pop(key, None)
    return True


def cache_exists(key: str) -> bool:
    """Return True if a key exists in cache and is not expired."""
    return cache_get(key) is not None


# ── Specific cache helpers ─────────────────────────────────────────────────────

def cache_price(coin_name: str, price: float) -> None:
    """Cache the latest price for a coin."""
    cache_set(f"{PREFIX_PRICE}{coin_name}", price, ttl=PRICE_TTL)


def get_cached_price(coin_name: str) -> Optional[float]:
    """Get the cached price for a coin. Returns None if expired."""
    return cache_get(f"{PREFIX_PRICE}{coin_name}")


def cache_signal(coin_name: str, signal: dict) -> None:
    """Cache the latest signal for a coin."""
    cache_set(f"{PREFIX_SIGNAL}{coin_name}", signal, ttl=SIGNAL_TTL)


def get_cached_signal(coin_name: str) -> Optional[dict]:
    """Get the cached signal for a coin. Returns None if expired."""
    return cache_get(f"{PREFIX_SIGNAL}{coin_name}")


def get_all_cached_signals() -> dict:
    """
    Get cached signals for all coins.

    Returns:
        dict: { 'BTC_USD': signal_dict, ... }
              Only includes coins with non-expired cache entries.
    """
    from config.settings import COINS
    result = {}
    for coin_name in COINS.values():
        signal = get_cached_signal(coin_name)
        if signal:
            result[coin_name] = signal
    return result


def check_rate_limit(identifier: str, max_requests: int = 60, window: int = 60) -> bool:
    """
    Simple rate limiter.

    Args:
        identifier:   User ID or IP address
        max_requests: Max allowed requests in the window
        window:       Time window in seconds

    Returns:
        bool: True if request is allowed, False if rate limited

    Example:
        >>> if not check_rate_limit(telegram_id, max_requests=5, window=60):
        ...     send_telegram(chat_id, "Too many requests. Wait a minute.")
    """
    key   = f"{PREFIX_RATELIM}{identifier}"
    count = cache_get(key)

    if count is None:
        cache_set(key, 1, ttl=window)
        return True

    if count >= max_requests:
        return False

    # Increment counter (rebuild with same TTL — approximation)
    cache_set(key, count + 1, ttl=window)
    return True


def get_cache_stats() -> dict:
    """
    Return cache statistics.

    Returns:
        dict: Storage backend, key count, memory usage
    """
    if REDIS_AVAILABLE and _redis_client:
        try:
            info    = _redis_client.info("memory")
            db_info = _redis_client.info("keyspace")
            return {
                "backend":       "redis",
                "connected":     True,
                "used_memory_mb":round(info.get("used_memory", 0) / 1024 / 1024, 2),
                "key_count":     sum(
                    v.get("keys", 0)
                    for v in db_info.values()
                    if isinstance(v, dict)
                ),
            }
        except Exception as e:
            return {"backend": "redis", "connected": False, "error": str(e)}

    # Memory cache stats
    now        = datetime.now(timezone.utc).timestamp()
    live_keys  = [k for k, v in _memory_cache.items() if v["expires_at"] > now]
    return {
        "backend":    "memory",
        "connected":  True,
        "key_count":  len(live_keys),
        "note":       "In-memory cache — data is lost on restart. Set REDIS_URL for persistence.",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    print("── Redis / Cache Status ──────────────────────────────")
    stats = get_cache_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n── Testing cache operations ──────────────────────────")
    cache_set("test:key", {"value": 42, "msg": "hello"}, ttl=60)
    result = cache_get("test:key")
    print(f"  Set and get: {result}")

    cache_price("BTC_USD", 66500.0)
    btc = get_cached_price("BTC_USD")
    print(f"  Cached BTC price: {btc}")

    print("\n  Cache is working correctly!" if btc else "\n  Cache test failed.")