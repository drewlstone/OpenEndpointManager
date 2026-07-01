from __future__ import annotations

import random
from datetime import datetime, timedelta

from app.services.health_probe import HealthProbeResult


def jittered_next_probe_at(
    completed_at: datetime, interval_seconds: int, jitter_seconds: int
) -> datetime:
    jitter = random.randint(-jitter_seconds, jitter_seconds) if jitter_seconds > 0 else 0
    delay = max(60, interval_seconds + jitter)
    return completed_at + timedelta(seconds=delay)


def probe_result_update_values(
    probe: HealthProbeResult,
    completed_at: datetime,
    interval_seconds: int,
    jitter_seconds: int,
    current_attempts: int,
    source: str,
) -> dict:
    return {
        "reachability_status": probe.reachability_status,
        "reachability_checked_at": completed_at,
        "reachability_method": probe.web_reachability_method
        or probe.network_reachability_method,
        "reachability_latency_ms": probe.web_latency_ms or probe.network_latency_ms,
        "reachability_error": probe.web_reachability_error
        or probe.network_reachability_error,
        "network_reachability_status": probe.network_reachability_status,
        "network_reachability_method": probe.network_reachability_method,
        "network_reachability_error": probe.network_reachability_error,
        "network_latency_ms": probe.network_latency_ms,
        "network_checked_at": completed_at,
        "web_reachability_status": probe.web_reachability_status,
        "web_reachability_method": probe.web_reachability_method,
        "web_reachability_error": probe.web_reachability_error,
        "web_latency_ms": probe.web_latency_ms,
        "web_checked_at": completed_at,
        "identity_confidence": probe.identity_confidence,
        "identity_checked_at": completed_at,
        "last_probe_completed_at": completed_at,
        "last_probe_duration_ms": probe.duration_ms,
        "next_probe_at": jittered_next_probe_at(
            completed_at, interval_seconds, jitter_seconds
        ),
        "probe_attempts": 0
        if probe.reachability_status == "reachable"
        else current_attempts + 1,
        "probe_source": source,
    }


def probe_failure_update_values(
    error: str,
    completed_at: datetime,
    interval_seconds: int,
    jitter_seconds: int,
    current_attempts: int,
    source: str,
) -> dict:
    error = error[:128] if error else "probe_failed"
    return {
        "reachability_status": "unknown",
        "reachability_checked_at": completed_at,
        "reachability_method": None,
        "reachability_latency_ms": None,
        "reachability_error": error,
        "network_reachability_status": "unknown",
        "network_reachability_method": None,
        "network_reachability_error": error,
        "network_latency_ms": None,
        "network_checked_at": completed_at,
        "web_reachability_status": "unknown",
        "web_reachability_method": None,
        "web_reachability_error": error,
        "web_latency_ms": None,
        "web_checked_at": completed_at,
        "identity_confidence": "unknown",
        "identity_checked_at": completed_at,
        "last_probe_completed_at": completed_at,
        "last_probe_duration_ms": None,
        "next_probe_at": jittered_next_probe_at(
            completed_at, interval_seconds, jitter_seconds
        ),
        "probe_attempts": current_attempts + 1,
        "probe_source": source,
    }
