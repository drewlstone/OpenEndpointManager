from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.db import get_db
from app.models.config import ConfigTemplate
from app.models.device import Device
from app.models.discovery import DiscoveredEndpoint
from app.models.org import DeviceGroup, Site, Tenant
from app.schemas import (
    DiscoveryApproveRequest,
    DiscoveryApproveResult,
    DiscoveredEndpointOut,
    DeviceOut,
)

router = APIRouter(prefix="/discoveries", tags=["discoveries"])


def _require_global_admin(principal: Principal) -> None:
    if principal.tenant_id is not None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "pending discoveries are only visible to global administrators",
        )


@router.get("", response_model=list[DiscoveredEndpointOut])
async def list_discoveries(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("device:read")),
    status_filter: str = Query(default="pending", alias="status"),
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[DiscoveredEndpoint]:
    _require_global_admin(principal)

    stmt = select(DiscoveredEndpoint)
    if status_filter:
        stmt = stmt.where(DiscoveredEndpoint.status == status_filter)
    stmt = stmt.order_by(DiscoveredEndpoint.last_seen_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/{discovery_id}/approve",
    response_model=DiscoveryApproveResult,
    status_code=status.HTTP_201_CREATED,
)
async def approve_discovery(
    discovery_id: int,
    req: DiscoveryApproveRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("device:write")),
) -> DiscoveryApproveResult:
    _require_global_admin(principal)

    discovery_result = await db.execute(
        select(DiscoveredEndpoint)
        .where(DiscoveredEndpoint.id == discovery_id)
        .with_for_update()
    )
    discovery = discovery_result.scalar_one_or_none()
    if discovery is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "discovery not found")
    if discovery.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "discovery is not pending")

    existing_device = await db.execute(select(Device).where(Device.mac == discovery.mac))
    if existing_device.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "device already exists")

    tenant = await db.get(Tenant, req.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "tenant not found")
    if tenant.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "tenant is not active")

    site = await db.get(Site, req.site_id)
    if site is None or site.tenant_id != req.tenant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "site must belong to tenant")

    if req.primary_group_id is not None:
        group = await db.get(DeviceGroup, req.primary_group_id)
        if group is None or group.tenant_id != req.tenant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "group must belong to tenant")
        if group.site_id is not None and group.site_id != req.site_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "group must belong to selected site")

    if req.config_profile_id is not None:
        template = await db.get(ConfigTemplate, req.config_profile_id)
        if template is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "template not found")
        if template.tenant_id is not None and template.tenant_id != req.tenant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "template must belong to tenant")

    model = (req.model or discovery.model or "CCX")[:64]
    serial = req.serial if req.serial is not None else discovery.serial
    if serial is not None:
        serial = serial[:64]

    device = Device(
        tenant_id=req.tenant_id,
        site_id=req.site_id,
        primary_group_id=req.primary_group_id,
        config_profile_id=req.config_profile_id,
        mac=discovery.mac,
        model=model,
        serial=serial,
        label=req.label,
        last_seen_at=discovery.last_seen_at,
        status="enrolled",
    )
    db.add(device)
    await db.flush()

    discovery.status = "approved"
    discovery.approved_device_id = device.id
    discovery.approved_at = datetime.now(timezone.utc)
    discovery.approved_by = f"{principal.kind}:{principal.id}"
    discovery.updated_at = discovery.approved_at
    await db.flush()

    return DiscoveryApproveResult(
        discovery=DiscoveredEndpointOut.model_validate(discovery),
        device=DeviceOut.model_validate(device),
    )
