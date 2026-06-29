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
from ipaddress import ip_address, ip_network

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
    enqueue_discovery,
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
from app.services.discovery import is_poly_provisioning_user_agent, parse_poly_user_agent
from app.services.firmware_resolver import resolve_firmware

router = APIRouter(prefix="/provisioning", tags=["provisioning"])

TRUSTED_PROXY_NETWORKS = (
    ip_network("127.0.0.1/32"),
    ip_network("172.16.0.0/12"),
)


def _mac_from_filename(filename: str) -> str | None:
    """Extract a MAC from filenames like 0004f2aabbcc.cfg or 0004f2aabbcc-phone.cfg."""
    stem = filename.split(".")[0].split("-")[0]
    try:
        return normalize_mac(stem)
    except ValueError:
        return None


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def _is_trusted_proxy(ip: str | None) -> bool:
    if ip is None:
        return False
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    return any(addr in network for network in TRUSTED_PROXY_NETWORKS)


def _client_ips(request: Request) -> tuple[str | None, str | None]:
    peer_ip = request.client.host if request.client else None
    endpoint_ip = _valid_ip(peer_ip)

    if _is_trusted_proxy(peer_ip):
        x_forwarded_for = request.headers.get("x-forwarded-for")
        x_real_ip = request.headers.get("x-real-ip")
        forwarded_ip = None
        if x_forwarded_for:
            forwarded_ip = _valid_ip(x_forwarded_for.split(",", 1)[0])
        endpoint_ip = forwarded_ip or _valid_ip(x_real_ip) or endpoint_ip

    proxy_ip = peer_ip if peer_ip and endpoint_ip and peer_ip != endpoint_ip else None
    return endpoint_ip, proxy_ip


async def _buffer_checkin(mac: str, endpoint_ip: str | None, proxy_ip: str | None, ua: str | None,
                          path: str, status: int, cache_hit: bool,
                          cfg_hash: str | None, nbytes: int) -> None:
    payload = json.dumps({
        "mac": mac, "ip": endpoint_ip, "proxy_ip": proxy_ip, "ua": ua, "path": path,
        "status": status, "cache_hit": cache_hit,
        "config_hash": cfg_hash, "bytes": nbytes,
        "ts": datetime.now(timezone.utc).isoformat(),
    }).encode()
    await enqueue_checkin(payload)
    metrics.checkins.inc()


async def _buffer_discovery(mac: str, endpoint_ip: str | None, proxy_ip: str | None,
                            ua: str | None, path: str, status: int) -> None:
    details = parse_poly_user_agent(ua)
    payload = json.dumps({
        "mac": mac,
        "model": details.model,
        "firmware_version": details.firmware_version,
        "serial": details.serial,
        "endpoint_ip": endpoint_ip,
        "proxy_ip": proxy_ip,
        "user_agent": ua,
        "last_path": path,
        "last_status": status,
        "ts": datetime.now(timezone.utc).isoformat(),
    }).encode()
    await enqueue_discovery(payload)


@router.get("/{filename}", response_class=PlainTextResponse)
async def get_config(
    filename: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    start = time.perf_counter()
    client_ip, proxy_ip = _client_ips(request)
    ua = request.headers.get("user-agent")

    is_global_master = filename == "000000000000.cfg"
    mac = None if is_global_master else _mac_from_filename(filename)
    path_type = "master" if is_global_master else "device"

    # Rate limit global master by IP; device configs prefer per-MAC limiting.
    rl_id = (client_ip or "unknown") if is_global_master else (mac or client_ip or "unknown")
    if not await rate_limit_ok(rl_id, settings.rate_limit_per_minute):
        metrics.provisioning_requests.labels(path_type, "429", "n/a").inc()
        return PlainTextResponse("rate limited", status_code=429)

    global_gen = await get_global_generation()

    if is_global_master:
        key = config_cache_key("global", "master", global_gen)
        cached = await cache_get(key)
        if cached is not None:
            metrics.cache_hits.inc()
            metrics.provisioning_requests.labels(path_type, "200", "hit").inc()
            elapsed = time.perf_counter() - start
            metrics.provisioning_latency.labels(path_type).observe(elapsed)
            logger.info("prov hit", extra={"mac": None, "path": filename,
                                            "cache_hit": True, "latency_ms": elapsed * 1000})
            return PlainTextResponse(cached.decode(), media_type="text/xml")

        metrics.cache_misses.inc()
        render_start = time.perf_counter()
        body = render_master_config("global", config_files=[])
        metrics.config_render_duration.observe(time.perf_counter() - render_start)
        await cache_set(key, body)

        metrics.provisioning_requests.labels(path_type, "200", "miss").inc()
        elapsed = time.perf_counter() - start
        metrics.provisioning_latency.labels(path_type).observe(elapsed)
        logger.info("prov miss", extra={"mac": None, "path": filename,
                                         "cache_hit": False, "latency_ms": elapsed * 1000})
        return PlainTextResponse(body.decode(), media_type="text/xml")

    # Device config requests must contain a usable MAC address.
    if mac is None:
        metrics.provisioning_requests.labels(path_type, "404", "miss").inc()
        return PlainTextResponse("not found", status_code=404)

    # Cache key incorporates global + per-device generation for invalidation
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
        await _buffer_checkin(mac, client_ip, proxy_ip, ua, filename, 200, True, None, len(cached))
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
        # Unknown devices still 404; first-touch discovery is buffered asynchronously.
        metrics.provisioning_requests.labels(path_type, "404", "miss").inc()
        if mac != "000000000000" and is_poly_provisioning_user_agent(ua):
            await _buffer_discovery(mac, client_ip, proxy_ip, ua, filename, 404)
        await _buffer_checkin(mac, client_ip, proxy_ip, ua, filename, 404, False, None, 0)
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
    await _buffer_checkin(mac, client_ip, proxy_ip, ua, filename, 200, False, cfg_hash, len(body))

    elapsed = time.perf_counter() - start
    metrics.provisioning_latency.labels(path_type).observe(elapsed)
    logger.info("prov miss", extra={"mac": mac, "path": filename,
                                    "cache_hit": False, "latency_ms": elapsed * 1000})
    return PlainTextResponse(body.decode(), media_type="text/xml")
