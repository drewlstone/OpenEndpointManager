from __future__ import annotations

import csv
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.db import get_db
from app.core.redis_client import bump_device_generation
from app.core.security import normalize_mac
from app.models.admin import CheckinEvent
from app.models.config import ConfigTemplate, TemplateScope
from app.models.device import Device
from app.models.org import DeviceGroup, Site, Tenant
from app.schemas import DeviceCreate, DeviceImportResult, DeviceInventoryOut, DeviceOut, DeviceUpdate
from app.services.device_import import import_devices

router = APIRouter(prefix="/devices", tags=["devices"])


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _display_model(model: str | None) -> str | None:
    if not model:
        return model
    normalized = model.strip()
    if not normalized:
        return None

    match = re.match(r"^([A-Za-z0-9]+)-\1_(.+)$", normalized)
    if match:
        return f"{match.group(1)} {match.group(2).replace('_', ' ')}"
    return normalized.replace("_", " ")


def _model_search_terms(value: str) -> set[str]:
    normalized = value.strip()
    if not normalized:
        return set()

    terms = {normalized, normalized.replace(" ", "_")}
    parts = normalized.split(maxsplit=1)
    if len(parts) == 2:
        family, model = parts
        terms.add(f"{family}-{family}_{model.replace(' ', '_')}")
    return terms


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


DEVICE_SORTS = {
    "mac": Device.mac,
    "model": Device.model,
    "serial": Device.serial,
    "label": Device.label,
    "asset_tag": Device.asset_tag,
    "tenant": Tenant.name,
    "site": Site.name,
    "group": DeviceGroup.name,
    "status": Device.status,
    "lifecycle_status": Device.status,
    "last_seen_at": Device.last_seen_at,
    "last_checkin_at": Device.last_checkin_at,
    "endpoint_ip": Device.endpoint_ip,
    "software_version": Device.software_version,
    "reachability_status": Device.reachability_status,
    "provisioning_health": Device.provisioning_health,
}


