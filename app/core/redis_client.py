import redis.asyncio as aioredis

from app.core.config import settings

redis_client: aioredis.Redis = aioredis.from_url(
    settings.redis_url, decode_responses=False
)


async def get_redis() -> aioredis.Redis:
    return redis_client


# ---- Config cache helpers -------------------------------------------------

def config_cache_key(mac: str, model: str, generation: int) -> str:
    return f"polyprov:cfg:{mac}:{model}:{generation}"


async def cache_get(key: str) -> bytes | None:
    return await redis_client.get(key)


async def cache_set(key: str, value: bytes, ttl: int | None = None) -> None:
    await redis_client.set(key, value, ex=ttl or settings.config_cache_ttl)


# ---- Generation counters (cache invalidation) -----------------------------

GLOBAL_GEN_KEY = "polyprov:gen:global"


async def get_global_generation() -> int:
    val = await redis_client.get(GLOBAL_GEN_KEY)
    return int(val) if val else 0


async def bump_global_generation() -> int:
    return await redis_client.incr(GLOBAL_GEN_KEY)


async def get_device_generation(mac: str) -> int:
    val = await redis_client.get(f"polyprov:gen:device:{mac}")
    return int(val) if val else 0


async def bump_device_generation(mac: str) -> int:
    return await redis_client.incr(f"polyprov:gen:device:{mac}")


# ---- Check-in write buffer (batched, keeps phones off the DB) -------------

async def enqueue_checkin(payload: bytes) -> None:
    await redis_client.rpush(settings.checkin_buffer_key, payload)


# ---- Rate limiting --------------------------------------------------------

async def rate_limit_ok(identifier: str, limit: int, window: int = 60) -> bool:
    """Fixed-window counter. Returns True if under limit."""
    key = f"polyprov:rl:{identifier}:{window}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window)
    return count <= limit
