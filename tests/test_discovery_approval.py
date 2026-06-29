"""Discovery approval integration tests. Require the full stack.

Run with:
    POLYPROV_TEST_STACK=1 pytest tests/test_discovery_approval.py
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine, text

from tests.conftest import REQUIRES_STACK


def _auth(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "changeme123"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _insert_discovery(mac: str, model: str = "CCX-CCX_500") -> None:
    from app.core.config import settings

    engine = create_engine(settings.database_url_sync)
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO discovered_endpoint "
                "(mac, status, model, firmware_version, serial, endpoint_ip, proxy_ip, "
                "user_agent, first_seen_at, last_seen_at, request_count, last_path, "
                "last_status, created_at, updated_at) "
                "VALUES (:mac, 'pending', :model, '9.4.1.0508', :mac, "
                "'10.0.0.246', '172.18.0.11', :ua, :now, :now, 1, :path, 404, :now, :now)"
            ),
            {
                "mac": mac,
                "model": model,
                "ua": f"FileTransport PolyCCX-CCX_500-UA/9.4.1.0508 (SN:{mac}) Type/Application",
                "path": f"{mac}.cfg",
                "now": now,
            },
        )


@REQUIRES_STACK
def test_approve_discovery_creates_device_and_marks_discovery_approved():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    auth = _auth(client)
    suffix = uuid.uuid4().hex[:8]
    mac = "64167f" + uuid.uuid4().hex[:6]
    _insert_discovery(mac)

    r = client.post(
        "/api/v1/tenants",
        json={"slug": f"approve-{suffix}", "name": "Approve Test"},
        headers=auth,
    )
    assert r.status_code == 201
    tenant_id = r.json()["id"]

    r = client.post(
        "/api/v1/sites",
        json={"tenant_id": tenant_id, "name": "HQ"},
        headers=auth,
    )
    assert r.status_code == 201
    site_id = r.json()["id"]

    r = client.post(
        "/api/v1/groups",
        json={"tenant_id": tenant_id, "site_id": site_id, "name": f"approve-{suffix}"},
        headers=auth,
    )
    assert r.status_code == 201
    group_id = r.json()["id"]

    r = client.post(
        "/api/v1/templates",
        json={
            "tenant_id": tenant_id,
            "name": f"approve-{suffix}",
            "scope": "tenant",
            "scope_ref": str(tenant_id),
            "body": {"device": {"approved": True}},
        },
        headers=auth,
    )
    assert r.status_code == 201
    template_id = r.json()["id"]

    discovery = client.get(f"/api/v1/discoveries?status=pending&limit=200", headers=auth).json()
    discovery_id = next(row["id"] for row in discovery if row["mac"] == mac)

    r = client.post(
        f"/api/v1/discoveries/{discovery_id}/approve",
        json={
            "tenant_id": tenant_id,
            "site_id": site_id,
            "primary_group_id": group_id,
            "config_profile_id": template_id,
            "label": "Lobby CCX500",
        },
        headers=auth,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["device"]["mac"] == mac
    assert body["device"]["tenant_id"] == tenant_id
    assert body["device"]["site_id"] == site_id
    assert body["device"]["label"] == "Lobby CCX500"
    assert body["discovery"]["status"] == "approved"
    assert body["discovery"]["approved_device_id"] == body["device"]["id"]
    assert body["discovery"]["approved_at"] is not None
    assert body["discovery"]["approved_by"].startswith("user:")

    pending = client.get("/api/v1/discoveries?status=pending&limit=200", headers=auth).json()
    assert all(row["mac"] != mac for row in pending)

    r = client.get(f"/provisioning/{mac}.cfg")
    assert r.status_code == 200


@REQUIRES_STACK
def test_approve_discovery_rejects_site_from_another_tenant():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    auth = _auth(client)
    suffix = uuid.uuid4().hex[:8]
    mac = "64167f" + uuid.uuid4().hex[:6]
    _insert_discovery(mac)

    r = client.post("/api/v1/tenants", json={"slug": f"tenant-a-{suffix}", "name": "A"}, headers=auth)
    assert r.status_code == 201
    tenant_a = r.json()["id"]
    r = client.post("/api/v1/tenants", json={"slug": f"tenant-b-{suffix}", "name": "B"}, headers=auth)
    assert r.status_code == 201
    tenant_b = r.json()["id"]
    r = client.post("/api/v1/sites", json={"tenant_id": tenant_b, "name": "Other"}, headers=auth)
    assert r.status_code == 201
    other_site = r.json()["id"]

    discovery = client.get("/api/v1/discoveries?status=pending&limit=200", headers=auth).json()
    discovery_id = next(row["id"] for row in discovery if row["mac"] == mac)

    r = client.post(
        f"/api/v1/discoveries/{discovery_id}/approve",
        json={"tenant_id": tenant_a, "site_id": other_site},
        headers=auth,
    )
    assert r.status_code == 400
    assert "site must belong to tenant" in r.text
