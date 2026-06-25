"""Render resolved parameter maps into Poly-compatible configuration files.

Poly CCX/Edge/Trio phones consume XML configuration where settings are
attributes on elements, plus a master config file (000000000000.cfg) that
lists which config files to load via APPLICATION/CONFIG_FILES.

We keep an internal flat/nested parameter map and emit the XML the phones
expect. A `raw_override` key lets an operator inject a verbatim file body as an
escape hatch.
"""
from __future__ import annotations

import hashlib
from xml.sax.saxutils import escape


def _attr(value: str) -> str:
    """Quote an XML attribute value with double quotes, escaping reserved chars.

    Poly parsers expect double-quoted attributes, so we always use them and
    escape & < > " explicitly rather than letting the quoting char vary.
    """
    return '"' + escape(value, {'"': "&quot;"}) + '"'


def _flatten(params: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dicts into Poly dotted-key parameters.

    {"voIpProt": {"server": {"1": {"address": "10.0.0.1"}}}}
      -> {"voIpProt.server.1.address": "10.0.0.1"}
    """
    out: dict[str, str] = {}
    for key, val in params.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            out.update(_flatten(val, full))
        elif isinstance(val, bool):
            out[full] = "1" if val else "0"
        elif val is None:
            continue
        else:
            out[full] = str(val)
    return out


def render_device_config(params: dict, mac: str) -> bytes:
    """Render the per-device <MAC>.cfg file body."""
    if "raw_override" in params:
        return params["raw_override"].encode()

    flat = _flatten({k: v for k, v in params.items() if k != "raw_override"})
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f"<!-- PolyProv generated config for {mac} -->",
        "<PHONE_CONFIG>",
        "  <ALL",
    ]
    for key in sorted(flat):
        lines.append(f"    {key}={_attr(flat[key])}")
    lines.append("  />")
    lines.append("</PHONE_CONFIG>")
    return ("\n".join(lines) + "\n").encode()


def render_master_config(mac: str, config_files: list[str], app_file_path: str | None = None) -> bytes:
    """Render the master config (000000000000.cfg or <MAC>.cfg master).

    config_files: ordered list of CONFIG_FILES the phone should pull.
    app_file_path: optional firmware APP_FILE_PATH to advertise.
    """
    files_attr = _attr(", ".join(config_files))
    app_attr = f" APP_FILE_PATH={_attr(app_file_path)}" if app_file_path else ""
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<!-- PolyProv master config for {mac} -->\n"
        f"<APPLICATION{app_attr}\n"
        f"  CONFIG_FILES={files_attr}\n"
        '  MISC_FILES=""\n'
        '  LOG_FILE_DIRECTORY=""\n'
        '  OVERRIDES_DIRECTORY=""\n'
        '  CONTACTS_DIRECTORY=""\n'
        "/>\n"
    )
    return body.encode()


def config_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()
