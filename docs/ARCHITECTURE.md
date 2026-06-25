# PolyProv — Architecture Document

A production-grade Poly provisioning and device management platform designed to
serve up to 100,000 SIP endpoints (Poly CCX first, extensible to Edge/Trio/VVX
and collaboration endpoints).

> **Scope note for the reader.** This document is the complete design, and as of
> v0.1.0 the code implements it: the two-plane backend (auth/RBAC, device
> inventory, the provisioning engine with full inheritance + caching, Poly CCX
> config generation), the firmware rollout state machine, batched check-in
> logging, observability, the React admin console, Docker Compose, the NGINX
> traffic split, and Kubernetes manifests with a Helm chart. Items deferred
> beyond 0.1 are listed in `ROADMAP.md`. Where a different design was chosen than
> the original brief requested, the trade-off is called out inline under
> **DESIGN CHOICE**.

---

## 1. System overview

PolyProv is split into two physically separable planes that share one
PostgreSQL system of record but almost never contend for it at runtime:

- **Provisioning plane** — extremely high read volume, tiny payloads, no human
  users. Poly phones boot, fetch a small number of config files and (rarely) a
  firmware image, and check in. This plane must survive 100k devices doing
  staggered check-ins without melting the database. It is served by NGINX in
  front of stateless provisioning workers, backed by a Redis cache of rendered
  configs. **A cache hit never touches PostgreSQL.**
- **Admin/API plane** — low volume, human + automation users, full CRUD,
  strongly authenticated (JWT + API keys), RBAC-gated, fully audited. This is
  where inventory, templates, firmware, and rollouts are managed.

The two planes are deliberately different services (or at least different
deployments of the same image with different route sets enabled) so that a
flood of phone traffic can never starve the admin UI, and an admin-side bug
can't take down provisioning.

```
                         ┌──────────────────────────────────────────┐
   Poly phones  ─────►   │  NGINX (provisioning vhost :80/:443)      │
   (DHCP opt 160/161)    │  - TLS termination                       │
                         │  - serves /firmware/* from object store  │
                         │  - proxies /provisioning/* to API        │
                         │  - rate limit zone: per-MAC / per-IP      │
                         └───────────────┬──────────────────────────┘
                                         │
                                  ┌──────▼───────┐   cache hit (no DB)
                                  │ Prov workers │◄──────────┐
                                  │  (FastAPI)   │           │
                                  └──────┬───────┘     ┌─────┴─────┐
                                         │ miss        │   Redis   │
                                         ▼             │ (configs, │
                                  ┌──────────────┐     │ rate-lim, │
   Admins / CI  ─────►  NGINX ──► │  Admin API   │────►│  queue)   │
   (JWT / API key)     (admin     │  (FastAPI)   │     └─────┬─────┘
                        vhost)    └──────┬───────┘           │
                                         │              ┌────▼─────┐
                                         ▼              │  Celery  │
                                  ┌──────────────┐      │ workers  │
                                  │  PostgreSQL  │◄─────┤ (rollout,│
                                  │  (primary +  │      │  import) │
                                  │   replicas)  │      └──────────┘
                                  └──────────────┘
                                         │
                                  ┌──────▼───────┐
                                  │ Object store │  firmware images,
                                  │ (S3-compat)  │  archived config snapshots
                                  └──────────────┘
```

**DESIGN CHOICE — FastAPI over NestJS.** The prompt allowed either. I chose
FastAPI because (a) Pydantic gives us request/response validation and OpenAPI
generation for free, (b) the provisioning hot path benefits from async I/O to
Redis/Postgres with minimal ceremony, and (c) the config-rendering logic is
pure Python and pairs naturally with Celery for background rollout jobs in the
same language. The trade-off vs. NestJS is weaker compile-time typing; we
mitigate with strict mypy + Pydantic v2 at the boundaries.

---

## 2. Major components

