from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import Principal, require_permission
from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.health_engine import HEALTH_SCHEDULER_LAST_RUN_KEY
from app.core.redis_client import redis_client
from app.schemas import HealthEngineRuntimeOut

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
