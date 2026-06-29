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
