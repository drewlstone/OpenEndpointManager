from __future__ import annotations

import csv
import io
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import bump_device_generation
from app.core.security import normalize_mac
from app.models.device import Device
from app.schemas import DeviceImportResult


async def _upsert_device(db: AsyncSession, row: dict) -> str:
    """Returns 'created' or 'updated'. Raises ValueError on bad data."""
    mac = normalize_mac(row["mac"])
    tenant_id = int(row["tenant_id"])
    result = await db.execute(select(Device).where(Device.mac == mac))
    device = result.scalar_one_or_none()
    fields = {
        "tenant_id": tenant_id,
        "model": row.get("model") or "CCX",
        "site_id": int(row["site_id"]) if row.get("site_id") else None,
        "primary_group_id": int(row["primary_group_id"]) if row.get("primary_group_id") else None,
        "serial": row.get("serial") or None,
        "label": row.get("label") or None,
    }
    if device is None:
        db.add(Device(mac=mac, **fields))
        return "created"
    for k, v in fields.items():
        setattr(device, k, v)
    await bump_device_generation(mac)  # invalidate cached config
    return "updated"


async def import_devices(
    db: AsyncSession, content: bytes, fmt: str
) -> DeviceImportResult:
    rows: list[dict]
    if fmt == "csv":
        text = content.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
    elif fmt == "json":
        data = json.loads(content.decode())
        rows = data if isinstance(data, list) else data.get("devices", [])
    else:
        raise ValueError(f"unsupported format: {fmt}")

    created = updated = 0
    errors: list[dict] = []
    for i, row in enumerate(rows):
        try:
            outcome = await _upsert_device(db, row)
            if outcome == "created":
                created += 1
            else:
                updated += 1
        except (ValueError, KeyError) as exc:
            errors.append({"row": i, "error": str(exc), "data": row})

    await db.flush()
    return DeviceImportResult(
        total=len(rows), created=created, updated=updated, errors=errors
    )
