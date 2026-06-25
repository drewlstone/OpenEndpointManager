# Troubleshooting

Symptom-based guide. For routine operations see [OPERATIONS.md](OPERATIONS.md).

## Phones aren't reaching the provisioning server

**Symptom:** no entries appear in Provisioning Logs / Check-in History for a
device.

- Confirm DHCP **option 160** is set and delivered as a **string/text** option
  (the most common field failure is sending it as binary). See
  [docs/dhcp/README.md](docs/dhcp/README.md).
- The value must be the full URL ending in `/provisioning/`, e.g.
  `https://prov.example.com/provisioning/`.
- For older firmware, also set option 161 to the same value; option 66 is the
  legacy fallback.
- From the phone's VLAN, verify reachability:
  `curl http://<prov-host>/provisioning/000000000000.cfg`.

## Device gets a 404

**Symptom:** Provisioning Logs show status 404 for a MAC.

- The device isn't enrolled. Import it (Devices → Import) or add it manually.
- Verify the MAC normalizes to what you expect — PolyProv stores 12 lowercase
  hex chars with no separators. The Devices page shows the normalized form.

## Config changes aren't reaching phones

- Confirm you saved the template. Saving bumps the generation counter; the next
  fetch re-renders.
- Phones only re-fetch on their provisioning interval or reboot. Force a reboot
  or wait for the interval.
- Check the device's effective scope: a higher-priority scope
  (`mac` > `group` > `site` > `tenant` > `model` > `global`) may be overriding
  your change. Lower group `priority` numbers win (applied later).
- If a device has an explicit config profile assigned (Device detail →
  Assign profile), that profile overrides scope resolution.

## HTTPS provisioning fails, HTTP works

- The phone doesn't trust your TLS certificate. Use a publicly-trusted cert, or
  push your private CA via the `sec.TLS.customCaCert.x` config parameter.
- Confirm the option 160 URL uses `https://` and the cert CN/SAN matches the
  host.

## Cache hit ratio is low

- Expected briefly after a deploy or a global generation bump (cold cache).
- If persistently low: look for frequent template edits (each bumps the global
  generation and invalidates all cached configs). Batch config changes.
- Confirm Redis is healthy and not evicting (`/readyz` checks Redis;
  watch Redis memory).

## Check-in buffer keeps growing

**Symptom:** `polyprov_checkin_buffer_depth` climbs and doesn't drain.

- The Celery worker running `flush_checkins` may be down — confirm the worker
  deployment is healthy.
- Confirm `celery-beat` is running and scheduling the flush.
- PostgreSQL write capacity may be saturated — check DB metrics.
- Mitigations: add worker replicas, raise `CHECKIN_FLUSH_BATCH`.

## `/readyz` returns 503

- It checks PostgreSQL and Redis. The plain-text body names which failed.
- Verify `DATABASE_URL` / `REDIS_URL` and that both services are reachable from
  the pod/container.

## Admin UI shows "Session expired"

- The access token expired and refresh failed. Sign in again.
- If it recurs immediately, `SECRET_KEY` may differ between admin-api replicas —
  all replicas must share the same key.

## Admin UI loads but API calls fail

- In Compose, the UI container proxies `/api` to `admin-api`. Confirm
  `admin-api` is healthy (`docker compose ps`).
- In Kubernetes, confirm the Ingress routes `/api` to the `admin-api` service.
- Check the browser network tab for the failing status: 401 (auth), 403
  (missing permission), 5xx (backend error — check admin-api logs).

## 403 Forbidden on an admin action

- The signed-in user lacks the required permission. Review their roles
  (Users & RBAC). `superadmin` has the `*` wildcard.
- Tenant-scoped users can only see/modify their own tenant's resources.

## Migrations / schema issues

- For dev, `tools/seed.py` creates the schema via `create_all`. For production
  use Alembic (`alembic.ini`, `migrations/env.py`) and apply
  `migrations/partitioning.sql` for partitioned log tables.

## Simulator gets errors at high device counts

- Pre-enroll the synthetic MACs first (the simulator uses OUI `0004f2` + index)
  — see [docs/load-test-plan.md](docs/load-test-plan.md). Unenrolled MACs return
  404 by design.
- Lower `--concurrency` if you're hitting rate limits; tune the NGINX
  rate-limit zones in `nginx/provisioning.conf` for legitimate load.

## Getting more detail

- Backend emits structured JSON logs (request id, mac, latency, cache_hit).
- Raw metrics: `GET /metrics`. Full dashboards: Grafana +
  `deploy/grafana-dashboard.json`.
