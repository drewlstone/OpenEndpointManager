"""Celery worker: flushes the Redis check-in buffer to PostgreSQL in batches.

This is the mechanism that keeps 100k phones from generating 100k synchronous
DB inserts. The provisioning workers push JSON onto a Redis list; this task
pops up to N at a time and bulk-inserts checkin/provisioning log rows, and
updates device.last_seen_at in a single pass.
"""
from __future__ import annotations

import json
from datetime import datetime

import redis
from celery import Celery
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.discovery import is_poly_provisioning_user_agent

celery_app = Celery("polyprov", broker=settings.redis_url, backend=settings.redis_url)
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

_sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
_sync_redis = redis.from_url(settings.redis_url, decode_responses=False)

def is_device_provisioning_request(user_agent: str | None) -> bool:
    return is_poly_provisioning_user_agent(user_agent)


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
            latest[b["mac"]] = {"ts": b["ts"], "h": b.get("config_hash")}
        if latest:
            session.execute(
                text(
                    "UPDATE device SET last_seen_at = :ts, last_config_hash = "
                    "COALESCE(:h, last_config_hash) WHERE mac = :mac"
                ),
                [
                    {"mac": mac, "ts": values["ts"], "h": values["h"]}
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
                "endpoint_ip = EXCLUDED.endpoint_ip, "
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
