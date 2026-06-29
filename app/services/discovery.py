from __future__ import annotations

import re
from dataclasses import dataclass


POLY_PROVISIONING_USER_AGENT_PREFIX = "FileTransport Poly"

POLY_UA_RE = re.compile(
    r"^FileTransport Poly(?P<model>.+?)-UA/(?P<version>[^\s]+)"
    r"(?:\s+\(SN:(?P<serial>[^)]+)\))?"
)


@dataclass(frozen=True)
class PolyUserAgentInfo:
    model: str | None
    firmware_version: str | None
    serial: str | None


def is_poly_provisioning_user_agent(user_agent: str | None) -> bool:
    return bool(
        user_agent
        and user_agent.startswith(POLY_PROVISIONING_USER_AGENT_PREFIX)
    )


def parse_poly_user_agent(user_agent: str | None) -> PolyUserAgentInfo:
    if not is_poly_provisioning_user_agent(user_agent):
        return PolyUserAgentInfo(None, None, None)

    match = POLY_UA_RE.search(user_agent or "")
    if not match:
        return PolyUserAgentInfo(None, None, None)

    return PolyUserAgentInfo(
        model=match.group("model") or None,
        firmware_version=match.group("version") or None,
        serial=match.group("serial") or None,
    )
