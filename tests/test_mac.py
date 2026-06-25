"""Unit tests for MAC normalization and formatting."""
import pytest

from app.core.security import format_mac, normalize_mac


@pytest.mark.parametrize("raw", [
    "00:04:f2:AA:BB:CC",
    "0004f2aabbcc",
    "00-04-f2-aa-bb-cc",
    "0004.f2aa.bbcc",
    " 0004f2aabbcc ",
    "00 04 f2 aa bb cc",
])
def test_normalize_accepts_all_separator_styles(raw):
    assert normalize_mac(raw) == "0004f2aabbcc"


@pytest.mark.parametrize("bad", ["xyz", "0004f2aabbc", "0004f2aabbccdd", "", "gggggggggggg"])
def test_normalize_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_mac(bad)


def test_format_default_colon():
    assert format_mac("0004f2aabbcc") == "00:04:f2:aa:bb:cc"


def test_format_custom_separator():
    assert format_mac("0004f2aabbcc", "-") == "00-04-f2-aa-bb-cc"
    assert format_mac("0004f2aabbcc", "") == "0004f2aabbcc"
