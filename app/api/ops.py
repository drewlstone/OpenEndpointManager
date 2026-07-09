from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db import get_db
from app.core.health_engine import HEALTH_SCHEDULER_LAST_RUN_KEY
from app.core.redis_client import redis_client
from app.models.admin import CheckinEvent, ProvisioningLog
from app.models.device import Device
from app.models.discovery import DiscoveredEndpoint
from app.schemas import HealthEngineRuntimeOut, ProvisioningReadinessOut

router = APIRouter(prefix="/ops", tags=["ops"])


def _parse_utc_datetime(value: bytes | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _celery_worker_status() -> tuple[bool, list[str], str | None]:
    inspector = celery_app.control.inspect(timeout=1.0)
    ping = inspector.ping() or {}
    stats = inspector.stats() or {}
    hostnames = sorted(set(ping) | set(stats))
    celery_version = None
    for values in stats.values():
        if isinstance(values, dict) and values.get("celery_version"):
            celery_version = str(values["celery_version"])
            break
    return bool(hostnames), hostnames, celery_version


def _worker_runtime_config() -> dict[str, Any] | None:
    result = celery_app.send_task("app.worker.health_engine_runtime")
    try:
        values = result.get(timeout=2.0, disable_sync_subtasks=False)
    except Exception:
        return None
    return values if isinstance(values, dict) else None


def _beat_connected(last_run: datetime | None, runtime: dict[str, Any] | None) -> bool:
    if last_run is None or not runtime:
        return False
    schedule_seconds = runtime.get("health_probe_schedule_seconds")
    try:
        schedule_seconds = float(schedule_seconds)
    except (TypeError, ValueError):
        return False
    grace_seconds = max(schedule_seconds * 2, schedule_seconds + 60)
    return datetime.now(timezone.utc) - last_run <= timedelta(seconds=grace_seconds)


def _ratio(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return part / total


def _status_from_attention(attention: list[dict[str, str]]) -> str:
    if any(item["severity"] == "critical" for item in attention):
        return "critical"
    if any(item["severity"] == "warning" for item in attention):
        return "warning"
    return "ready"


def _add_attention(attention: list[dict[str, str]], severity: str, code: str, label: str) -> None:
    attention.append({"severity": severity, "code": code, "label": label})


async def _redis_buffer_depths() -> tuple[bool, int | None, int | None, datetime | None]:
    scheduler_last_run = None
    try:
        await redis_client.ping()
        checkin_depth, discovery_depth, last_run_raw = await asyncio.gather(
            redis_client.llen(settings.checkin_buffer_key),
            redis_client.llen(settings.discovery_buffer_key),
            redis_client.get(HEALTH_SCHEDULER_LAST_RUN_KEY),
        )
        scheduler_last_run = _parse_utc_datetime(last_run_raw)
        return True, int(checkin_depth), int(discovery_depth), scheduler_last_run
    except Exception:
        return False, None, None, scheduler_last_run


async def _readiness_db_aggregates(
    db: AsyncSession,
    principal: Principal,
    now: datetime,
) -> tuple[bool, dict[str, Any]]:
    cutoff_15m = now - timedelta(minutes=15)
    cutoff_1h = now - timedelta(hours=1)
    stale_cutoff = now - timedelta(hours=24)

    try:
        await db.execute(text("SELECT 1"))

        device_stmt = select(Device.status, func.count()).group_by(Device.status)
        if principal.tenant_id is not None:
            device_stmt = device_stmt.where(Device.tenant_id == principal.tenant_id)
        status_counts = {status: count for status, count in (await db.execute(device_stmt)).all()}
        total_devices = sum(status_counts.values())

        checkin_at = func.coalesce(Device.last_checkin_at, Device.last_seen_at)
        stale_stmt = select(func.count()).select_from(Device).where(
            (checkin_at.is_(None)) | (checkin_at < stale_cutoff)
        )
        if principal.tenant_id is not None:
            stale_stmt = stale_stmt.where(Device.tenant_id == principal.tenant_id)
        stale_24h = (await db.execute(stale_stmt)).scalar_one()

        recent_stmt = select(func.count(func.distinct(CheckinEvent.mac))).select_from(CheckinEvent).where(
            CheckinEvent.ts >= cutoff_15m
        )
        if principal.tenant_id is not None:
            recent_stmt = recent_stmt.join(Device, Device.mac == CheckinEvent.mac).where(
                Device.tenant_id == principal.tenant_id
            )
        recent_checkins_15m = (await db.execute(recent_stmt)).scalar_one()

        pending_discoveries = 0
        if principal.tenant_id is None:
            pending_discoveries = (
                await db.execute(
                    select(func.count()).select_from(DiscoveredEndpoint).where(
                        DiscoveredEndpoint.status == "pending"
                    )
                )
            ).scalar_one()

        requests_15m = (
            await db.execute(
                select(func.count()).select_from(ProvisioningLog).where(ProvisioningLog.ts >= cutoff_15m)
            )
        ).scalar_one()
        requests_1h = (
            await db.execute(
                select(func.count()).select_from(ProvisioningLog).where(ProvisioningLog.ts >= cutoff_1h)
            )
        ).scalar_one()
        errors_15m = (
            await db.execute(
                select(func.count()).select_from(ProvisioningLog).where(
                    ProvisioningLog.ts >= cutoff_15m,
                    ProvisioningLog.status_code >= 400,
                )
            )
        ).scalar_one()
        errors_1h = (
            await db.execute(
                select(func.count()).select_from(ProvisioningLog).where(
                    ProvisioningLog.ts >= cutoff_1h,
                    ProvisioningLog.status_code >= 400,
                )
            )
        ).scalar_one()
        cache_hits_15m = (
            await db.execute(
                select(func.count()).select_from(ProvisioningLog).where(
                    ProvisioningLog.ts >= cutoff_15m,
                    ProvisioningLog.cache_hit.is_(True),
                )
            )
        ).scalar_one()
        cache_misses_15m = (
            await db.execute(
                select(func.count()).select_from(ProvisioningLog).where(
                    ProvisioningLog.ts >= cutoff_15m,
                    ProvisioningLog.cache_hit.is_(False),
                )
            )
        ).scalar_one()

        return True, {
            "fleet": {
                "total_devices": total_devices,
                "enrolled": status_counts.get("enrolled", 0),
                "disabled": status_counts.get("disabled", 0),
                "retired": status_counts.get("retired", 0),
                "pending_discoveries": pending_discoveries,
                "recent_checkins_15m": recent_checkins_15m,
                "stale_24h": stale_24h,
            },
            "provisioning": {
                "requests_15m": requests_15m,
                "requests_1h": requests_1h,
                "errors_15m": errors_15m,
                "errors_1h": errors_1h,
                "error_rate_15m": _ratio(errors_15m, requests_15m),
                "cache_hits_15m": cache_hits_15m,
                "cache_misses_15m": cache_misses_15m,
                "cache_hit_ratio_15m": _ratio(cache_hits_15m, cache_hits_15m + cache_misses_15m),
            },
        }
    except Exception:
        return False, {
            "fleet": {
                "total_devices": 0,
                "enrolled": 0,
                "disabled": 0,
                "retired": 0,
                "pending_discoveries": 0,
                "recent_checkins_15m": 0,
                "stale_24h": 0,
            },
            "provisioning": {
                "requests_15m": 0,
                "requests_1h": 0,
                "errors_15m": 0,
                "errors_1h": 0,
                "error_rate_15m": None,
                "cache_hits_15m": 0,
                "cache_misses_15m": 0,
                "cache_hit_ratio_15m": None,
            },
        }


@router.get("/health-engine", response_model=HealthEngineRuntimeOut)
async def health_engine_runtime(
    _: Principal = Depends(require_permission("report:read")),
) -> HealthEngineRuntimeOut:
    redis_connected = False
    scheduler_last_run = None
    try:
        await redis_client.ping()
        redis_connected = True
        scheduler_last_run = _parse_utc_datetime(
            await redis_client.get(HEALTH_SCHEDULER_LAST_RUN_KEY)
        )
    except Exception:
        pass

    worker_connected, worker_hostnames, celery_worker_version = await asyncio.to_thread(
        _celery_worker_status
    )
    runtime = await asyncio.to_thread(_worker_runtime_config) if worker_connected else None
    if runtime and runtime.get("hostname") and not worker_hostnames:
        worker_hostnames = [str(runtime["hostname"])]

    scheduler_next_run = None
    if scheduler_last_run and runtime and runtime.get("health_probe_schedule_seconds") is not None:
        scheduler_next_run = scheduler_last_run + timedelta(
            seconds=float(runtime["health_probe_schedule_seconds"])
        )

    return HealthEngineRuntimeOut(
        health_probe_scheduler_enabled=runtime.get("health_probe_scheduler_enabled") if runtime else None,
        health_probe_icmp_enabled=runtime.get("health_probe_icmp_enabled") if runtime else None,
        health_probe_interval_seconds=runtime.get("health_probe_interval_seconds") if runtime else None,
        health_probe_timeout_seconds=runtime.get("health_probe_timeout_seconds") if runtime else None,
        health_probe_batch_size=runtime.get("health_probe_batch_size") if runtime else None,
        health_probe_concurrency=runtime.get("health_probe_concurrency") if runtime else None,
        health_probe_jitter_seconds=runtime.get("health_probe_jitter_seconds") if runtime else None,
        worker_connected=worker_connected and runtime is not None,
        beat_connected=_beat_connected(scheduler_last_run, runtime),
        redis_connected=redis_connected,
        worker_hostnames=worker_hostnames,
        celery_worker_version=celery_worker_version,
        scheduler_last_run=scheduler_last_run,
        scheduler_next_run=scheduler_next_run,
    )

@router.get("/provisioning-readiness", response_model=ProvisioningReadinessOut)
async def provisioning_readiness(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("report:read")),
) -> ProvisioningReadinessOut:
    generated_at = datetime.now(timezone.utc)
    db_connected, aggregates = await _readiness_db_aggregates(db, principal, generated_at)
    redis_connected, checkin_depth, discovery_depth, scheduler_last_run = await _redis_buffer_depths()

    worker_connected, _, _ = await asyncio.to_thread(_celery_worker_status)
    runtime = await asyncio.to_thread(_worker_runtime_config) if worker_connected else None
    runtime_worker_connected = worker_connected and runtime is not None
    beat_connected = _beat_connected(scheduler_last_run, runtime)

    fleet = aggregates["fleet"]
    provisioning = aggregates["provisioning"]
    attention: list[dict[str, str]] = []

    if not db_connected:
        _add_attention(attention, "critical", "db_disconnected", "Database is not reachable")
    if not redis_connected:
        _add_attention(attention, "critical", "redis_disconnected", "Redis is not reachable")
    if not runtime_worker_connected:
        _add_attention(attention, "critical", "worker_disconnected", "Celery worker is not connected")
    if not beat_connected:
        _add_attention(attention, "critical", "beat_disconnected", "Celery beat is not reporting scheduler activity")
    if fleet["stale_24h"] > 0:
        _add_attention(attention, "warning", "stale_devices", f"{fleet['stale_24h']} devices stale for 24h+")
    if fleet["pending_discoveries"] > 0:
        _add_attention(attention, "warning", "pending_discoveries", f"{fleet['pending_discoveries']} pending discoveries need approval")
    if provisioning["errors_15m"] > 0:
        _add_attention(attention, "warning", "provisioning_errors", f"{provisioning['errors_15m']} provisioning errors in the last 15m")
    hit_ratio = provisioning["cache_hit_ratio_15m"]
    if hit_ratio is not None and provisioning["requests_15m"] >= 10 and hit_ratio < 0.95:
        _add_attention(attention, "warning", "low_cache_hit_ratio", "Cache hit ratio is below 95% over the last 15m")
    if checkin_depth is not None and checkin_depth > settings.checkin_flush_batch * 2:
        _add_attention(attention, "warning", "checkin_buffer_backlog", f"Check-in buffer depth is {checkin_depth}")
    if discovery_depth is not None and discovery_depth > settings.discovery_flush_batch * 2:
        _add_attention(attention, "warning", "discovery_buffer_backlog", f"Discovery buffer depth is {discovery_depth}")

    return ProvisioningReadinessOut(
        generated_at=generated_at,
        status=_status_from_attention(attention),
        fleet=fleet,
        provisioning=provisioning,
        buffers={
            "checkin_buffer_depth": checkin_depth,
            "discovery_buffer_depth": discovery_depth,
        },
        runtime={
            "db_connected": db_connected,
            "redis_connected": redis_connected,
            "worker_connected": runtime_worker_connected,
            "beat_connected": beat_connected,
        },
        attention=attention,
    )
