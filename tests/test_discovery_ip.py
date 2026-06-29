import asyncio
import json
from types import SimpleNamespace

import app.provisioning.router as provisioning_router
from app.provisioning.router import _buffer_discovery, _client_ips


def _request(peer, headers=None):
    return SimpleNamespace(
        client=SimpleNamespace(host=peer) if peer else None,
        headers=headers or {},
    )


def test_client_ip_extraction_uses_forwarded_real_ip_and_preserves_proxy_ip():
    endpoint_ip, proxy_ip = _client_ips(_request(
        "172.18.0.11",
        {"x-forwarded-for": "10.0.0.246", "x-real-ip": "10.0.0.246"},
    ))

    assert endpoint_ip == "10.0.0.246"
    assert proxy_ip == "172.18.0.11"


def test_discovery_payload_uses_resolved_endpoint_and_proxy_ip(monkeypatch):
    captured = []

    async def fake_enqueue(payload):
        captured.append(json.loads(payload))

    monkeypatch.setattr(provisioning_router, "enqueue_discovery", fake_enqueue)

    asyncio.run(_buffer_discovery(
        "64167f9f4c90",
        "10.0.0.246",
        "172.18.0.11",
        "FileTransport PolyCCX-CCX_500-UA/9.4.1.0508 (SN:64167f9f4c90) Type/Application",
        "64167f9f4c90.cfg",
        404,
    ))

    assert len(captured) == 1
    payload = captured[0]
    assert payload["endpoint_ip"] == "10.0.0.246"
    assert payload["proxy_ip"] == "172.18.0.11"
    assert payload["mac"] == "64167f9f4c90"
    assert payload["model"] == "CCX-CCX_500"
    assert payload["firmware_version"] == "9.4.1.0508"
    assert payload["serial"] == "64167f9f4c90"
