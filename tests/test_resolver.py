"""Unit tests for template inheritance merge (no DB needed for deep_merge)."""
from app.provisioning.resolver import deep_merge


def test_later_scalar_wins():
    assert deep_merge({"tone": "US"}, {"tone": "UK"})["tone"] == "UK"


def test_nested_dicts_merge_not_replace():
    base = {"voIpProt": {"server": {"1": {"address": "10.0.0.1", "port": "5060"}}}}
    override = {"voIpProt": {"server": {"1": {"address": "10.9.9.9"}}}}
    result = deep_merge(base, override)
    assert result["voIpProt"]["server"]["1"]["address"] == "10.9.9.9"
    assert result["voIpProt"]["server"]["1"]["port"] == "5060"  # preserved


def test_lists_replace_not_concat():
    assert deep_merge({"x": [1, 2]}, {"x": [3]})["x"] == [3]


def test_does_not_mutate_inputs():
    base = {"a": {"b": 1}}
    override = {"a": {"c": 2}}
    deep_merge(base, override)
    assert base == {"a": {"b": 1}}  # unchanged
    assert override == {"a": {"c": 2}}


def test_full_inheritance_chain_order():
    # global -> model -> tenant -> site -> group -> mac, later wins
    g = {"voIpProt": {"server": {"1": {"address": "g", "port": "5060"}}}, "tone": "US"}
    model = {"up": {"headsetMode": "0"}}
    tenant = {"voIpProt": {"server": {"1": {"address": "t"}}}}
    site = {"tcpIpApp": {"sntp": {"address": "ntp.local"}}}
    group = {"bg": {"color": "blue"}}
    mac = {"reg": {"1": {"label": "Desk"}}, "tone": "UK"}

    eff = g
    for layer in (model, tenant, site, group, mac):
        eff = deep_merge(eff, layer)

    assert eff["voIpProt"]["server"]["1"]["address"] == "t"   # tenant beat global
    assert eff["voIpProt"]["server"]["1"]["port"] == "5060"   # global survived
    assert eff["tone"] == "UK"                                 # mac beat global
    assert eff["up"]["headsetMode"] == "0"                     # model preserved
    assert eff["reg"]["1"]["label"] == "Desk"                 # mac added
    assert eff["bg"]["color"] == "blue"                        # group added
