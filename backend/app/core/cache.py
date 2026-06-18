"""Cache helpers with Redis primary and in-memory fallback.

The app should keep working locally even when Redis is not running. Redis is used
when available; otherwise a process-local fallback is used for token revocation,
refresh allowlists, and small admin analytics cache entries.
"""

from __future__ import annotations

import json
import hashlib
import logging
import time
from typing import Any, Optional

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[redis.Redis] = None
_memory: dict[str, tuple[Any, float | None]] = {}
_memory_sets: dict[str, tuple[set[str], float | None]] = {}
_redis_available: bool | None = None


def _now() -> float:
    return time.time()


def _expired(exp: float | None) -> bool:
    return exp is not None and exp <= _now()


def _ttl_exp(ttl_seconds: int | None) -> float | None:
    if ttl_seconds is None:
        return None
    return _now() + max(0, int(ttl_seconds))


def _get_client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def _redis_ok() -> bool:
    global _redis_available
    if _redis_available is False:
        if settings.REQUIRE_REDIS:
            raise RuntimeError("Redis is required but unavailable")
        return False
    try:
        await _get_client().ping()
        _redis_available = True
        return True
    except Exception as exc:
        _redis_available = False
        if settings.REQUIRE_REDIS:
            logger.error("Redis is required but unavailable: %s", exc)
            raise RuntimeError("Redis is required but unavailable") from exc
        logger.warning("Redis unavailable; using in-memory cache fallback: %s", exc)
        return False



async def ensure_ready() -> None:
    """Fail fast when production explicitly requires Redis."""
    if settings.REQUIRE_REDIS:
        await _redis_ok()


async def close() -> None:
    """Close the async Redis connection before the application event loop exits.

    Uvicorn reloads create and destroy event loops repeatedly on Windows.  If
    the Redis transport is left for garbage collection, ``StreamWriter.__del__``
    can run after the loop is already closed and emit noisy runtime errors.
    """
    global _redis, _redis_available
    client = _redis
    _redis = None
    _redis_available = None
    if client is None:
        return
    try:
        aclose = getattr(client, "aclose", None)
        if callable(aclose):
            await aclose()
        else:
            close_method = getattr(client, "close", None)
            if callable(close_method):
                result = close_method()
                if hasattr(result, "__await__"):
                    await result
    except Exception:
        logger.exception("Redis shutdown cleanup failed")

def get_client() -> redis.Redis:
    """Public Redis client accessor for code that explicitly needs Redis."""
    return _get_client()


async def set_str(key: str, value: str, ttl_seconds: int | None = None) -> None:
    if await _redis_ok():
        try:
            if ttl_seconds is None:
                await _get_client().set(key, value)
            else:
                await _get_client().set(key, value, ex=ttl_seconds)
            return
        except RedisError:
            logger.exception("Redis set_str failed; falling back to memory")
    _memory[key] = (value, _ttl_exp(ttl_seconds))


async def get_str(key: str) -> str | None:
    if await _redis_ok():
        try:
            return await _get_client().get(key)
        except RedisError:
            logger.exception("Redis get_str failed; falling back to memory")
    item = _memory.get(key)
    if not item:
        return None
    value, exp = item
    if _expired(exp):
        _memory.pop(key, None)
        return None
    return value


async def s_add(key: str, member: str, ttl_seconds: int | None = None) -> None:
    if await _redis_ok():
        try:
            r = _get_client()
            await r.sadd(key, member)
            if ttl_seconds is not None:
                await r.expire(key, ttl_seconds)
            return
        except RedisError:
            logger.exception("Redis s_add failed; falling back to memory")
    members, _ = _memory_sets.get(key, (set(), None))
    members.add(member)
    _memory_sets[key] = (members, _ttl_exp(ttl_seconds))


async def s_remove(key: str, member: str) -> None:
    if await _redis_ok():
        try:
            await _get_client().srem(key, member)
            return
        except RedisError:
            logger.exception("Redis s_remove failed; falling back to memory")
    item = _memory_sets.get(key)
    if item:
        members, exp = item
        members.discard(member)
        _memory_sets[key] = (members, exp)


async def s_is_member(key: str, member: str) -> bool:
    if await _redis_ok():
        try:
            return bool(await _get_client().sismember(key, member))
        except RedisError:
            logger.exception("Redis s_is_member failed; falling back to memory")
    item = _memory_sets.get(key)
    if not item:
        return False
    members, exp = item
    if _expired(exp):
        _memory_sets.pop(key, None)
        return False
    return member in members


def make_key(prefix: str, parts: list[Any]) -> str:
    raw = prefix + ":" + json.dumps(parts, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


async def get_json(key: str) -> Any | None:
    val = await get_str(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None


async def set_json(key: str, value: Any, ttl_seconds: int = 60) -> None:
    await set_str(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)


async def delete_key(key: str) -> None:
    """Delete one cache key from Redis and the local fallback."""
    if await _redis_ok():
        try:
            await _get_client().delete(key)
        except RedisError:
            logger.exception("Redis delete_key failed; falling back to memory")
    _memory.pop(key, None)
    _memory_sets.pop(key, None)


async def acquire_lock(key: str, ttl_seconds: int = 60) -> str | None:
    """Acquire a short-lived distributed lock and return its ownership token.

    Redis uses SET NX EX so two backend workers cannot approve the same action
    concurrently. The process-local fallback keeps development mode safe inside
    one process; production requires Redis through REQUIRE_REDIS=true.
    """
    import uuid

    token = uuid.uuid4().hex
    ttl = max(1, int(ttl_seconds))
    if await _redis_ok():
        try:
            acquired = await _get_client().set(key, token, ex=ttl, nx=True)
            return token if acquired else None
        except RedisError:
            logger.exception("Redis acquire_lock failed; falling back to memory")

    item = _memory.get(key)
    if item is not None:
        _, exp = item
        if not _expired(exp):
            return None
        _memory.pop(key, None)
    _memory[key] = (token, _ttl_exp(ttl))
    return token


async def release_lock(key: str, token: str) -> None:
    """Release a distributed lock only when ``token`` still owns it."""
    if await _redis_ok():
        try:
            script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
              return redis.call('del', KEYS[1])
            end
            return 0
            """
            await _get_client().eval(script, 1, key, token)
            return
        except RedisError:
            logger.exception("Redis release_lock failed; falling back to memory")
    item = _memory.get(key)
    if item and item[0] == token:
        _memory.pop(key, None)


async def invalidate(prefix: str) -> None:
    """Delete keys by prefix (best-effort)."""
    if await _redis_ok():
        try:
            pattern = f"{prefix}:*"
            async for k in _get_client().scan_iter(match=pattern, count=200):
                await _get_client().delete(k)
            return
        except RedisError:
            logger.exception("Redis invalidate failed; falling back to memory")
    for k in list(_memory.keys()):
        if k.startswith(prefix + ":"):
            _memory.pop(k, None)
    for k in list(_memory_sets.keys()):
        if k.startswith(prefix + ":"):
            _memory_sets.pop(k, None)


async def invalidate_admin_caches() -> None:
    """Invalidate cached admin/model analytics after state-changing actions."""
    for prefix in (
        "admin_overview_v2",
        "admin_gpd",
        "admin_top_models",
        "admin_rev",
        "models_compare_v2",
    ):
        await invalidate(prefix)
