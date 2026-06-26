#!/usr/bin/env python3
"""Seed the database: create tables, roles, permissions, a superadmin, and a
sample tenant + global template + a few devices.

Run inside the API container after the DB is up. The backend image sets
PYTHONPATH=/app so the top-level app package is importable:
    python tools/seed.py
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base, AsyncSessionLocal, engine
from app.core.security import hash_password, normalize_mac
from app.models import (
    AdminUser, ConfigTemplate, Device, Permission, Role, RolePermission,
    TemplateScope, Tenant, UserRole,
)

PERMISSIONS = [
    "*",  # wildcard for superadmin
    "tenant:read", "tenant:write", "site:read", "site:write",
    "group:read", "group:write", "device:read", "device:write",
    "template:read", "template:write", "firmware:read", "firmware:write",
    "user:read", "user:write", "api_key:create",
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:  # type: AsyncSession
        # permissions
        perm_objs = {}
        for name in PERMISSIONS:
            existing = await db.execute(select(Permission).where(Permission.name == name))
            p = existing.scalar_one_or_none()
            if not p:
                p = Permission(name=name)
                db.add(p)
                await db.flush()
            perm_objs[name] = p

        # superadmin role with wildcard
        res = await db.execute(select(Role).where(Role.name == "superadmin"))
        role = res.scalar_one_or_none()
        if not role:
            role = Role(name="superadmin")
            db.add(role)
            await db.flush()
            db.add(RolePermission(role_id=role.id, permission_id=perm_objs["*"].id))

        # superadmin user
        email = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
        password = os.getenv("SEED_ADMIN_PASSWORD", "changeme123")
        res = await db.execute(select(AdminUser).where(AdminUser.email == email))
        user = res.scalar_one_or_none()
        if not user:
            user = AdminUser(email=email, hashed_password=hash_password(password))
            db.add(user)
            await db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id))

        # sample tenant + global template + devices
        res = await db.execute(select(Tenant).where(Tenant.slug == "acme"))
        tenant = res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(slug="acme", name="Acme Corp")
            db.add(tenant)
            await db.flush()

        res = await db.execute(
            select(ConfigTemplate).where(ConfigTemplate.scope == TemplateScope.global_)
        )
        if not res.scalar_one_or_none():
            db.add(ConfigTemplate(
                name="global-defaults", scope=TemplateScope.global_,
                body={
                    "tcpIpApp": {"sntp": {"address": "pool.ntp.org"}},
                    "voIpProt": {"server": {"1": {
                        "address": "sip.example.com", "port": "5060",
                        "transport": "TLS"}}},
                    "log": {"level": {"change": {"app1": "3"}}},
                },
                priority=10,
            ))

        for i, label in enumerate(["Front Desk", "Lobby", "Conf Room A"]):
            mac = normalize_mac(f"0004f2{i:06x}")
            res = await db.execute(select(Device).where(Device.mac == mac))
            if not res.scalar_one_or_none():
                db.add(Device(tenant_id=tenant.id, mac=mac, model="CCX",
                              label=label, status="enrolled"))

        await db.commit()
    print("Seed complete.")
    print(f"  admin user: {email} / {password}")
    print("  sample tenant 'acme' with 3 CCX devices (0004f2000000..02)")


if __name__ == "__main__":
    asyncio.run(seed())
