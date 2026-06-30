import uuid

from tests.conftest import REQUIRES_STACK


def _auth(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "changeme123"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _tenant(client, auth, suffix, name="Tenant"):
    r = client.post(
        "/api/v1/tenants",
        headers=auth,
        json={"slug": f"{name.lower()}-{suffix}", "name": f"{name} {suffix}"},
    )
    assert r.status_code == 201
    return r.json()["id"]


@REQUIRES_STACK
def test_patch_device_updates_safe_admin_fields_and_bumps_generation(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    bumped = []

    async def fake_bump(mac):
        bumped.append(mac)
        return 1

    monkeypatch.setattr("app.api.devices.bump_device_generation", fake_bump)

    client = TestClient(app)
    auth = _auth(client)
    suffix = uuid.uuid4().hex[:8]
    tenant_id = _tenant(client, auth, suffix)

    site = client.post(
        "/api/v1/sites",
        headers=auth,
        json={"tenant_id": tenant_id, "name": f"HQ {suffix}"},
    )
    assert site.status_code == 201
    site_id = site.json()["id"]

    group = client.post(
        "/api/v1/groups",
        headers=auth,
        json={"tenant_id": tenant_id, "site_id": site_id, "name": f"Phones {suffix}"},
    )
    assert group.status_code == 201
    group_id = group.json()["id"]

    template = client.post(
        "/api/v1/templates",
        headers=auth,
        json={
            "tenant_id": tenant_id,
            "name": f"Profile {suffix}",
            "scope": "tenant",
            "scope_ref": str(tenant_id),
            "body": {"device": {"label": "edited"}},
        },
    )
    assert template.status_code == 201
    template_id = template.json()["id"]

    mac = "0004f2" + uuid.uuid4().hex[:6]
    created = client.post(
        "/api/v1/devices",
        headers=auth,
        json={"tenant_id": tenant_id, "mac": mac, "model": "CCX", "serial": "SERIAL-1"},
    )
    assert created.status_code == 201
    mac = created.json()["mac"]

    updated = client.patch(
        f"/api/v1/devices/{mac}",
        headers=auth,
        json={
            "label": "Lobby phone",
            "asset_tag": "ASSET-100",
            "site_id": site_id,
            "primary_group_id": group_id,
            "config_profile_id": template_id,
            "status": "disabled",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["label"] == "Lobby phone"
    assert body["asset_tag"] == "ASSET-100"
    assert body["site_id"] == site_id
    assert body["primary_group_id"] == group_id
    assert body["config_profile_id"] == template_id
    assert body["status"] == "disabled"
    assert body["mac"] == mac
    assert body["serial"] == "SERIAL-1"
    assert body["model"] == "CCX"
    assert bumped == [mac]


@REQUIRES_STACK
def test_patch_device_rejects_unsafe_or_cross_tenant_updates():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    auth = _auth(client)
    suffix = uuid.uuid4().hex[:8]
    tenant_id = _tenant(client, auth, f"a-{suffix}", "TenantA")
    other_tenant_id = _tenant(client, auth, f"b-{suffix}", "TenantB")

    site = client.post(
        "/api/v1/sites",
        headers=auth,
        json={"tenant_id": tenant_id, "name": f"Site A {suffix}"},
    )
    assert site.status_code == 201
    site_id = site.json()["id"]

    other_site = client.post(
        "/api/v1/sites",
        headers=auth,
        json={"tenant_id": other_tenant_id, "name": f"Site B {suffix}"},
    )
    assert other_site.status_code == 201
    other_site_id = other_site.json()["id"]

    site_two = client.post(
        "/api/v1/sites",
        headers=auth,
        json={"tenant_id": tenant_id, "name": f"Site A2 {suffix}"},
    )
    assert site_two.status_code == 201
    site_two_id = site_two.json()["id"]

    group_site_two = client.post(
        "/api/v1/groups",
        headers=auth,
        json={"tenant_id": tenant_id, "site_id": site_two_id, "name": f"Site2 Group {suffix}"},
    )
    assert group_site_two.status_code == 201
    group_site_two_id = group_site_two.json()["id"]

    other_template = client.post(
        "/api/v1/templates",
        headers=auth,
        json={
            "tenant_id": other_tenant_id,
            "name": f"Other Profile {suffix}",
            "scope": "tenant",
            "scope_ref": str(other_tenant_id),
            "body": {"other": True},
        },
    )
    assert other_template.status_code == 201
    other_template_id = other_template.json()["id"]

    mac = "0004f2" + uuid.uuid4().hex[:6]
    created = client.post(
        "/api/v1/devices",
        headers=auth,
        json={"tenant_id": tenant_id, "site_id": site_id, "mac": mac, "model": "CCX"},
    )
    assert created.status_code == 201
    mac = created.json()["mac"]

    r = client.patch(f"/api/v1/devices/{mac}", headers=auth, json={"tenant_id": other_tenant_id})
    assert r.status_code == 422

    r = client.patch(f"/api/v1/devices/{mac}", headers=auth, json={"model": "VVX"})
    assert r.status_code == 422

    r = client.patch(f"/api/v1/devices/{mac}", headers=auth, json={"site_id": other_site_id})
    assert r.status_code == 400
    assert "site must belong" in r.text

    r = client.patch(f"/api/v1/devices/{mac}", headers=auth, json={"primary_group_id": group_site_two_id})
    assert r.status_code == 400
    assert "selected site" in r.text

    r = client.patch(f"/api/v1/devices/{mac}", headers=auth, json={"config_profile_id": other_template_id})
    assert r.status_code == 400
    assert "template must be global" in r.text
