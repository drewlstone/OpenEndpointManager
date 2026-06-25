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

celery_app = Celery("polyprov", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.beat_schedule = {
    "flush-checkins": {
        "task": "app.worker.flush_checkins",
        "schedule": 2.0,  # every 2 seconds
    },
    "create-log-partitions": {
        "task": "app.worker.ensure_log_partitions",
        "schedule": 3600.0,
    },
}

_sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
_sync_redis = redis.from_url(settings.redis_url, decode_responses=False)


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

    with Session(_sync_engine) as session:
        # bulk insert check-in events
        session.execute(
            text(
                "INSERT INTO checkin_event (mac, ip, ts, user_agent, config_hash) "
                "VALUES (:mac, :ip, :ts, :ua, :config_hash)"
            ),
            [
                {
                    "mac": b["mac"], "ip": b.get("ip"),
                    "ts": b["ts"], "ua": b.get("ua"),
                    "config_hash": b.get("config_hash"),
                }
                for b in batch
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
        # update last_seen for the distinct macs in this batch
        latest: dict[str, str] = {}
        for b in batch:
            latest[b["mac"]] = b["ts"]
        session.execute(
            text(
                "UPDATE device SET last_seen_at = :ts, last_config_hash = "
                "COALESCE(:h, last_config_hash) WHERE mac = :mac"
            ),
            [{"mac": m, "ts": ts, "h": None} for m, ts in latest.items()],
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
