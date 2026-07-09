from __future__ import annotations

import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api import admin as admin_router
from app.api import auth as auth_router
from app.api import devices as devices_router
from app.api import discovery as discovery_router
from app.api import reports as reports_router
from app.api import ops as ops_router
from app.api import users as users_router
from app.core.config import settings
from app.core.db import engine
from app.core.logging_config import configure_logging
from app.core.redis_client import redis_client
from app.provisioning import router as prov_router

configure_logging()

# PROVISIONING_PLANE / ADMIN_PLANE / ALL controls which routers are mounted,
# so the same image can run as a dedicated prov node or admin node.
PLANE = os.getenv("POLYPROV_PLANE", "all").lower()

app = FastAPI(
    title="PolyProv",
    description="Poly provisioning & device management platform",
    version="0.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

if PLANE in ("all", "admin"):
    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(devices_router.router, prefix="/api/v1")
    app.include_router(discovery_router.router, prefix="/api/v1")
    app.include_router(admin_router.router, prefix="/api/v1")
    app.include_router(reports_router.router, prefix="/api/v1")
    app.include_router(ops_router.router, prefix="/api/v1")
    app.include_router(users_router.router, prefix="/api/v1")

if PLANE in ("all", "provisioning"):
    app.include_router(prov_router.router)


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz() -> Response:
    checks = {"db": False, "redis": False}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:
        pass
    try:
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        pass
    ok = all(checks.values())
    return Response(
        content=str(checks),
        status_code=200 if ok else 503,
        media_type="text/plain",
    )


@app.get("/metrics", tags=["ops"])
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
