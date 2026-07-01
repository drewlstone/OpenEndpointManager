from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal, require_permission
from app.core.db import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    verify_password,
)
from app.models.admin import AdminUser, ApiKey, Role, UserRole
from app.models.org import Tenant
from app.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    LoginRequest,
    Token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> Token:
    result = await db.execute(select(AdminUser).where(AdminUser.email == req.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "inactive user")
    return Token(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=Token)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)) -> Token:
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")
    sub = payload["sub"]
    return Token(
        access_token=create_access_token(sub),
        refresh_token=create_refresh_token(sub),
    )


@router.get("/me")
async def me(
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tenant_name = None
    if principal.tenant_id is not None:
        tenant = await db.get(Tenant, principal.tenant_id)
        tenant_name = tenant.name if tenant else None

    base = {
        "kind": principal.kind,
        "id": principal.id,
        "tenant_id": principal.tenant_id,
        "tenant_name": tenant_name,
        "permissions": sorted(principal.permissions),
    }

    if principal.kind == "user":
        user = await db.get(AdminUser, int(principal.id))
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "inactive user")
        role_rows = await db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
        )
        return {
            **base,
            "email": user.email,
            "display_name": user.email,
            "roles": list(role_rows.scalars().all()),
        }

    if principal.kind == "api_key":
        api_key = await db.get(ApiKey, int(principal.id))
        name = api_key.name if api_key else None
        return {
            **base,
            "name": name,
            "display_name": f"API key: {name}" if name else f"API key #{principal.id}",
            "roles": [],
        }

    return {**base, "display_name": principal.kind, "roles": []}


@router.post("/api-keys", response_model=ApiKeyCreated)
async def create_api_key(
    req: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_permission("api_key:create")),
) -> ApiKeyCreated:
    full, prefix, digest = generate_api_key()
    key = ApiKey(
        tenant_id=req.tenant_id,
        name=req.name,
        hashed_key=digest,
        prefix=prefix,
        scopes=req.scopes,
    )
    db.add(key)
    await db.flush()
    return ApiKeyCreated(id=key.id, name=key.name, api_key=full, prefix=prefix)