| Component | Responsibility | Scales by |
|---|---|---|
| **NGINX (prov vhost)** | TLS, static firmware serving, rate limiting, proxy to prov workers | add instances behind L4 LB |
| **NGINX (admin vhost)** | TLS, proxy to admin API, stricter rate limits | usually 2 for HA |
| **Provisioning workers** | Resolve + render config per request, serve from cache, write check-in events async | horizontal, stateless |
| **Admin API** | CRUD for tenants/sites/groups/devices/templates/firmware, auth, RBAC, audit, reporting | horizontal, stateless |
| **Admin UI** | React SPA console (14 pages) served as static assets; talks to the Admin API | horizontal, stateless static serving |
| **PostgreSQL** | System of record | primary + read replicas, partitioned log tables |
| **Redis** | Rendered-config cache, rate-limit counters, Celery broker/result | cluster or managed |
| **Celery workers** | Firmware rollout scheduling, bulk import, log rollup, cache warming | horizontal by queue |
| **Object store (S3)** | Firmware binaries, config snapshot archive | managed |
| **Prometheus + Grafana** | Metrics, dashboards, alerting | standard |

---

## 3. Data model

Core entities and the most important columns. Full DDL lives in
`migrations/` and the SQLAlchemy models in `app/models/`.

```
tenant (id, slug, name, status, created_at)
  └─ site (id, tenant_id, name, region, timezone)
       └─ device_group (id, tenant_id, site_id?, name, kind, parent_group_id?)
            kind ∈ {customer, region, site, building, department,
                    model, firmware_ring, service_profile}

device (id, tenant_id, site_id?, primary_group_id?,
        mac CHAR(12) UNIQUE,        -- normalized, lowercase, no separators
        model, serial?, label?,
        firmware_target_id?,        -- explicit pin, overrides ring
        config_profile_id?,         -- explicit template assignment
        status, last_seen_at, last_config_hash, created_at)

device_group_member (device_id, group_id)   -- many-to-many for non-primary groups

config_template (id, tenant_id?, scope, scope_ref, name, parent_id?,
                 body JSONB,        -- key/value params, not raw XML
                 priority, updated_at)
   scope ∈ {global, model, group, tenant, site, mac}

firmware_image (id, model, version, sha256, size_bytes,
                object_key, signed?, created_at)

firmware_assignment (id, scope, scope_ref, firmware_image_id,
                     ring, state, window_id?)
   ring ∈ {test, pilot, production}
   state ∈ {scheduled, active, paused, completed, rolled_back}

rollout_window (id, name, cron?, start_at, end_at, tz)

-- high-volume, append-only, time-partitioned:
checkin_event       (id, device_id, mac, ip, ts, user_agent, config_hash)
provisioning_log    (id, device_id?, mac, ts, path, status_code, cache_hit, bytes)
firmware_log        (id, device_id?, mac, ts, firmware_image_id?, status_code, bytes)
error_log           (id, mac?, ts, kind, detail JSONB)

-- admin plane:
admin_user (id, email, hashed_password, is_active, mfa_secret?)
role (id, name)            user_role (user_id, role_id)
permission (id, name)      role_permission (role_id, permission_id)
api_key (id, tenant_id?, hashed_key, prefix, scopes, last_used_at, expires_at)
audit_log (id, actor_type, actor_id, action, target, before JSONB, after JSONB, ts)
```

**DESIGN CHOICE — templates store params (JSONB), not raw config files.**
The prompt implies MAC/model/group/tenant/global *files*. Storing raw per-MAC
files for 100k devices is an operational nightmare (no inheritance, no diffing,
duplicated boilerplate). Instead each template stores a flat parameter map, and
the engine **resolves** the effective parameter set by merging up the
inheritance chain, then **renders** the Poly-format config files on demand. We
still expose the rendered files at exactly the paths Poly expects, so phones see
no difference. Raw-file overrides are still supported via a `raw_override` key
for escape hatches.

**Partitioning.** `checkin_event`, `provisioning_log`, `firmware_log`, and
`error_log` are `PARTITION BY RANGE (ts)` monthly. A Celery job creates next
month's partition and drops/archives partitions past retention. This keeps the
hot indexes small and makes log pruning an `O(1)` `DROP TABLE`.

---

## 4. Provisioning workflow

1. Phone boots, obtains DHCP lease incl. Option 160 (Poly) → provisioning URL,
   e.g. `https://prov.example.com/provisioning/`.
2. Phone requests its files in Poly's documented order. For CCX the master
   config is `000000000000.cfg` (global) and per-device `<MAC>.cfg`.
