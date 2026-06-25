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
from app.models.admin import AdminUser, ApiKey
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
async def me(principal: Principal = Depends(get_principal)) -> dict:
    return {
        "kind": principal.kind,
        "id": principal.id,
        "tenant_id": principal.tenant_id,
        "permissions": sorted(principal.permissions),
    }


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
