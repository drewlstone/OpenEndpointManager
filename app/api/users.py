from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.db import get_db
from app.core.security import hash_password
from app.models.admin import (
    AdminUser,
    Permission,
    Role,
    RolePermission,
    UserRole,
)

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    tenant_id: int | None = None
    role_ids: list[int] = []


class RoleCreate(BaseModel):
    name: str
    permission_names: list[str] = []


@router.get("")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("user:read")),
) -> list[dict]:
    users = (await db.execute(select(AdminUser).order_by(AdminUser.id))).scalars().all()
    out = []
    for u in users:
        role_rows = await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == u.id)
        )
        out.append({
            "id": u.id, "email": u.email, "is_active": u.is_active,
            "tenant_id": u.tenant_id, "roles": list(role_rows.scalars().all()),
        })
    return out


@router.post("", status_code=201)
async def create_user(
    req: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("user:write")),
) -> dict:
    existing = await db.execute(select(AdminUser).where(AdminUser.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "user already exists")
    user = AdminUser(
        email=req.email, hashed_password=hash_password(req.password),
        tenant_id=req.tenant_id,
    )
    db.add(user)
    await db.flush()
    for rid in req.role_ids:
        db.add(UserRole(user_id=user.id, role_id=rid))
    return {"id": user.id, "email": user.email}


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("user:write")),
) -> dict:
    user = await db.get(AdminUser, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    user.is_active = False
    return {"id": user_id, "is_active": False}


@router.get("/roles/all")
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("user:read")),
) -> list[dict]:
    roles = (await db.execute(select(Role).order_by(Role.id))).scalars().all()
    out = []
    for r in roles:
        perm_rows = await db.execute(
            select(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == r.id)
        )
        out.append({"id": r.id, "name": r.name, "permissions": list(perm_rows.scalars().all())})
    return out


@router.post("/roles", status_code=201)
async def create_role(
    req: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("user:write")),
) -> dict:
    role = Role(name=req.name)
    db.add(role)
    await db.flush()
    for pname in req.permission_names:
        perm = (await db.execute(select(Permission).where(Permission.name == pname))).scalar_one_or_none()
        if perm:
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    return {"id": role.id, "name": role.name}


@router.get("/permissions/all")
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("user:read")),
) -> list[str]:
    perms = (await db.execute(select(Permission.name).order_by(Permission.name))).scalars().all()
    return list(perms)
