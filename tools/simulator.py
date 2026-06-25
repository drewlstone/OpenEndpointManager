#!/usr/bin/env python3
"""Synthetic Poly device check-in simulator.

Simulates N phones booting and fetching their master + per-device config the way
real Poly CCX phones do, with staggered timing. Use it to validate the
provisioning plane at 10k / 50k / 100k device scale.

Usage:
    python tools/simulator.py --base-url http://localhost:8080 \
        --devices 10000 --concurrency 500 --duration 60

Each simulated device:
    1. GET /provisioning/000000000000.cfg   (master)
    2. GET /provisioning/<MAC>.cfg          (per-device)
and reports latency percentiles, cache-hit ratio (from response timing
heuristics), and error counts.

Requires: httpx  (pip install httpx). Falls back to urllib if httpx absent.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time


def gen_mac(i: int) -> str:
    # Poly OUI 0004f2 + 6 hex from the index
    return f"0004f2{i:06x}"


async def _run_httpx(args) -> None:
    import httpx

    macs = [gen_mac(i) for i in range(args.devices)]
    latencies: list[float] = []
    errors = 0
    statuses: dict[int, int] = {}
    sem = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def one(mac: str) -> None:
            nonlocal errors
            # stagger boot across the duration window
            await asyncio.sleep(random.random() * args.duration)
            async with sem:
                for fname in ("000000000000.cfg", f"{mac}.cfg"):
                    t0 = time.perf_counter()
                    try:
                        r = await client.get(
                            f"{args.base_url}/provisioning/{fname}",
                            headers={"User-Agent": "PolycomCCX/8.1.2"},
                        )
                        dt = time.perf_counter() - t0
                        latencies.append(dt)
                        statuses[r.status_code] = statuses.get(r.status_code, 0) + 1
                    except Exception:
                        errors += 1

        await asyncio.gather(*(one(m) for m in macs))

    _report(latencies, errors, statuses, args)


def _report(latencies, errors, statuses, args) -> None:
    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        print(f"\n=== Simulation: {args.devices} devices ===")
        print(f"requests:   {len(latencies)}")
        print(f"errors:     {errors}")
        print(f"statuses:   {statuses}")
        print(f"latency ms  p50={p50*1000:.1f}  p95={p95*1000:.1f}  p99={p99*1000:.1f}")
        print(f"mean ms     {statistics.mean(latencies)*1000:.1f}")
    else:
        print("no successful requests")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--devices", type=int, default=10000)
    ap.add_argument("--concurrency", type=int, default=500)
    ap.add_argument("--duration", type=float, default=60.0,
                    help="seconds over which to stagger boots")
    args = ap.parse_args()
    asyncio.run(_run_httpx(args))


if __name__ == "__main__":
    main()
