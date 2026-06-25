from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.db import get_db
from app.core.redis_client import bump_device_generation
from app.core.security import normalize_mac
from app.models.device import Device
from app.schemas import DeviceCreate, DeviceImportResult, DeviceOut
from app.services.device_import import import_devices

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceOut, status_code=201)
async def create_device(
    req: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:write")),
) -> Device:
    mac = normalize_mac(req.mac)
    existing = await db.execute(select(Device).where(Device.mac == mac))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "device already exists")
    device = Device(
        tenant_id=req.tenant_id, mac=mac, model=req.model,
        site_id=req.site_id, primary_group_id=req.primary_group_id,
        serial=req.serial, label=req.label,
    )
    db.add(device)
    await db.flush()
    return device


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("device:read")),
    tenant_id: int | None = None,
    site_id: int | None = None,
    model: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[Device]:
    stmt = select(Device)
    # tenant-scoped principals only see their tenant
    if principal.tenant_id is not None:
        stmt = stmt.where(Device.tenant_id == principal.tenant_id)
    elif tenant_id is not None:
        stmt = stmt.where(Device.tenant_id == tenant_id)
    if site_id is not None:
        stmt = stmt.where(Device.site_id == site_id)
    if model is not None:
        stmt = stmt.where(Device.model == model)
    if status_filter is not None:
        stmt = stmt.where(Device.status == status_filter)
    stmt = stmt.order_by(Device.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{mac}", response_model=DeviceOut)
async def get_device(
    mac: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:read")),
) -> Device:
    norm = normalize_mac(mac)
    result = await db.execute(select(Device).where(Device.mac == norm))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    return device


@router.post("/{mac}/assign-profile/{template_id}", response_model=DeviceOut)
async def assign_profile(
    mac: str,
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:write")),
) -> Device:
    norm = normalize_mac(mac)
    result = await db.execute(select(Device).where(Device.mac == norm))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    device.config_profile_id = template_id
    await bump_device_generation(norm)
    await db.flush()
    return device


@router.post("/import", response_model=DeviceImportResult)
async def import_endpoint(
    file: UploadFile,
    fmt: str = Query(default="csv", pattern="^(csv|json)$"),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:write")),
) -> DeviceImportResult:
    content = await file.read()
    return await import_devices(db, content, fmt)


@router.get("/export/csv")
async def export_csv(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("device:read")),
) -> StreamingResponse:
    stmt = select(Device)
    if principal.tenant_id is not None:
        stmt = stmt.where(Device.tenant_id == principal.tenant_id)
    result = await db.execute(stmt)
    devices = result.scalars().all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["mac", "tenant_id", "model", "site_id", "label", "status"])
        yield buf.getvalue()
        for d in devices:
            buf.seek(0); buf.truncate()
            writer.writerow([d.mac, d.tenant_id, d.model, d.site_id or "",
                             d.label or "", d.status])
            yield buf.getvalue()

    return StreamingResponse(
        generate(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=devices.csv"},
    )
