"""API/integration tests. Require the full stack (Postgres + Redis).

Run with:
    docker compose -f deploy/docker/docker-compose.yml up -d
    POLYPROV_TEST_STACK=1 pytest tests/test_api.py
"""
import pytest

from tests.conftest import REQUIRES_STACK


@REQUIRES_STACK
def test_login_and_create_device():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # login as the seeded superadmin
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "changeme123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # create a tenant
    r = client.post("/api/v1/tenants", json={"slug": "t1", "name": "Tenant 1"}, headers=auth)
    assert r.status_code == 201
    tid = r.json()["id"]

    # create a device
    r = client.post("/api/v1/devices",
                    json={"tenant_id": tid, "mac": "00:04:f2:11:22:33", "model": "CCX"},
                    headers=auth)
    assert r.status_code == 201
    assert r.json()["mac"] == "0004f2112233"


@REQUIRES_STACK
def test_global_master_config_returns_without_pseudo_device():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/provisioning/000000000000.cfg")
    assert r.status_code == 200
    assert "<APPLICATION" in r.text
    assert "CONFIG_FILES=" in r.text
    assert "device not enrolled" not in r.text


@REQUIRES_STACK
def test_global_master_config_second_request_uses_cache(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.provisioning import router as prov_router

    client = TestClient(app)
    first = client.get("/provisioning/000000000000.cfg")
    assert first.status_code == 200

    def fail_render(*args, **kwargs):
        raise AssertionError("global master was rendered instead of served from cache")

    monkeypatch.setattr(prov_router, "render_master_config", fail_render)
    second = client.get("/provisioning/000000000000.cfg")
    assert second.status_code == 200
    assert second.text == first.text


@REQUIRES_STACK
def test_provisioning_returns_config_for_enrolled_device():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    # seeded device 0004f2000000 should resolve a config
    r = client.get("/provisioning/0004f2000000.cfg")
    assert r.status_code == 200
    assert "PHONE_CONFIG" in r.text


@REQUIRES_STACK
def test_provisioning_404_for_unknown_device():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/provisioning/0004f2ffffff.cfg")
    assert r.status_code == 404


@REQUIRES_STACK
def test_dashboard_reports_counts():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "changeme123"})
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/reports/dashboard", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "total_devices" in body and "online" in body and "by_model" in body


@REQUIRES_STACK
def test_templates_crud_and_inheritance_effect():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "changeme123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # create a model-scoped template; should not error
    r = client.post("/api/v1/templates", headers=auth, json={
        "name": "ccx-model", "scope": "model", "scope_ref": "CCX",
        "body": {"up": {"headsetMode": "1"}}, "priority": 50,
    })
    assert r.status_code == 201

    # list templates includes it
    r = client.get("/api/v1/templates", headers=auth)
    assert r.status_code == 200
    assert any(t["name"] == "ccx-model" for t in r.json())


@REQUIRES_STACK
def test_users_and_roles_listing():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "changeme123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get("/api/v1/users", headers=auth)
    assert r.status_code == 200
    assert any(u["email"] == "admin@example.com" for u in r.json())

    r = client.get("/api/v1/users/roles/all", headers=auth)
    assert r.status_code == 200
    assert any(role["name"] == "superadmin" for role in r.json())


@REQUIRES_STACK
def test_rbac_blocks_unauthorized():
    """A request with no auth must be rejected on protected endpoints."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/api/v1/devices")
    assert r.status_code == 401


@REQUIRES_STACK
def test_firmware_register_and_assign_ring():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.post("/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "changeme123"})
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post("/api/v1/firmware?model=CCX&version=8.1.2&object_key=ccx/8.1.2/sip.ld",
                    headers=auth)
    assert r.status_code in (201, 409)  # 409 if a prior run registered it

    fw = client.get("/api/v1/firmware", headers=auth).json()
    img = next(f for f in fw if f["version"] == "8.1.2")

    r = client.post("/api/v1/firmware/assignments", headers=auth, json={
        "scope": "model", "scope_ref": "CCX",
        "firmware_image_id": img["id"], "ring": "test",
    })
    assert r.status_code == 201


def _login_superadmin(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "changeme123"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_probe_device(client, auth, suffix, endpoint_ip="192.0.2.10"):
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    tenant = client.post(
        "/api/v1/tenants",
        json={"slug": f"probe-{suffix}", "name": f"Probe {suffix}"},
        headers=auth,
    )
    assert tenant.status_code == 201
    mac = "0004f2" + suffix[:6]
    device = client.post(
        "/api/v1/devices",
        json={"tenant_id": tenant.json()["id"], "mac": mac, "model": "CCX"},
        headers=auth,
    )
    assert device.status_code == 201
    mac = device.json()["mac"]

    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE device SET endpoint_ip = :endpoint_ip WHERE mac = :mac"),
            {"endpoint_ip": endpoint_ip, "mac": mac},
        )
    engine.dispose()
    return mac


@REQUIRES_STACK
def test_manual_probe_returns_202_and_enqueues_worker(monkeypatch):
    import uuid

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    from app.api import devices as devices_router
    from app.core.config import settings
    from app.main import app

    client = TestClient(app)
    auth = _login_superadmin(client)
    mac = _create_probe_device(client, auth, uuid.uuid4().hex[:8])
    sent = []

    def fake_send_task(name, args):
        sent.append((name, args))

    monkeypatch.setattr(devices_router.celery_app, "send_task", fake_send_task)

    r = client.post(f"/api/v1/devices/{mac}/probe", headers=auth)

    assert r.status_code == 202
    body = r.json()
    assert body["mac"] == mac
    assert body["status"] == "queued"
    assert body["probe_source"] == "manual"
    assert body["last_probe_started_at"]
    assert body["next_probe_at"]
    assert sent == [("app.worker.probe_device_now", [mac])]

    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT probe_source, last_probe_started_at, next_probe_at "
                "FROM device WHERE mac = :mac"
            ),
            {"mac": mac},
        ).mappings().one()
    engine.dispose()

    assert row["probe_source"] == "manual"
    assert row["last_probe_started_at"] is not None
    assert row["next_probe_at"] is not None


@REQUIRES_STACK
def test_manual_probe_duplicate_returns_409_without_enqueue(monkeypatch):
    import uuid
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, text

    from app.api import devices as devices_router
    from app.core.config import settings
    from app.main import app

    client = TestClient(app)
    auth = _login_superadmin(client)
    mac = _create_probe_device(client, auth, uuid.uuid4().hex[:8])
    sent = []

    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE device SET "
                "last_probe_started_at = :started_at, "
                "last_probe_completed_at = NULL, "
                "probe_source = 'manual' "
                "WHERE mac = :mac"
            ),
            {"started_at": datetime.now(timezone.utc), "mac": mac},
        )
    engine.dispose()

    monkeypatch.setattr(
        devices_router.celery_app,
        "send_task",
        lambda name, args: sent.append((name, args)),
    )

    r = client.post(f"/api/v1/devices/{mac}/probe", headers=auth)

    assert r.status_code == 409
    assert sent == []
