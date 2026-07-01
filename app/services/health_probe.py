from __future__ import annotations

import asyncio
import socket
import ssl
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class HealthProbeResult:
    reachability_status: str
    identity_confidence: str
    method: str | None
    latency_ms: int | None
    error: str | None
    duration_ms: int


@dataclass(frozen=True)
class _TcpResult:
    ok: bool
    latency_ms: int | None
    error: str | None


async def _tcp_connect(host: str, port: int, timeout: float) -> _TcpResult:
    start = time.perf_counter()
    writer = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        return _TcpResult(True, int((time.perf_counter() - start) * 1000), None)
    except TimeoutError:
        return _TcpResult(False, None, "timeout")
    except ConnectionRefusedError:
        return _TcpResult(False, None, "connection_refused")
    except socket.gaierror:
        return _TcpResult(False, None, "dns_failure")
    except OSError as exc:
        return _TcpResult(False, None, exc.__class__.__name__.lower())
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def _head_request(host: str, port: int, use_tls: bool, timeout: float) -> _TcpResult:
    start = time.perf_counter()
    writer = None
    ssl_context = None
    if use_tls:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host,
                port,
                ssl=ssl_context,
                server_hostname=host if use_tls else None,
            ),
            timeout=timeout,
        )
        request = f"HEAD / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        writer.write(request.encode("ascii"))
        await asyncio.wait_for(writer.drain(), timeout=timeout)
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if line.startswith(b"HTTP/"):
            return _TcpResult(True, int((time.perf_counter() - start) * 1000), None)
        return _TcpResult(False, None, "invalid_http_response")
    except TimeoutError:
        return _TcpResult(False, None, "timeout")
    except ConnectionRefusedError:
        return _TcpResult(False, None, "connection_refused")
    except ssl.SSLError:
        return _TcpResult(False, None, "tls_error")
    except socket.gaierror:
        return _TcpResult(False, None, "dns_failure")
    except OSError as exc:
        return _TcpResult(False, None, exc.__class__.__name__.lower())
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


def _failure_error(*results: _TcpResult) -> str:
    errors = [result.error for result in results if result.error]
    if not errors:
        return "probe_failed"
    if "timeout" in errors:
        return "timeout"
    if "dns_failure" in errors:
        return "dns_failure"
    if all(error == "connection_refused" for error in errors):
        return "connection_refused"
    return errors[0]


async def probe_endpoint(endpoint_ip: str | None, timeout: float) -> HealthProbeResult:
    started = time.perf_counter()
    if not endpoint_ip:
        return HealthProbeResult(
            reachability_status="unknown",
            identity_confidence="not_checked",
            method=None,
            latency_ms=None,
            error="no_endpoint_ip",
            duration_ms=0,
        )

    tcp_443 = await _tcp_connect(endpoint_ip, 443, timeout)
    tcp_80 = await _tcp_connect(endpoint_ip, 80, timeout)

    https = await _head_request(endpoint_ip, 443, True, timeout) if tcp_443.ok else None
    http = await _head_request(endpoint_ip, 80, False, timeout) if tcp_80.ok else None

    if https and https.ok:
        return HealthProbeResult(
            "reachable",
            "unknown",
            "https_head",
            https.latency_ms,
            None,
            int((time.perf_counter() - started) * 1000),
        )

    if http and http.ok:
        return HealthProbeResult(
            "reachable",
            "unknown",
            "http_head",
            http.latency_ms,
            None,
            int((time.perf_counter() - started) * 1000),
        )

    if tcp_443.ok:
        return HealthProbeResult(
            "reachable",
            "unknown",
            "tcp_443",
            tcp_443.latency_ms,
            https.error if https else None,
            int((time.perf_counter() - started) * 1000),
        )

    if tcp_80.ok:
        return HealthProbeResult(
            "reachable",
            "unknown",
            "tcp_80",
            tcp_80.latency_ms,
            http.error if http else None,
            int((time.perf_counter() - started) * 1000),
        )

    return HealthProbeResult(
        reachability_status="unreachable",
        identity_confidence="unknown",
        method=None,
        latency_ms=None,
        error=_failure_error(tcp_443, tcp_80),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