@router.get("", response_model=list[DeviceInventoryOut])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("device:read")),
    tenant_id: int | None = None,
    site_id: int | None = None,
    group_id: int | None = None,
    model: str | None = None,
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    sort: str = Query(default="mac"),
    direction: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[dict]:
    latest_endpoint_ip = (
        select(CheckinEvent.ip)
        .where(
            CheckinEvent.mac == Device.mac,
            CheckinEvent.user_agent.startswith("FileTransport Poly"),
        )
        .order_by(CheckinEvent.ts.desc())
        .limit(1)
        .scalar_subquery()
    )

    endpoint_ip = func.coalesce(Device.endpoint_ip, latest_endpoint_ip)
    last_checkin_at = func.coalesce(Device.last_checkin_at, Device.last_seen_at)

    stmt = (
        select(
            Device.id.label("id"),
            Device.tenant_id.label("tenant_id"),
            Tenant.name.label("tenant_name"),
            Device.site_id.label("site_id"),
            Site.name.label("site_name"),
            Device.primary_group_id.label("primary_group_id"),
            DeviceGroup.name.label("primary_group_name"),
            Device.mac.label("mac"),
            Device.model.label("model"),
            Device.serial.label("serial"),
            Device.label.label("label"),
            Device.asset_tag.label("asset_tag"),
            endpoint_ip.label("endpoint_ip"),
            Device.proxy_ip.label("proxy_ip"),
            Device.software_version.label("software_version"),
            Device.status.label("status"),
            Device.status.label("lifecycle_status"),
            Device.last_seen_at.label("last_seen_at"),
            last_checkin_at.label("last_checkin_at"),
            func.coalesce(Device.reachability_status, literal("unknown")).label("reachability_status"),
            func.coalesce(Device.identity_confidence, literal("unknown")).label("identity_confidence"),
            func.coalesce(Device.provisioning_health, literal("unknown")).label("provisioning_health"),
        )
        .join(Tenant, Tenant.id == Device.tenant_id)
        .outerjoin(Site, Site.id == Device.site_id)
        .outerjoin(DeviceGroup, DeviceGroup.id == Device.primary_group_id)
    )

    # tenant-scoped principals only see their tenant
    if principal.tenant_id is not None:
        stmt = stmt.where(Device.tenant_id == principal.tenant_id)
    elif tenant_id is not None:
        stmt = stmt.where(Device.tenant_id == tenant_id)
    if site_id is not None:
        stmt = stmt.where(Device.site_id == site_id)
    if group_id is not None:
        stmt = stmt.where(Device.primary_group_id == group_id)
    if model is not None:
        stmt = stmt.where(Device.model == model)
    if status_filter is not None:
        stmt = stmt.where(Device.status == status_filter)
    if q:
        term = f"%{q.strip()}%"
        mac_term = f"%{q.replace(':', '').replace('-', '').lower()}%"
        model_filters = [
            Device.model.ilike(f"%{model_term}%")
            for model_term in _model_search_terms(q)
        ]
        stmt = stmt.where(
            or_(
                Device.mac.ilike(mac_term),
                *model_filters,
                Device.serial.ilike(term),
                Device.label.ilike(term),
                Device.asset_tag.ilike(term),
                Device.software_version.ilike(term),
                endpoint_ip.ilike(term),
                Device.proxy_ip.ilike(term),
                Tenant.name.ilike(term),
                Site.name.ilike(term),
                DeviceGroup.name.ilike(term),
            )
        )

    if sort == "endpoint_ip":
        sort_expr = endpoint_ip
    elif sort == "last_checkin_at":
        sort_expr = last_checkin_at
    else:
        sort_expr = DEVICE_SORTS.get(sort, Device.mac)
    order_expr = sort_expr.desc() if direction == "desc" else sort_expr.asc()
    stmt = stmt.order_by(order_expr.nullslast(), Device.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    devices = [dict(row) for row in result.mappings().all()]
    for device in devices:
        device["model_display"] = _display_model(device["model"])
    return devices


@router.get("/{mac}", response_model=DeviceOut)
async def get_device(
    mac: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:read")),
) -> dict:
    norm = normalize_mac(mac)
    result = await db.execute(
        select(
            Device.id.label("id"),
            Device.tenant_id.label("tenant_id"),
            Tenant.name.label("tenant_name"),
            Device.site_id.label("site_id"),
            Site.name.label("site_name"),
            Device.primary_group_id.label("primary_group_id"),
            DeviceGroup.name.label("primary_group_name"),
            Device.mac.label("mac"),
            Device.model.label("model"),
            Device.serial.label("serial"),
            Device.status.label("status"),
            Device.label.label("label"),
            Device.asset_tag.label("asset_tag"),
            Device.config_profile_id.label("config_profile_id"),
            ConfigTemplate.name.label("config_profile_name"),
            Device.last_seen_at.label("last_seen_at"),
            Device.last_checkin_at.label("last_checkin_at"),
            Device.endpoint_ip.label("endpoint_ip"),
            Device.proxy_ip.label("proxy_ip"),
            Device.software_version.label("software_version"),
            func.coalesce(Device.reachability_status, literal("unknown")).label("reachability_status"),
            Device.reachability_checked_at.label("reachability_checked_at"),
            func.coalesce(Device.identity_confidence, literal("unknown")).label("identity_confidence"),
            func.coalesce(Device.provisioning_health, literal("unknown")).label("provisioning_health"),
        )
        .join(Tenant, Tenant.id == Device.tenant_id)
        .outerjoin(Site, Site.id == Device.site_id)
        .outerjoin(DeviceGroup, DeviceGroup.id == Device.primary_group_id)
        .outerjoin(ConfigTemplate, ConfigTemplate.id == Device.config_profile_id)
        .where(Device.mac == norm)
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    device = dict(row)
    device["model_display"] = _display_model(device["model"])
    return device


@router.patch("/{mac}", response_model=DeviceOut)
async def update_device(
    mac: str,
    req: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("device:write")),
) -> Device:
    norm = normalize_mac(mac)
    result = await db.execute(select(Device).where(Device.mac == norm))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    updates = req.model_dump(exclude_unset=True)
    bump_generation = False

    if "site_id" in updates and updates["site_id"] is not None:
        site = await db.get(Site, updates["site_id"])
        if site is None or site.tenant_id != device.tenant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "site must belong to device tenant")

    effective_site_id = updates.get("site_id", device.site_id)
    effective_group_id = updates.get("primary_group_id", device.primary_group_id)
    if effective_group_id is not None:
        group = await db.get(DeviceGroup, effective_group_id)
        if group is None or group.tenant_id != device.tenant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "group must belong to device tenant")
        if group.site_id is not None and group.site_id != effective_site_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "group must belong to selected site")

    if "config_profile_id" in updates and updates["config_profile_id"] is not None:
        template = await db.get(ConfigTemplate, updates["config_profile_id"])
        if template is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "template not found")
        is_global = template.scope == TemplateScope.global_
        belongs_to_tenant = template.tenant_id == device.tenant_id
        if not is_global and not belongs_to_tenant:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "template must be global or belong to device tenant")

    for field in ("label", "asset_tag"):
        if field in updates:
            setattr(device, field, _clean_optional_string(updates[field]))

    if "site_id" in updates and device.site_id != updates["site_id"]:
        device.site_id = updates["site_id"]
        bump_generation = True
    if "primary_group_id" in updates and device.primary_group_id != updates["primary_group_id"]:
        device.primary_group_id = updates["primary_group_id"]
        bump_generation = True
    if "config_profile_id" in updates and device.config_profile_id != updates["config_profile_id"]:
        device.config_profile_id = updates["config_profile_id"]
        bump_generation = True
    if "status" in updates:
        device.status = updates["status"]

    if bump_generation:
        await bump_device_generation(norm)
    await db.flush()
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
