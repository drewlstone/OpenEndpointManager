from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.db import get_db
from app.models.admin import CheckinEvent, ErrorLog, ProvisioningLog
from app.models.device import Device
from app.models.org import Site, Tenant

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("device:read")),
) -> dict:
    """Aggregate counts for the dashboard landing page."""
    dev_q = select(func.count()).select_from(Device)
    if principal.tenant_id is not None:
        dev_q = dev_q.where(Device.tenant_id == principal.tenant_id)
    total_devices = (await db.execute(dev_q)).scalar_one()

    # devices seen in the last 15 minutes are "online"
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    online_q = select(func.count()).select_from(Device).where(Device.last_seen_at >= cutoff)
    if principal.tenant_id is not None:
        online_q = online_q.where(Device.tenant_id == principal.tenant_id)
    online = (await db.execute(online_q)).scalar_one()

    # stale: never seen or not seen in 24h
    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    stale_q = select(func.count()).select_from(Device).where(
        (Device.last_seen_at.is_(None)) | (Device.last_seen_at < stale_cutoff)
    )
    if principal.tenant_id is not None:
        stale_q = stale_q.where(Device.tenant_id == principal.tenant_id)
    stale = (await db.execute(stale_q)).scalar_one()

    tenants = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one()
    sites = (await db.execute(select(func.count()).select_from(Site))).scalar_one()

    # provisioning activity in last hour
    hour_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    prov_count = (
        await db.execute(
            select(func.count()).select_from(ProvisioningLog).where(
                ProvisioningLog.ts >= hour_cutoff
            )
        )
    ).scalar_one()
    error_count = (
        await db.execute(
            select(func.count()).select_from(ProvisioningLog).where(
                ProvisioningLog.ts >= hour_cutoff, ProvisioningLog.status_code >= 400
            )
        )
    ).scalar_one()

    # device count by model
    model_rows = await db.execute(
        select(Device.model, func.count()).group_by(Device.model)
    )
    by_model = {m: c for m, c in model_rows.all()}

    return {
        "total_devices": total_devices,
        "online": online,
        "stale": stale,
        "tenants": tenants,
        "sites": sites,
        "provisioning_last_hour": prov_count,
        "errors_last_hour": error_count,
        "by_model": by_model,
    }


@router.get("/provisioning-logs")
async def provisioning_logs(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:read")),
    mac: str | None = None,
    status_min: int | None = Query(default=None, description="filter status_code >= this"),
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[dict]:
    stmt = select(ProvisioningLog)
    if mac:
        stmt = stmt.where(ProvisioningLog.mac == mac.replace(":", "").replace("-", "").lower())
    if status_min is not None:
        stmt = stmt.where(ProvisioningLog.status_code >= status_min)
    stmt = stmt.order_by(ProvisioningLog.ts.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id, "mac": r.mac, "ts": r.ts.isoformat() if r.ts else None,
            "path": r.path, "status_code": r.status_code,
            "cache_hit": r.cache_hit, "bytes": r.bytes,
        }
        for r in rows
    ]


@router.get("/checkins")
async def checkins(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:read")),
    mac: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[dict]:
    stmt = select(CheckinEvent)
    if mac:
        stmt = stmt.where(CheckinEvent.mac == mac.replace(":", "").replace("-", "").lower())
    stmt = stmt.order_by(CheckinEvent.ts.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id, "mac": r.mac, "ip": r.ip,
            "ts": r.ts.isoformat() if r.ts else None,
            "user_agent": r.user_agent, "config_hash": r.config_hash,
        }
        for r in rows
    ]


@router.get("/errors")
async def errors(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:read")),
    limit: int = Query(default=100, le=1000),
) -> list[dict]:
    rows = (
        await db.execute(
            select(ErrorLog).order_by(ErrorLog.ts.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id, "mac": r.mac, "ts": r.ts.isoformat() if r.ts else None,
            "kind": r.kind, "detail": r.detail,
        }
        for r in rows
    ]
