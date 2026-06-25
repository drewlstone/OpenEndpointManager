"""Provisioning plane router.

This is the high-volume path Poly phones hit. Design rules:
  * A cache HIT never touches PostgreSQL.
  * Check-in / log writes are buffered in Redis and flushed in batches by a
    Celery worker, so 100k phones don't generate 100k synchronous inserts.
  * Rate limiting is per-MAC and per-IP.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import metrics
from app.core.config import settings
from app.core.db import get_db
from app.core.logging_config import logger
from app.core.redis_client import (
    cache_get,
    cache_set,
    config_cache_key,
    enqueue_checkin,
    get_device_generation,
    get_global_generation,
    rate_limit_ok,
)
from app.core.security import normalize_mac
from app.models.device import Device
from app.provisioning.renderer import (
    config_hash,
    render_device_config,
    render_master_config,
)
from app.provisioning.resolver import resolve_effective_config
from app.services.firmware_resolver import resolve_firmware

router = APIRouter(prefix="/provisioning", tags=["provisioning"])


def _mac_from_filename(filename: str) -> str | None:
    """Extract a MAC from filenames like 0004f2aabbcc.cfg or 0004f2aabbcc-phone.cfg."""
    stem = filename.split(".")[0].split("-")[0]
    try:
        return normalize_mac(stem)
    except ValueError:
        return None


async def _buffer_checkin(mac: str, ip: str | None, ua: str | None,
                          path: str, status: int, cache_hit: bool,
                          cfg_hash: str | None, nbytes: int) -> None:
    payload = json.dumps({
        "mac": mac, "ip": ip, "ua": ua, "path": path,
        "status": status, "cache_hit": cache_hit,
        "config_hash": cfg_hash, "bytes": nbytes,
        "ts": datetime.now(timezone.utc).isoformat(),
    }).encode()
    await enqueue_checkin(payload)
    metrics.checkins.inc()


@router.get("/{filename}", response_class=PlainTextResponse)
async def get_config(
    filename: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    start = time.perf_counter()
    client_ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    mac = _mac_from_filename(filename)
    path_type = "master" if filename.startswith("000000000000") else "device"

    # Rate limit (per-MAC if known, else per-IP)
    rl_id = mac or client_ip or "unknown"
    if not await rate_limit_ok(rl_id, settings.rate_limit_per_minute):
        metrics.provisioning_requests.labels(path_type, "429", "n/a").inc()
        return PlainTextResponse("rate limited", status_code=429)

    # Master/global config with no MAC -> serve global master listing
    if mac is None:
        metrics.provisioning_requests.labels(path_type, "404", "miss").inc()
        return PlainTextResponse("not found", status_code=404)

    # Cache key incorporates global + per-device generation for invalidation
    global_gen = await get_global_generation()
    device_gen = await get_device_generation(mac)
    generation = global_gen * 1_000_000 + device_gen

    # We cache per (mac, path_type) — combine into the model slot of the key
    cache_slot = f"{path_type}"
    key = config_cache_key(mac, cache_slot, generation)

    cached = await cache_get(key)
    if cached is not None:
        # ---- CACHE HIT: no DB access at all ----
        metrics.cache_hits.inc()
        metrics.provisioning_requests.labels(path_type, "200", "hit").inc()
        await _buffer_checkin(mac, client_ip, ua, filename, 200, True, None, len(cached))
        elapsed = time.perf_counter() - start
        metrics.provisioning_latency.labels(path_type).observe(elapsed)
        logger.info("prov hit", extra={"mac": mac, "path": filename,
                                        "cache_hit": True, "latency_ms": elapsed * 1000})
        return PlainTextResponse(cached.decode(), media_type="text/xml")

    # ---- CACHE MISS: resolve + render ----
    metrics.cache_misses.inc()
    render_start = time.perf_counter()

    result = await db.execute(select(Device).where(Device.mac == mac))
    device = result.scalar_one_or_none()
    if device is None:
        # Unknown device. Optionally auto-enroll; here we 404 and log.
        metrics.provisioning_requests.labels(path_type, "404", "miss").inc()
        await _buffer_checkin(mac, client_ip, ua, filename, 404, False, None, 0)
        return PlainTextResponse("device not enrolled", status_code=404)

    effective = await resolve_effective_config(db, device)

    if path_type == "master":
        firmware = await resolve_firmware(db, device)
        app_path = (
            f"{settings.provisioning_base_path}firmware/{firmware.object_key}"
            if firmware else None
        )
        body = render_master_config(
            mac, config_files=[f"{mac}.cfg"], app_file_path=app_path
        )
    else:
        body = render_device_config(effective, mac)

    metrics.config_render_duration.observe(time.perf_counter() - render_start)
    await cache_set(key, body)

    cfg_hash = config_hash(body)
    metrics.provisioning_requests.labels(path_type, "200", "miss").inc()
    await _buffer_checkin(mac, client_ip, ua, filename, 200, False, cfg_hash, len(body))

    elapsed = time.perf_counter() - start
    metrics.provisioning_latency.labels(path_type).observe(elapsed)
    logger.info("prov miss", extra={"mac": mac, "path": filename,
                                    "cache_hit": False, "latency_ms": elapsed * 1000})
    return PlainTextResponse(body.decode(), media_type="text/xml")
