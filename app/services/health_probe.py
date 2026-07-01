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
    network_reachability_status: str
    network_reachability_method: str | None
    network_reachability_error: str | None
    network_latency_ms: int | None
    web_reachability_status: str
    web_reachability_method: str | None
    web_reachability_error: str | None
    web_latency_ms: int | None
    duration_ms: int


@dataclass(frozen=True)
class _TcpResult:
    ok: bool
    latency_ms: int | None
    error: str | None


@dataclass(frozen=True)
class _NetworkResult:
    status: str
    method: str | None
    error: str | None
    latency_ms: int | None


@dataclass(frozen=True)
class _WebResult:
    status: str
    method: str | None
    error: str | None
    latency_ms: int | None


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
    if "dns_failure" in errors:
        return "dns_failure"
    if all(error == "connection_refused" for error in errors):
        return "connection_refused"
    if "timeout" in errors:
        return "timeout"
    return errors[0]


async def _icmp_probe(
    host: str, enabled: bool, command: str, timeout_seconds: float
) -> _NetworkResult:
    if not enabled:
        return _NetworkResult("unknown", None, "icmp_disabled", None)

    start = time.perf_counter()
    timeout_arg = max(1, int(timeout_seconds))
    try:
        proc = await asyncio.create_subprocess_exec(
            command,
            "-c",
            "1",
            "-W",
            str(timeout_arg),
            host,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            code = await asyncio.wait_for(proc.wait(), timeout=timeout_seconds + 0.5)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return _NetworkResult("unreachable", "icmp", "timeout", None)
    except FileNotFoundError:
        return _NetworkResult("unknown", None, "icmp_unavailable", None)
    except PermissionError:
        return _NetworkResult("unknown", None, "icmp_not_permitted", None)
    except OSError as exc:
        return _NetworkResult("unknown", None, exc.__class__.__name__.lower(), None)

    latency_ms = int((time.perf_counter() - start) * 1000)
    if code == 0:
        return _NetworkResult("reachable", "icmp", None, latency_ms)
    return _NetworkResult("unreachable", "icmp", "icmp_failed", None)


def _classify_web(
    tcp_443: _TcpResult,
    tcp_80: _TcpResult,
    https: _TcpResult | None,
    http: _TcpResult | None,
) -> _WebResult:
    if https and https.ok:
        return _WebResult("reachable", "https_head", None, https.latency_ms)
    if http and http.ok:
        return _WebResult("reachable", "http_head", None, http.latency_ms)
    if tcp_443.ok:
        return _WebResult(
            "reachable", "tcp_443", https.error if https else None, tcp_443.latency_ms
        )
    if tcp_80.ok:
        return _WebResult(
            "reachable", "tcp_80", http.error if http else None, tcp_80.latency_ms
        )

    error = _failure_error(tcp_443, tcp_80)
    if error == "connection_refused":
        return _WebResult("refused", None, error, None)
    if error == "timeout":
        return _WebResult("timeout", None, error, None)
    return _WebResult("unreachable", None, error, None)


def _summary_status(network: _NetworkResult, web: _WebResult) -> str:
    if network.status == "reachable" or web.status == "reachable":
        return "reachable"
    if network.status == "unreachable" and web.status in {"unreachable", "timeout"}:
        return "unreachable"
    return "unknown"


async def probe_endpoint(
    endpoint_ip: str | None,
    timeout: float,
    icmp_enabled: bool = False,
    icmp_command: str = "ping",
    icmp_timeout: float = 1.0,
) -> HealthProbeResult:
    started = time.perf_counter()
    if not endpoint_ip:
        return HealthProbeResult(
            reachability_status="unknown",
            identity_confidence="not_checked",
            network_reachability_status="unknown",
            network_reachability_method=None,
            network_reachability_error="no_endpoint_ip",
            network_latency_ms=None,
            web_reachability_status="not_checked",
            web_reachability_method=None,
            web_reachability_error="no_endpoint_ip",
            web_latency_ms=None,
            duration_ms=0,
        )

    network_task = asyncio.create_task(
        _icmp_probe(endpoint_ip, icmp_enabled, icmp_command, icmp_timeout)
    )

    tcp_443 = await _tcp_connect(endpoint_ip, 443, timeout)
    tcp_80 = await _tcp_connect(endpoint_ip, 80, timeout)

    https = await _head_request(endpoint_ip, 443, True, timeout) if tcp_443.ok else None
    http = await _head_request(endpoint_ip, 80, False, timeout) if tcp_80.ok else None

    network = await network_task
    web = _classify_web(tcp_443, tcp_80, https, http)

    return HealthProbeResult(
        reachability_status=_summary_status(network, web),
        identity_confidence="unknown",
        network_reachability_status=network.status,
        network_reachability_method=network.method,
        network_reachability_error=network.error,
        network_latency_ms=network.latency_ms,
        web_reachability_status=web.status,
        web_reachability_method=web.method,
        web_reachability_error=web.error,
        web_latency_ms=web.latency_ms,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
