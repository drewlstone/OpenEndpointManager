from app.services.discovery import parse_poly_user_agent
from app.worker import device_checkin_telemetry, is_device_provisioning_request


def test_device_provisioning_request_user_agent_detection():
    assert is_device_provisioning_request(
        "FileTransport PolyCCX-CCX_600-UA/8.0.2.3267 (SN:482567b5313f) Type/Application"
    )
    assert is_device_provisioning_request("FileTransport Poly")

    assert not is_device_provisioning_request("curl/8.5.0")
    assert not is_device_provisioning_request(
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    )
    assert not is_device_provisioning_request(None)
    assert not is_device_provisioning_request("")


def test_poly_user_agent_parsing_with_serial():
    info = parse_poly_user_agent(
        "FileTransport PolyCCX-CCX_600-UA/8.0.2.3267 (SN:482567b5313f) Type/Application"
    )

    assert info.model == "CCX-CCX_600"
    assert info.firmware_version == "8.0.2.3267"
    assert info.serial == "482567b5313f"


def test_poly_user_agent_parsing_without_serial():
    info = parse_poly_user_agent("FileTransport PolyEdge-Edge_E400-UA/9.0.1.1234 Type/Application")

    assert info.model == "Edge-Edge_E400"
    assert info.firmware_version == "9.0.1.1234"
    assert info.serial is None


def test_non_poly_user_agent_has_no_discovery_details():
    info = parse_poly_user_agent("curl/8.5.0")

    assert info.model is None
    assert info.firmware_version is None
    assert info.serial is None


def test_device_checkin_telemetry_extracts_current_state_fields():
    telemetry = device_checkin_telemetry({
        "ts": "2026-06-30T12:34:56+00:00",
        "ip": "192.0.2.10",
        "proxy_ip": "172.18.0.1",
        "ua": "FileTransport PolyCCX-CCX_600-UA/8.0.2.3267 (SN:482567b5313f) Type/Application",
        "config_hash": "abc123",
    })

    assert telemetry == {
        "ts": "2026-06-30T12:34:56+00:00",
        "ip": "192.0.2.10",
        "proxy_ip": "172.18.0.1",
        "serial": "482567b5313f",
        "software_version": "8.0.2.3267",
        "h": "abc123",
    }


def test_device_checkin_telemetry_handles_unparseable_version():
    telemetry = device_checkin_telemetry({
        "ts": "2026-06-30T12:34:56+00:00",
        "ip": "192.0.2.10",
        "proxy_ip": None,
        "ua": "FileTransport Poly",
        "config_hash": None,
    })

    assert telemetry["serial"] is None
    assert telemetry["software_version"] is None
    assert telemetry["ip"] == "192.0.2.10"
    assert telemetry["proxy_ip"] is None
