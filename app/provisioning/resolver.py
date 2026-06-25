"""Resolve the effective configuration for a device by merging templates.

Order (lowest priority first, later wins):
    global -> model -> tenant -> site -> group(s by priority) -> mac

Each template may also have an explicit parent_id chain which is expanded
before merging. The result is a single parameter map handed to the renderer.
"""
from __future__ import annotations

import copy

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigTemplate, TemplateScope
from app.models.device import Device, DeviceGroupMember
from app.models.org import DeviceGroup


def deep_merge(base: dict, override: dict) -> dict:
    """Key-wise deep merge. Nested dicts merge; scalars/lists replace."""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


async def _expand_parent_chain(
    db: AsyncSession, template: ConfigTemplate, seen: set[int]
) -> dict:
    """Merge a template's parent chain (parent first) then itself."""
    if template.parent_id and template.parent_id not in seen:
        seen.add(template.parent_id)
        parent = await db.get(ConfigTemplate, template.parent_id)
        if parent:
            base = await _expand_parent_chain(db, parent, seen)
            return deep_merge(base, template.body or {})
    return copy.deepcopy(template.body or {})


async def _templates_for(
    db: AsyncSession, scope: TemplateScope, scope_ref: str | None
) -> list[ConfigTemplate]:
    stmt = select(ConfigTemplate).where(ConfigTemplate.scope == scope)
    if scope_ref is not None:
        stmt = stmt.where(ConfigTemplate.scope_ref == str(scope_ref))
    result = await db.execute(stmt.order_by(ConfigTemplate.priority))
    return list(result.scalars().all())


async def resolve_effective_config(db: AsyncSession, device: Device) -> dict:
    """Build the effective parameter map for a device."""
    effective: dict = {}

    async def apply(scope: TemplateScope, scope_ref: str | None) -> None:
        nonlocal effective
        for tpl in await _templates_for(db, scope, scope_ref):
            expanded = await _expand_parent_chain(db, tpl, set())
            effective = deep_merge(effective, expanded)

    # 1. global
    await apply(TemplateScope.global_, None)
    # 2. model
    await apply(TemplateScope.model, device.model)
    # 3. tenant
    await apply(TemplateScope.tenant, str(device.tenant_id))
    # 4. site
    if device.site_id:
        await apply(TemplateScope.site, str(device.site_id))
    # 5. groups (primary + secondary), ordered by group.priority
    group_ids: list[int] = []
    if device.primary_group_id:
        group_ids.append(device.primary_group_id)
    members = await db.execute(
        select(DeviceGroupMember.group_id).where(
            DeviceGroupMember.device_id == device.id
        )
    )
    group_ids.extend([g for g in members.scalars().all() if g not in group_ids])
    if group_ids:
        groups = await db.execute(
            select(DeviceGroup)
            .where(DeviceGroup.id.in_(group_ids))
            .order_by(DeviceGroup.priority)
        )
        for grp in groups.scalars().all():
            await apply(TemplateScope.group, str(grp.id))
    # 6. mac (always wins)
    await apply(TemplateScope.mac, device.mac)

    # explicit per-device profile override (highest)
    if device.config_profile_id:
        profile = await db.get(ConfigTemplate, device.config_profile_id)
        if profile:
            expanded = await _expand_parent_chain(db, profile, set())
            effective = deep_merge(effective, expanded)

    return effective
