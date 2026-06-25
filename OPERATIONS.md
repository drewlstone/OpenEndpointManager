# Operations

Day-2 runbook for operators running PolyProv. Assumes a deployed stack (see
[DEPLOYMENT.md](DEPLOYMENT.md)).

## Daily situational awareness

The Admin UI top bar shows a persistent fleet-status strip (online / stale /
errors-per-hour / total) on every page. The **Dashboard** adds counts by model
and recent provisioning activity. For metrics and trends use Grafana with the
dashboard in `deploy/grafana-dashboard.json`.

Key health signals:

| Signal | Where | Healthy |
|--------|-------|---------|
| Cache hit ratio | Grafana / System Health page | > 95% steady state |
| Check-in buffer depth | `polyprov_checkin_buffer_depth` | bounded, drains between flushes |
| Provisioning p95 latency | `polyprov_provisioning_latency_seconds` | low for cache hits |
| Errors per hour | Dashboard / fleet strip | near zero |
| Readiness | `/readyz` | 200 (DB + Redis reachable) |

## Common tasks

### Enroll devices

- **UI:** Devices → Import CSV/JSON, or Add device.
- **API:** `POST /api/v1/devices/import?fmt=csv` (multipart file) or
  `POST /api/v1/devices`.
- CSV columns: `mac, tenant_id, model, site_id, primary_group_id, serial, label`
  (only `mac` and `tenant_id` are required). MACs are normalized automatically
  from any separator style.

### Change configuration

Templates store parameter maps merged by scope
(`global → model → tenant → site → group → mac`). Edit or add a template
(Templates page). Saving bumps a generation counter, so the next phone fetch
re-renders and re-caches automatically — no cache flush needed.

### Roll out firmware

1. Upload the binary to object storage.
2. Register its metadata: Firmware page → Register firmware (model, version,
   object key).
3. Assign to a ring: Rollout Rings → New assignment. `test`/`pilot` advertise
   immediately; `production` advertises only inside its rollout window.
4. **Rollback:** Rollout Rings → Roll back. Because phones pull, the next
   check-in advertises the previous good version.

### Find why a device isn't provisioning

1. Device detail page → check Last seen, recent check-ins, and provisioning
   requests.
2. Provisioning Logs (filter by MAC) → look for 404 (not enrolled) or other
   non-200 status.
3. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for specific symptoms.

## Cache behavior

- A cache **hit** never touches PostgreSQL; it serves rendered bytes from Redis
  and buffers a check-in.
- Cache is keyed by `mac:type:generation`. Invalidation is implicit: editing a
  template bumps the global generation; editing/assigning a device bumps its
  per-device generation. There is no manual "flush cache" button by design —
  changes propagate on next fetch.
- `CONFIG_CACHE_TTL` (default 3600s) bounds staleness even absent a generation
  bump.

## Check-in write path

Phones don't write to PostgreSQL directly. Provisioning workers push check-in
and log records onto a Redis list; the Celery `flush_checkins` task (every ~2s)
bulk-inserts them and updates `last_seen_at`. If the buffer grows:

- Add Celery worker replicas.
- Raise `CHECKIN_FLUSH_BATCH`.
- Check PostgreSQL write capacity.

## Log retention

The high-volume log tables (`checkin_event`, `provisioning_log`,
`firmware_log`, `error_log`) are designed for monthly range partitioning
(`migrations/partitioning.sql`). The beat task pre-creates next month's
partition. Prune old data by dropping old partitions (an O(1) `DROP TABLE`).
Set retention per your compliance needs.

## Scaling levers (quick reference)

| Symptom | Lever |
|---------|-------|
| High prov latency / CPU | More `prov-api` replicas (HPA) |
| Cache hit ratio dropping | Raise `CONFIG_CACHE_TTL`; check for churny template edits |
| Check-in buffer growing | More Celery workers; raise flush batch |
| Resolver DB load on misses | Add read replicas |
| PostgreSQL write pressure | Confirm batching working; partition + prune logs |

## Backups

Verify nightly PostgreSQL backups and WAL archiving are succeeding. Confirm the
firmware bucket has versioning enabled. **Periodically rehearse a restore** —
an untested backup is not a backup.

## Routine checks

- Weekly: review error logs and failed provisioning attempts; confirm backup
  jobs green; confirm partition creation ran.
- Monthly: prune expired log partitions; review API keys for unused/expired
  entries; rotate `SECRET_KEY` per policy (invalidates active sessions).
