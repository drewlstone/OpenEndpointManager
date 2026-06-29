from app.services.discovery import parse_poly_user_agent
from app.worker import is_device_provisioning_request


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
