from types import SimpleNamespace

from app.provisioning.router import _client_ips


def _request(peer, headers=None):
    return SimpleNamespace(
        client=SimpleNamespace(host=peer) if peer else None,
        headers=headers or {},
    )


def test_trusted_proxy_uses_first_forwarded_for_ip():
    endpoint_ip, proxy_ip = _client_ips(_request(
        "172.18.0.5",
        {"x-forwarded-for": "10.0.0.99, 172.18.0.5"},
    ))

    assert endpoint_ip == "10.0.0.99"
    assert proxy_ip == "172.18.0.5"


def test_trusted_proxy_falls_back_to_real_ip():
    endpoint_ip, proxy_ip = _client_ips(_request(
        "172.18.0.5",
        {"x-real-ip": "10.0.0.99"},
    ))

    assert endpoint_ip == "10.0.0.99"
    assert proxy_ip == "172.18.0.5"


def test_untrusted_peer_ignores_forwarded_headers():
    endpoint_ip, proxy_ip = _client_ips(_request(
        "10.0.0.99",
        {"x-forwarded-for": "203.0.113.10", "x-real-ip": "203.0.113.11"},
    ))

    assert endpoint_ip == "10.0.0.99"
    assert proxy_ip is None


def test_direct_trusted_loopback_without_headers_has_no_proxy_ip():
    endpoint_ip, proxy_ip = _client_ips(_request("127.0.0.1"))

    assert endpoint_ip == "127.0.0.1"
    assert proxy_ip is None
