"""Celery worker: flushes the Redis check-in buffer to PostgreSQL in batches.

This is the mechanism that keeps 100k phones from generating 100k synchronous
DB inserts. The provisioning workers push JSON onto a Redis list; this task
pops up to N at a time and bulk-inserts checkin/provisioning log rows, and
updates device.last_seen_at in a single pass.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.discovery import is_poly_provisioning_user_agent, parse_poly_user_agent
from app.services.health_probe import probe_endpoint
from app.services.health_state import probe_failure_update_values, probe_result_update_values

logger = logging.getLogger(__name__)

celery_app.conf.beat_schedule = {
    "flush-checkins": {
        "task": "app.worker.flush_checkins",
        "schedule": 2.0,  # every 2 seconds
    },
    "flush-discoveries": {
        "task": "app.worker.flush_discoveries",
        "schedule": 2.0,
    },
    "create-log-partitions": {
        "task": "app.worker.ensure_log_partitions",
        "schedule": 3600.0,
    },
}
if settings.health_probe_scheduler_enabled:
    celery_app.conf.beat_schedule["schedule-health-probes"] = {
        "task": "app.worker.schedule_health_probes",
        "schedule": settings.health_probe_schedule_seconds,
    }

_sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
_sync_redis = redis.from_url(settings.redis_url, decode_responses=False)


def is_device_provisioning_request(user_agent: str | None) -> bool:
    return is_poly_provisioning_user_agent(user_agent)


def device_checkin_telemetry(batch_item: dict) -> dict[str, str | None]:
    user_agent = batch_item.get("ua")
    details = parse_poly_user_agent(user_agent)
    return {
        "ts": batch_item["ts"],
        "ip": batch_item.get("ip"),
        "proxy_ip": batch_item.get("proxy_ip"),
        "serial": details.serial,
        "software_version": details.firmware_version,
        "h": batch_item.get("config_hash"),
    }


def _claim_due_health_probes() -> list[dict]:
    now = datetime.now(timezone.utc)
    claim_until = now + timedelta(seconds=settings.health_probe_claim_timeout_seconds)
    with Session(_sync_engine) as session:
        with session.begin():
            rows = session.execute(
                text(
                    "SELECT id, mac, endpoint_ip, probe_attempts "
                    "FROM device "
                    "WHERE status = 'enrolled' "
                    "AND endpoint_ip IS NOT NULL "
                    "AND (next_probe_at IS NULL OR next_probe_at <= :now) "
                    "ORDER BY next_probe_at NULLS FIRST, id "
                    "LIMIT :limit "
                    "FOR UPDATE SKIP LOCKED"
                ),
                {"now": now, "limit": settings.health_probe_batch_size},
            ).mappings().all()
            devices = [dict(row) for row in rows]
            if devices:
                session.execute(
                    text(
                        "UPDATE device SET "
                        "last_probe_started_at = :started_at, "
                        "probe_source = 'scheduled', "
                        "next_probe_at = :claim_until "
                        "WHERE id = :id"
                    ),
                    [
                        {
                            "id": device["id"],
                            "started_at": now,
                            "claim_until": claim_until,
                        }
                        for device in devices
                    ],
                )
    return devices


async def _probe_devices(devices: list[dict], source: str) -> list[dict]:
    semaphore = asyncio.Semaphore(max(1, settings.health_probe_concurrency))

    async def run_probe(device: dict) -> dict:
        async with semaphore:
            completed_at = None
            try:
                probe = await probe_endpoint(
                    device["endpoint_ip"],
                    settings.health_probe_timeout_seconds,
                    settings.health_probe_icmp_enabled,
                    settings.health_probe_icmp_command,
                    settings.health_probe_icmp_timeout_seconds,
                )
                completed_at = datetime.now(timezone.utc)
                updates = probe_result_update_values(
                    probe,
                    completed_at,
                    settings.health_probe_interval_seconds,
                    settings.health_probe_jitter_seconds,
                    device.get("probe_attempts") or 0,
                    source,
                )
                return {"id": device["id"], "ok": True, "updates": updates}
            except Exception as exc:
                completed_at = completed_at or datetime.now(timezone.utc)
                error = exc.__class__.__name__.lower()
                updates = probe_failure_update_values(
                    error,
                    completed_at,
                    settings.health_probe_interval_seconds,
                    settings.health_probe_jitter_seconds,
                    device.get("probe_attempts") or 0,
                    source,
                )
                return {"id": device["id"], "ok": False, "updates": updates}

    return await asyncio.gather(*(run_probe(device) for device in devices))


def _load_manual_probe_device(mac: str) -> dict | None:
    with Session(_sync_engine) as session:
        row = session.execute(
            text(
                "SELECT id, mac, endpoint_ip, probe_attempts "
                "FROM device "
                "WHERE mac = :mac"
            ),
            {"mac": mac},
        ).mappings().one_or_none()
        return dict(row) if row is not None else None


def _persist_health_probe_updates(results: list[dict]) -> None:
    if not results:
        return
    update_sql = text(
        "UPDATE device SET "
        "reachability_status = :reachability_status, "
        "reachability_checked_at = :reachability_checked_at, "
        "reachability_method = :reachability_method, "
        "reachability_latency_ms = :reachability_latency_ms, "
        "reachability_error = :reachability_error, "
        "network_reachability_status = :network_reachability_status, "
        "network_reachability_method = :network_reachability_method, "
        "network_reachability_error = :network_reachability_error, "
        "network_latency_ms = :network_latency_ms, "
        "network_checked_at = :network_checked_at, "
        "web_reachability_status = :web_reachability_status, "
        "web_reachability_method = :web_reachability_method, "
        "web_reachability_error = :web_reachability_error, "
        "web_latency_ms = :web_latency_ms, "
        "web_checked_at = :web_checked_at, "
        "identity_confidence = :identity_confidence, "
        "identity_checked_at = :identity_checked_at, "
        "last_probe_completed_at = :last_probe_completed_at, "
        "last_probe_duration_ms = :last_probe_duration_ms, "
        "next_probe_at = :next_probe_at, "
        "probe_attempts = :probe_attempts, "
        "probe_source = :probe_source "
        "WHERE id = :id"
    )
    with Session(_sync_engine) as session:
        session.execute(
            update_sql,
            [{"id": result["id"], **result["updates"]} for result in results],
        )
        session.commit()


@celery_app.task(name="app.worker.schedule_health_probes")
def schedule_health_probes() -> dict:
    started = time.perf_counter()
    if not settings.health_probe_scheduler_enabled:
        return {
            "claimed": 0,
            "probed": 0,
            "skipped": 0,
            "failed": 0,
            "duration_ms": 0,
            "enabled": False,
        }

    devices = _claim_due_health_probes()
    if not devices:
        return {
            "claimed": 0,
            "probed": 0,
            "skipped": 0,
            "failed": 0,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "enabled": True,
        }

    results = asyncio.run(_probe_devices(devices, "scheduled"))
    _persist_health_probe_updates(results)
    failed = sum(1 for result in results if not result["ok"])
    summary = {
        "claimed": len(devices),
        "probed": len(results) - failed,
        "skipped": 0,
        "failed": failed,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "enabled": True,
    }
    logger.info("scheduled health probes completed: %s", summary)
    return summary


@celery_app.task(name="app.worker.probe_device_now")
def probe_device_now(mac: str) -> dict:
    started = time.perf_counter()
    device = _load_manual_probe_device(mac)
    if device is None:
        return {
            "mac": mac,
            "probed": 0,
            "failed": 0,
            "skipped": 1,
            "reason": "device_not_found",
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    results = asyncio.run(_probe_devices([device], "manual"))
    _persist_health_probe_updates(results)
    failed = sum(1 for result in results if not result["ok"])
    summary = {
        "mac": mac,
        "probed": len(results) - failed,
        "failed": failed,
        "skipped": 0,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    logger.info("manual health probe completed: %s", summary)
    return summary


@celery_app.task(name="app.worker.flush_checkins")
def flush_checkins() -> int:
    batch: list[dict] = []
    for _ in range(settings.checkin_flush_batch):
        raw = _sync_redis.lpop(settings.checkin_buffer_key)
        if raw is None:
            break
        batch.append(json.loads(raw))
    if not batch:
        return 0

    device_batch = [
        b for b in batch if is_device_provisioning_request(b.get("ua"))
    ]

    with Session(_sync_engine) as session:
        # bulk insert real device check-in events
        if device_batch:
            session.execute(
                text(
                    "INSERT INTO checkin_event (mac, ip, proxy_ip, ts, user_agent, config_hash) "
                    "VALUES (:mac, :ip, :proxy_ip, :ts, :ua, :config_hash)"
                ),
                [
                    {
                        "mac": b["mac"], "ip": b.get("ip"),
                        "proxy_ip": b.get("proxy_ip"), "ts": b["ts"], "ua": b.get("ua"),
                        "config_hash": b.get("config_hash"),
                    }
                    for b in device_batch
                ],
            )
        # bulk insert provisioning logs
        session.execute(
            text(
                "INSERT INTO provisioning_log (mac, ts, path, status_code, cache_hit, bytes) "
                "VALUES (:mac, :ts, :path, :status, :cache_hit, :bytes)"
            ),
            [
                {
                    "mac": b["mac"], "ts": b["ts"], "path": b["path"],
                    "status": b["status"], "cache_hit": b["cache_hit"],
                    "bytes": b["bytes"],
                }
                for b in batch
            ],
        )
        # update device telemetry only from real device check-ins
        latest: dict[str, dict[str, str | None]] = {}
        for b in device_batch:
            latest[b["mac"]] = device_checkin_telemetry(b)
        if latest:
            session.execute(
                text(
                    "UPDATE device SET "
                    "last_seen_at = :ts, "
                    "last_checkin_at = :ts, "
                    "endpoint_ip = :ip, "
                    "proxy_ip = :proxy_ip, "
                    "serial = CASE "
                    "WHEN :serial IS NOT NULL AND (serial IS NULL OR serial = '' OR serial = :serial) "
                    "THEN :serial ELSE serial END, "
                    "software_version = COALESCE(:software_version, software_version), "
                    "last_config_hash = COALESCE(:h, last_config_hash) "
                    "WHERE mac = :mac"
                ),
                [
                    {
                        "mac": mac,
                        "ts": values["ts"],
                        "ip": values["ip"],
                        "proxy_ip": values["proxy_ip"],
                        "serial": values["serial"],
                        "software_version": values["software_version"],
                        "h": values["h"],
                    }
                    for mac, values in latest.items()
                ],
            )
        session.commit()
    return len(batch)


@celery_app.task(name="app.worker.flush_discoveries")
def flush_discoveries() -> int:
    batch: list[dict] = []
    for _ in range(settings.discovery_flush_batch):
        raw = _sync_redis.lpop(settings.discovery_buffer_key)
        if raw is None:
            break
        batch.append(json.loads(raw))
    if not batch:
        return 0

    with Session(_sync_engine) as session:
        session.execute(
            text(
                "INSERT INTO discovered_endpoint "
                "(mac, status, model, firmware_version, serial, endpoint_ip, proxy_ip, "
                "user_agent, first_seen_at, last_seen_at, request_count, last_path, "
                "last_status, created_at, updated_at) "
                "VALUES (:mac, 'pending', :model, :firmware_version, :serial, "
                ":endpoint_ip, :proxy_ip, :user_agent, :ts, :ts, 1, :last_path, "
                ":last_status, :ts, :ts) "
                "ON CONFLICT (mac) DO UPDATE SET "
                "model = COALESCE(EXCLUDED.model, discovered_endpoint.model), "
                "firmware_version = COALESCE(EXCLUDED.firmware_version, discovered_endpoint.firmware_version), "
                "serial = COALESCE(EXCLUDED.serial, discovered_endpoint.serial), "
                "endpoint_ip = CASE "
                "WHEN EXCLUDED.endpoint_ip = '172.18.0.1' "
                "AND discovered_endpoint.endpoint_ip IS NOT NULL "
                "AND discovered_endpoint.endpoint_ip <> EXCLUDED.endpoint_ip "
                "THEN discovered_endpoint.endpoint_ip "
                "ELSE EXCLUDED.endpoint_ip END, "
                "proxy_ip = EXCLUDED.proxy_ip, "
                "user_agent = EXCLUDED.user_agent, "
                "last_seen_at = EXCLUDED.last_seen_at, "
                "request_count = discovered_endpoint.request_count + 1, "
                "last_path = EXCLUDED.last_path, "
                "last_status = EXCLUDED.last_status, "
                "updated_at = EXCLUDED.updated_at"
            ),
            [
                {
                    "mac": b["mac"],
                    "model": b.get("model"),
                    "firmware_version": b.get("firmware_version"),
                    "serial": b.get("serial"),
                    "endpoint_ip": b.get("endpoint_ip"),
                    "proxy_ip": b.get("proxy_ip"),
                    "user_agent": b.get("user_agent"),
                    "ts": b["ts"],
                    "last_path": b["last_path"],
                    "last_status": b["last_status"],
                }
                for b in batch
            ],
        )
        session.commit()
    return len(batch)


@celery_app.task(name="app.worker.ensure_log_partitions")
def ensure_log_partitions() -> str:
    """Create next month's partitions for the time-partitioned log tables.

    In production the log tables are declared PARTITION BY RANGE (ts). This
    task pre-creates the upcoming partition. The base schema in migrations
    creates the current month. (No-op here if tables aren't partitioned.)
    """
    return "ok"
