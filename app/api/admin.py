from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.db import get_db
from app.core.redis_client import bump_global_generation
from app.models.config import (
    ConfigTemplate,
    FirmwareAssignment,
    FirmwareImage,
    FirmwareRing,
    RolloutState,
    TemplateScope,
)
from app.models.org import DeviceGroup, GroupKind, Site, Tenant
from app.schemas import (
    FirmwareAssignmentCreate,
    FirmwareOut,
    GroupCreate,
    GroupOut,
    SiteCreate,
    SiteOut,
    TemplateCreate,
    TemplateOut,
    TenantCreate,
    TenantOut,
)

router = APIRouter(tags=["org"])


# ---- Tenants ----

@router.post("/tenants", response_model=TenantOut, status_code=201)
async def create_tenant(req: TenantCreate, db: AsyncSession = Depends(get_db),
                        _: Principal = Depends(require_permission("tenant:write"))) -> Tenant:
    tenant = Tenant(slug=req.slug, name=req.name)
    db.add(tenant)
    await db.flush()
    return tenant


@router.get("/tenants", response_model=list[TenantOut])
async def list_tenants(db: AsyncSession = Depends(get_db),
                       _: Principal = Depends(require_permission("tenant:read"))) -> list[Tenant]:
    result = await db.execute(select(Tenant).order_by(Tenant.id))
    return list(result.scalars().all())


# ---- Sites ----

@router.post("/sites", response_model=SiteOut, status_code=201)
async def create_site(req: SiteCreate, db: AsyncSession = Depends(get_db),
                      _: Principal = Depends(require_permission("site:write"))) -> Site:
    site = Site(tenant_id=req.tenant_id, name=req.name,
                region=req.region, timezone=req.timezone)
    db.add(site)
    await db.flush()
    return site


@router.get("/sites", response_model=list[SiteOut])
async def list_sites(tenant_id: int | None = None, db: AsyncSession = Depends(get_db),
                     _: Principal = Depends(require_permission("site:read"))) -> list[Site]:
    stmt = select(Site)
    if tenant_id:
        stmt = stmt.where(Site.tenant_id == tenant_id)
    result = await db.execute(stmt.order_by(Site.id))
    return list(result.scalars().all())


# ---- Groups ----

@router.post("/groups", response_model=GroupOut, status_code=201)
async def create_group(req: GroupCreate, db: AsyncSession = Depends(get_db),
                       _: Principal = Depends(require_permission("group:write"))) -> DeviceGroup:
    group = DeviceGroup(
        tenant_id=req.tenant_id, name=req.name, kind=GroupKind(req.kind),
        site_id=req.site_id, parent_group_id=req.parent_group_id, priority=req.priority,
    )
    db.add(group)
    await db.flush()
    return group


@router.get("/groups", response_model=list[GroupOut])
async def list_groups(tenant_id: int | None = None, db: AsyncSession = Depends(get_db),
                      _: Principal = Depends(require_permission("group:read"))) -> list[DeviceGroup]:
    stmt = select(DeviceGroup)
    if tenant_id:
        stmt = stmt.where(DeviceGroup.tenant_id == tenant_id)
    result = await db.execute(stmt.order_by(DeviceGroup.priority))
    return list(result.scalars().all())


# ---- Templates ----

@router.post("/templates", response_model=TemplateOut, status_code=201)
async def create_template(req: TemplateCreate, db: AsyncSession = Depends(get_db),
                          _: Principal = Depends(require_permission("template:write"))) -> ConfigTemplate:
    scope = TemplateScope("global" if req.scope == "global" else req.scope)
    tpl = ConfigTemplate(
        name=req.name, scope=scope, scope_ref=req.scope_ref,
        tenant_id=req.tenant_id, parent_id=req.parent_id,
        body=req.body, priority=req.priority,
    )
    db.add(tpl)
    await db.flush()
    await bump_global_generation()  # any template change invalidates caches
    return tpl


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(scope: str | None = None, db: AsyncSession = Depends(get_db),
                         _: Principal = Depends(require_permission("template:read"))) -> list[ConfigTemplate]:
    stmt = select(ConfigTemplate)
    if scope:
        stmt = stmt.where(ConfigTemplate.scope == TemplateScope(scope))
    result = await db.execute(stmt.order_by(ConfigTemplate.priority))
    return list(result.scalars().all())


# ---- Firmware ----

@router.get("/firmware", response_model=list[FirmwareOut])
async def list_firmware(model: str | None = None, db: AsyncSession = Depends(get_db),
                        _: Principal = Depends(require_permission("firmware:read"))) -> list[FirmwareImage]:
    stmt = select(FirmwareImage)
    if model:
        stmt = stmt.where(FirmwareImage.model == model)
    result = await db.execute(stmt.order_by(FirmwareImage.id))
    return list(result.scalars().all())


@router.post("/firmware", response_model=FirmwareOut, status_code=201)
async def register_firmware(
    model: str,
    version: str,
    object_key: str,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("firmware:write")),
) -> FirmwareImage:
    """Register a firmware image already uploaded to the object store.

    In production the binary is uploaded to S3 out-of-band (or via a presigned
    URL); this records the metadata and sha256 placeholder. The upload helper in
    tools/ computes the real hash.
    """
    import hashlib

    existing = await db.execute(
        select(FirmwareImage).where(
            FirmwareImage.model == model, FirmwareImage.version == version
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "firmware version exists")
    img = FirmwareImage(
        model=model, version=version, object_key=object_key,
        sha256=hashlib.sha256(object_key.encode()).hexdigest(), size_bytes=0,
    )
    db.add(img)
    await db.flush()
    return img


@router.get("/firmware/assignments")
async def list_assignments(db: AsyncSession = Depends(get_db),
                           _: Principal = Depends(require_permission("firmware:read"))) -> list[dict]:
    rows = (await db.execute(select(FirmwareAssignment).order_by(FirmwareAssignment.id))).scalars().all()
    return [
        {
            "id": a.id, "scope": a.scope, "scope_ref": a.scope_ref,
            "firmware_image_id": a.firmware_image_id, "ring": a.ring.value,
            "state": a.state.value, "window_id": a.window_id,
        }
        for a in rows
    ]


@router.post("/firmware/assignments", status_code=201)
async def create_assignment(req: FirmwareAssignmentCreate, db: AsyncSession = Depends(get_db),
                            _: Principal = Depends(require_permission("firmware:write"))) -> dict:
    assignment = FirmwareAssignment(
        scope=req.scope, scope_ref=req.scope_ref,
        firmware_image_id=req.firmware_image_id,
        ring=FirmwareRing(req.ring), state=RolloutState.active,
        window_id=req.window_id,
    )
    db.add(assignment)
    await db.flush()
    await bump_global_generation()
    return {"id": assignment.id, "state": assignment.state.value}


@router.post("/firmware/assignments/{assignment_id}/rollback")
async def rollback_assignment(assignment_id: int, db: AsyncSession = Depends(get_db),
                              _: Principal = Depends(require_permission("firmware:write"))) -> dict:
    assignment = await db.get(FirmwareAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "assignment not found")
    assignment.state = RolloutState.rolled_back
    await db.flush()
    await bump_global_generation()
    return {"id": assignment_id, "state": assignment.state.value}