3. Request hits NGINX prov vhost → rate-limit check → proxy to a prov worker.
4. Worker computes a **cache key** = `mac:model:config_generation`. It reads
   Redis. **Hit → return bytes, log check-in asynchronously, done. No DB.**
5. **Miss →** worker resolves the effective parameter set:
   `global → model → tenant → site → group(s by priority) → mac`,
   renders the Poly config file(s), stores in Redis with a TTL and a
   generation tag, returns bytes.
6. Check-in / provisioning-log writes are pushed to a Redis list and flushed in
   batches by a Celery consumer (or written via async fire-and-forget with a
   bounded queue). This is the key to surviving 100k devices: **writes are
   batched, reads are cached.**
7. Config changes in the admin plane bump the device's (or scope's)
   `config_generation`, which invalidates the cache key naturally on next fetch.

```
phone ──GET /provisioning/<MAC>.cfg──► nginx ──► worker
                                                   │
                                          redis.get(cachekey)
                                          ┌────────┴────────┐
                                       HIT │                │ MISS
                                          ▼                 ▼
                                 return bytes        resolve chain (DB)
                                 enqueue checkin      render config
                                 (no DB)              redis.set(cachekey)
                                                      return + enqueue checkin
```

---

## 5. DHCP discovery workflow

Poly phones discover their provisioning server via DHCP options, in this
preference order:

- **Option 160** (Poly-specific, recommended) — a string containing the
  provisioning server URL, e.g. `https://prov.example.com/provisioning/`.
  Supports full URL incl. scheme, so HTTPS works directly.
- **Option 161** — Poly also reads this for the provisioning server address in
  some firmware lines; we document setting both 160 and 161 to the same URL for
  maximum compatibility across CCX/Edge/Trio firmware generations.
- **Option 66** (TFTP server name, legacy fallback) — a bare host or URL.
  Older behavior; we support it but recommend 160/161. When only a hostname is
  present, phones default to `http://<host>/`.

Example ISC dhcpd snippet (also in `docs/dhcp/`):

```
option poly-160 code 160 = text;
option poly-161 code 161 = text;
subnet 10.20.0.0 255.255.0.0 {
  option poly-160 "https://prov.example.com/provisioning/";
  option poly-161 "https://prov.example.com/provisioning/";
  # legacy fallback:
  option tftp-server-name "prov.example.com";
}
```

Windows DHCP and Cisco IOS equivalents are in `docs/dhcp/`. Note: Option 160
must be configured as a **string/text** option; sending it as binary is the
most common field failure.

---

## 6. File structure

Provisioning root as served to phones (Poly-compatible layout):

```
/provisioning/
  000000000000.cfg            # master/global config (rendered)
  <MAC>.cfg                   # per-device override config (rendered)
  <MAC>-phone.cfg             # optional per-device phone config
  region/<region>.cfg         # optional shared includes
  models/<model>.cfg          # model defaults (rendered)
  firmware/                    # served by NGINX directly from object store
    ccx/<version>/...
```

Repository layout:

```
app/
  main.py                 # app factory, wires admin + prov routers
  core/                   # config, security, db, redis, logging, metrics
  models/                 # SQLAlchemy models
  schemas/                # Pydantic request/response models
  api/                    # admin routers (auth, devices, templates, firmware...)
  provisioning/           # prov router, resolver, renderer, cache
  services/               # business logic (import, rollout, audit)
migrations/               # Alembic
nginx/                    # prov + admin vhosts, rate-limit zones
deploy/docker/            # Dockerfile, docker-compose.yml
deploy/k8s/               # manifests + Helm chart skeleton
tools/                    # device simulator, load test plan
tests/                    # unit + api tests
docs/                     # this doc, dhcp guides, runbooks
```

---

## 7. Template inheritance model

Effective config for a device is the deep-merge of all applicable templates,
lowest priority first (later wins):

```
1. global            (scope=global)
2. model             (scope=model,  scope_ref=<model>)
3. tenant            (scope=tenant, scope_ref=<tenant_id>)
4. site              (scope=site,   scope_ref=<site_id>)
5. groups            (scope=group,  ordered by group.priority asc)
6. mac               (scope=mac,    scope_ref=<mac>)   -- always wins
```

