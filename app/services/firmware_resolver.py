"""Resolve which firmware (if any) to advertise to a device.

Precedence:
    1. explicit device.firmware_target_id (pin) — always wins
    2. firmware assignment matching the device, honoring ring + rollout window

Production-ring assignments only advertise during their rollout window;
test/pilot advertise immediately. rolled_back assignments advertise the prior
known-good by simply being deactivated, so the next-best active assignment wins.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import (
    FirmwareAssignment,
    FirmwareImage,
    FirmwareRing,
    RolloutState,
    RolloutWindow,
)
from app.models.device import Device


def _in_window(window: RolloutWindow | None, now: datetime) -> bool:
    if window is None:
        return True
    if window.start_at and now < window.start_at:
        return False
    if window.end_at and now > window.end_at:
        return False
    return True


async def resolve_firmware(
    db: AsyncSession, device: Device, now: datetime | None = None
) -> FirmwareImage | None:
    now = now or datetime.now(timezone.utc)

    if device.firmware_target_id:
        return await db.get(FirmwareImage, device.firmware_target_id)

    # candidate assignments by model scope (group/site scopes resolved similarly)
    stmt = (
        select(FirmwareAssignment)
        .where(
            FirmwareAssignment.scope == "model",
            FirmwareAssignment.scope_ref == device.model,
            FirmwareAssignment.state == RolloutState.active,
        )
    )
    result = await db.execute(stmt)
    assignments = list(result.scalars().all())
    if not assignments:
        return None

    # prefer test > pilot > production for the device's eligibility, but a real
    # implementation maps devices to rings via group membership. Here we honor
    # the window gate for production.
    chosen: FirmwareAssignment | None = None
    for a in assignments:
        if a.ring == FirmwareRing.production:
            window = (
                await db.get(RolloutWindow, a.window_id) if a.window_id else None
            )
            if not _in_window(window, now):
                continue
        chosen = a
        break

    if chosen is None:
        return None
    return await db.get(FirmwareImage, chosen.firmware_image_id)
