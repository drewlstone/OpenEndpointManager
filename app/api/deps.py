from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token, hash_api_key
from app.models.admin import (
    AdminUser,
    ApiKey,
    Permission,
    Role,
    RolePermission,
    UserRole,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


class Principal:
    def __init__(self, kind: str, id_: str, tenant_id: int | None,
                 permissions: set[str]):
        self.kind = kind
        self.id = id_
        self.tenant_id = tenant_id
        self.permissions = permissions


async def _permissions_for_user(db: AsyncSession, user_id: int) -> set[str]:
    stmt = (
        select(Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    result = await db.execute(stmt)
    return set(result.scalars().all())


async def get_principal(
    token: str | None = Depends(oauth2_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    # API key path
    if x_api_key:
        digest = hash_api_key(x_api_key)
        result = await db.execute(select(ApiKey).where(ApiKey.hashed_key == digest))
        api_key = result.scalar_one_or_none()
        if api_key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid API key")
        scopes = set(api_key.scopes or [])
        return Principal("api_key", str(api_key.id), api_key.tenant_id, scopes)

    # JWT path
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong token type")

    user_id = int(payload["sub"])
    user = await db.get(AdminUser, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "inactive user")
    perms = await _permissions_for_user(db, user_id)
    return Principal("user", str(user_id), user.tenant_id, perms)


def require_permission(permission: str):
    async def checker(principal: Principal = Depends(get_principal)) -> Principal:
        # superadmin wildcard
        if "*" in principal.permissions or permission in principal.permissions:
            return principal
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"missing permission: {permission}"
        )
    return checker
