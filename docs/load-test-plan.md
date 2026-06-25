# Load Test Plan & Security Checklist

## Load testing the provisioning plane

Goal: confirm the cache-first design holds at 10k / 50k / 100k devices with
acceptable latency and a healthy cache hit ratio, and that the batched writer
keeps the check-in buffer from growing unbounded.

### Setup

1. Stand up a production-like stack (managed Postgres + Redis, ≥4 prov-api
   replicas behind the LB, the Celery worker running the 2s flush).
2. Pre-enroll the synthetic MACs (the simulator uses OUI `0004f2` + index):

   ```bash
   # generate a CSV of N devices and import it
   python - <<'PY'
   import csv
   with open("/tmp/devices.csv","w",newline="") as f:
       w=csv.writer(f); w.writerow(["mac","tenant_id","model"])
       for i in range(100000):
           w.writerow([f"0004f2{i:06x}", 1, "CCX"])
   PY
   curl -F file=@/tmp/devices.csv "http://admin/api/v1/devices/import?fmt=csv" -H "Authorization: Bearer $TOKEN"
   ```

### Runs

```bash
python tools/simulator.py --base-url http://prov:8080 --devices 10000  --concurrency 500  --duration 60
python tools/simulator.py --base-url http://prov:8080 --devices 50000  --concurrency 1000 --duration 120
python tools/simulator.py --base-url http://prov:8080 --devices 100000 --concurrency 2000 --duration 300
```

### Pass criteria (suggested, tune to your SLOs)

| Metric | Target |
|--------|--------|
| p95 latency (cache hit) | < 50 ms |
| p99 latency (cache hit) | < 150 ms |
| Cache hit ratio (steady state) | > 95% |
| Error rate | < 0.1% |
| Check-in buffer depth | bounded; drains between flushes |
| Postgres CPU | headroom remaining at 100k |

### What to watch in Grafana

- `polyprov_cache_hits_total` vs `polyprov_cache_misses_total` — misses should
  spike only at the start (cold cache) then fall off.
- `polyprov_checkin_buffer_depth` — must not grow without bound; if it does,
  add Celery worker replicas or increase `CHECKIN_FLUSH_BATCH`.
- `polyprov_provisioning_latency_seconds` histogram.
- Postgres connections — should stay low because hits skip the DB.

### Tuning levers if a run fails

- Raise prov-api replica count / HPA max.
- Raise `CONFIG_CACHE_TTL` (fewer re-renders) — at the cost of slower
  propagation; generation bumps still invalidate immediately on change.
- Increase Redis resources / move to a Redis cluster.
- Add Postgres read replicas and route resolver reads there.
- Increase the flush batch size and/or worker count.

---

## Security test checklist

- [ ] **AuthN:** endpoints reject missing/expired/invalid JWT and bad API keys.
- [ ] **AuthZ/RBAC:** a `readonly` principal is denied write endpoints; a
      tenant-scoped principal cannot read another tenant's devices.
- [ ] **API key hygiene:** full key shown once; only the hash is stored; revoked
      keys stop working immediately.
- [ ] **Rate limiting:** per-IP and per-MAC limits return 429 under flood;
      legitimate staggered traffic is unaffected.
- [ ] **Input validation:** malformed MACs rejected on import and lookup;
      oversized/garbage import files fail gracefully with per-row errors.
- [ ] **Transport:** HTTPS enforced on admin (HSTS); firmware over TLS; HTTP
      provisioning flagged in logs.
- [ ] **Secrets:** none in the image, repo, or logs; sourced from a manager.
- [ ] **Injection:** parameterized queries throughout (SQLAlchemy); config
      rendering escapes XML special chars (covered by `tests/test_renderer.py`).
- [ ] **Audit:** every mutation writes an audit_log row with actor + before/after.
- [ ] **Provisioning trust:** confirm MAC alone never authorizes sensitive
      config; credentials delivered only over TLS (and encrypted config where
      the model supports it).
- [ ] **Dependency + container scan:** run `pip-audit` and a container image
      scanner in CI; fail on high-severity CVEs.
- [ ] **DoS:** confirm an unknown-MAC flood (404 path) doesn't exhaust DB
      connections (it hits the resolver once per MAC then is cheap).