Templates may also declare an explicit `parent_id` for arbitrary chaining
(e.g. a "lobby phone" template parented to a "kiosk base" template). Resolution
is: build the ordered list above, expand each template's parent chain, then
deep-merge. The merge is key-wise; nested dicts merge, scalars and lists
replace. The result is a flat parameter map handed to the renderer.

Caching: the resolved parameter map and the rendered files are both cached in
Redis keyed by `mac:model:generation`. Any write that could affect a device
bumps the relevant generation counter (per-device for MAC edits, per-scope for
template edits, with a global generation as the nuclear option).

---

## 8. Firmware management model

- **firmware_image** — one row per (model, version), pointing at an object-store
  key, with sha256 and size. Upload validates the binary and computes the hash.
- **firmware_assignment** — binds a firmware image to a scope (model/group/site)
  and a **ring**. Rings model staged rollout:
  - `test` — internal/lab devices, immediate.
  - `pilot` — a small percentage or named group, after test passes.
  - `production` — everyone else, gated by a `rollout_window`.
- **rollout_window** — when production devices are *allowed* to be told to
  upgrade (e.g. 01:00–05:00 site-local). The resolver only advertises the new
  `APP_FILE_PATH` to a production device during its window.
- **rollback** — flipping an assignment's `state` to `rolled_back` and bumping
  generation makes the next check-in advertise the previous known-good version.
  Because phones pull, rollback is just "advertise the old version again."
- **download logging** — every firmware fetch writes a `firmware_log` row
  (async/batched like check-ins). NGINX access logs are the backstop.

State machine: `scheduled → active → (paused ↔ active) → completed`, with
`active|paused → rolled_back` always available.

---

## 9. Device inventory model

- MAC is the natural key, normalized to 12 lowercase hex chars on the way in
  (strip `:`, `-`, `.`, whitespace; reject non-12-hex). All lookups use the
  normalized form; we render whatever separator a given Poly model expects.
- Devices belong to one tenant, optionally one site, one primary group, and any
  number of secondary groups.
- Bulk import accepts CSV or JSON, validates+normalizes MACs, upserts by MAC,
  and reports per-row results. Runs as a Celery job for large files with a
  progress record.
- Search/filter API supports tenant, site, group, model, firmware, status, and
  `last_seen` ranges, all backed by indexes (see §11).
- `last_seen_at` and `last_config_hash` are updated from check-ins via the
  batched writer, never synchronously on the hot path.

---

## 10. Security model

- **Admin auth:** JWT (short-lived access + refresh) for humans; bcrypt/argon2
  password hashing; optional TOTP MFA field. API keys for automation, stored
  hashed (only a prefix is shown after creation), with scopes and expiry.
- **RBAC:** roles → permissions, permissions checked per endpoint via a
  dependency. Seeded roles: `superadmin`, `tenant_admin`, `operator`,
  `readonly`. Tenant-scoped keys/users can only see their tenant's rows
  (row-level filter injected from the auth context).
