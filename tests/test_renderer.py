"""Unit tests for the Poly config renderer (stdlib only, no DB/Redis)."""
from app.provisioning.renderer import (
    _flatten,
    config_hash,
    render_device_config,
    render_master_config,
)


def test_flatten_nested_to_dotted_keys():
    flat = _flatten({"voIpProt": {"server": {"1": {"address": "10.9.9.9"}}}})
    assert flat["voIpProt.server.1.address"] == "10.9.9.9"


def test_flatten_bool_becomes_one_zero():
    flat = _flatten({"up": {"echo": True, "mute": False}})
    assert flat["up.echo"] == "1"
    assert flat["up.mute"] == "0"


def test_flatten_drops_none():
    flat = _flatten({"a": None, "b": "x"})
    assert "a" not in flat and flat["b"] == "x"


def test_device_config_is_escaped_xml():
    body = render_device_config({"reg": {"1": {"label": 'A & "B"'}}}, "0004f2aabbcc").decode()
    assert "<?xml" in body
    assert "<PHONE_CONFIG>" in body
    assert "&amp;" in body and "&quot;" in body
    assert 'reg.1.label="' in body


def test_device_config_attrs_sorted_for_determinism():
    body = render_device_config({"z": "1", "a": "2"}, "0004f2aabbcc").decode()
    assert body.index("\n    a=") < body.index("\n    z=")


def test_raw_override_bypasses_rendering():
    assert render_device_config({"raw_override": "<custom/>"}, "x") == b"<custom/>"


def test_master_config_advertises_firmware():
    m = render_master_config(
        "0004f2aabbcc", ["0004f2aabbcc.cfg"],
        app_file_path="/provisioning/firmware/ccx/8.1.2/sip.ld",
    ).decode()
    assert "APP_FILE_PATH=" in m
    assert "CONFIG_FILES=" in m
    assert "0004f2aabbcc.cfg" in m


def test_master_config_without_firmware_omits_app_path():
    m = render_master_config("0004f2aabbcc", ["0004f2aabbcc.cfg"]).decode()
    assert "APP_FILE_PATH=" not in m


def test_config_hash_is_deterministic():
    assert config_hash(b"abc") == config_hash(b"abc")
    assert config_hash(b"abc") != config_hash(b"abd")
