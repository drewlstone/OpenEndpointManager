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