- **Provisioning auth:** the prov plane is intentionally low-friction (phones
  can't do JWT). Defense in depth instead: network ACLs / mTLS optional, HTTPS
  enforced, per-MAC + per-IP rate limiting, optional per-device shared secret in
  the URL path, and config bodies never contain secrets in cleartext when the
  model supports encrypted config. **MAC is an identifier, not a secret** — we
  never rely on MAC alone for authorization of sensitive config.
- **Audit logging:** every admin mutation writes an `audit_log` row with
  before/after JSON and actor identity.
- **Transport:** HTTPS everywhere; HSTS on admin; TLS for firmware. HTTP
  provisioning is supported for legacy phones but logged and flagged.
- **Secrets:** env/secret-manager only; never in the image or repo.

---

## 11. Scaling model

Targets and the indexes/strategies that hit them:

- **100k devices, staggered check-ins** (Poly default re-provision is hours, so
  steady-state is well under ~30 req/s even with a 2h interval; boot storms are
  the real load). The cache absorbs boot storms because all devices of a
  model/scope share a rendered file once the first miss populates it.
- **Cache-first:** rendered-config cache hit rate should exceed 95% in steady
  state; only generation bumps cause re-renders.
- **Batched writes:** check-in/log writes go through a Redis buffer flushed in
  batches of N or every T ms, turning 100k tiny inserts into a few bulk inserts.
- **Read replicas:** the resolver's DB reads (on cache miss) go to replicas.
- **Indexes (selected):**
  - `device(mac)` unique btree — primary lookup.
  - `device(tenant_id, site_id, status)` — inventory filters.
  - `device(model)`, `device(firmware_target_id)` — rollout queries.
  - `device(last_seen_at)` — stale-device reports.
  - `config_template(scope, scope_ref)` — resolution.
  - `firmware_assignment(scope, scope_ref, state)` — resolution.
  - log tables: `(device_id, ts)` and partition pruning on `ts`.
- **Horizontal scaling:** prov workers and admin API are stateless; scale by
  replica count behind the LB. Celery scales by queue. Postgres scales reads via
  replicas and writes via batching + partitioning; sharding by tenant is the
  next lever if a single primary is ever the bottleneck (not needed at 100k).

---

## 12. Monitoring and logging model

- **Structured JSON logs** with request id, mac, tenant, latency, cache_hit.
- **/metrics** Prometheus endpoint exposing: request rate/latency per route,
  cache hit ratio, render duration, DB pool usage, queue depth, check-ins/sec,
  firmware bytes served, error counts by kind.
- **Grafana** dashboards (JSON in `deploy/`): "Provisioning overview",
  "Firmware rollout", "Inventory health".
- **Health:** `/healthz` (liveness), `/readyz` (readiness — checks DB + Redis).
- **Alerts (suggested):** cache hit ratio < 90%, check-in rate drop > 50%,
  error_log rate spike, replica lag, queue depth growth.

---

## 13. Deployment model

- **Dev:** `docker compose up` brings up Postgres, Redis, the API (admin+prov),
  the Celery worker and beat, the provisioning NGINX, the Admin UI, and MinIO
  for S3 emulation. Local provisioning_root volume. See `INSTALL.md`.
- **Prod:** Kubernetes. Separate Deployments for `admin-api`, `prov-api`,
  `celery-worker`, `celery-beat`, and `ui` (static SPA). NGINX as ingress or
  sidecar; an Ingress routes `/api` and ops endpoints to `admin-api` and `/` to
  the UI. Managed Postgres (primary + replicas) and Redis. S3 for firmware. HPA
  on CPU for the provisioning plane. PodDisruptionBudgets and anti-affinity for
  HA. See `DEPLOYMENT.md`.
- Helm chart skeleton in `deploy/k8s/helm/` with values for replica counts,
  image tags, resource requests, external service endpoints, and the UI host.

---

## 14. Production hardening checklist

- [ ] HTTPS enforced on both planes; valid certs; HSTS on admin.
- [ ] Provisioning and admin on separate hostnames/vhosts (and ideally separate
      node pools).
- [ ] Rate limiting active per-MAC and per-IP on the prov vhost.
- [ ] DB least-privilege roles; app role can't `DROP`; migrations run as a
      separate role.
- [ ] Read replicas configured; resolver reads routed to replicas.
- [ ] Redis persistence/AOF for the write buffer, or accept bounded loss with
      NGINX logs as backstop.
- [ ] Log partitions auto-created and pruned; retention documented.
- [ ] Backups: nightly `pg_dump`/WAL archiving to object store; firmware bucket
      versioned; **tested restore** runbook.
- [ ] Secrets in a manager, not env files in the image.
- [ ] mTLS or network policy restricting who can reach the admin plane.
- [ ] Audit log shipped off-box (immutable store) for tamper evidence.
- [ ] HPA + PDB + anti-affinity; multi-AZ Postgres; DR region with WAL ship.
- [ ] Load test at 1x and 2x target before go-live (simulator in `tools/`).
- [ ] Security review: dependency scan, container scan, OpenAPI fuzz.

---

## Disaster recovery (summary)

- **RPO:** WAL archiving to object store gives ~minutes. **RTO:** restore
  primary from latest base backup + WAL replay, repoint app via service
  discovery. Firmware bucket is independently durable/versioned. Redis cache is
  rebuildable from Postgres (cold start = elevated DB load, mitigated by cache
  warming Celery job). Provisioning degrades gracefully: if Redis is down,
  workers render straight from DB at higher latency; if DB is down, cached
  configs still serve, so most phones stay provisioned.
