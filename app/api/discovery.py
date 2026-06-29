from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_permission
from app.core.db import get_db
from app.models.discovery import DiscoveredEndpoint
from app.schemas import DiscoveredEndpointOut

router = APIRouter(prefix="/discoveries", tags=["discoveries"])


@router.get("", response_model=list[DiscoveredEndpointOut])
async def list_discoveries(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_permission("device:read")),
    status_filter: str = Query(default="pending", alias="status"),
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[DiscoveredEndpoint]:
    if principal.tenant_id is not None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "pending discoveries are only visible to global administrators",
        )

    stmt = select(DiscoveredEndpoint)
    if status_filter:
        stmt = stmt.where(DiscoveredEndpoint.status == status_filter)
    stmt = stmt.order_by(DiscoveredEndpoint.last_seen_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())
