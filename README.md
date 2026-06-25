# PolyProv

A Poly provisioning and device management platform, designed to serve up to
**100,000 SIP endpoints** (Poly CCX first, extensible to Edge/Trio/VVX and
collaboration endpoints).

**Version 0.1.0 — feature-complete.** PolyProv includes a full architecture, a
two-plane backend (authenticated admin API + cache-first provisioning plane), a
14-page React admin console, firmware ring rollouts, batched check-in logging,
observability, a Docker Compose stack, Kubernetes/Helm deployment, and a device
simulator. The correctness-critical core (config inheritance merge, Poly XML
rendering, MAC normalization) is unit-tested; integration tests cover the API.

See [CHANGELOG.md](CHANGELOG.md) for what's in this release,
[ROADMAP.md](ROADMAP.md) for known limitations and future direction, and the
handoff docs below to get running.

### Documentation

| Doc | Purpose |
|-----|---------|
| [INSTALL.md](INSTALL.md) | Local install and quick start |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment (Docker, K8s, Helm) |
| [OPERATIONS.md](OPERATIONS.md) | Day-2 operations runbook |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-based fixes |
| [API_REFERENCE.md](API_REFERENCE.md) | REST API snapshot (live spec at `/docs`) |
| [SECURITY.md](SECURITY.md) | Security model + hardening checklist |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup and standards |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full system design (14 sections) |
| [docs/dhcp/README.md](docs/dhcp/README.md) | DHCP option 160/161/66 setup |
| [docs/load-test-plan.md](docs/load-test-plan.md) | Load test + security checklist |

---

## Why two planes

Phones and admins have opposite traffic profiles, so PolyProv splits them:

- **Provisioning plane** — huge read volume, no humans, must survive boot
  storms. Cache-first: a cache hit **never touches PostgreSQL**. Writes
  (check-ins, logs) are buffered in Redis and flushed in batches, so 100k phones
  don't become 100k synchronous inserts.
- **Admin plane** — low volume, authenticated (JWT + API keys), RBAC-gated,
  fully audited.

The same image runs as either plane via `POLYPROV_PLANE=provisioning|admin|all`,
so a phone-traffic flood can't starve the admin API and vice versa.

Full design: **`docs/ARCHITECTURE.md`** (14 sections incl. data model, scaling,
security, DR).

---

## Quick start (local)

```bash
cd deploy/docker
docker compose up --build -d

# create schema + seed an admin user and sample devices
docker compose exec admin-api python tools/seed.py
#   -> admin@example.com / changeme123, tenant 'acme', 3 CCX devices

# admin API docs (Swagger/OpenAPI):
open http://localhost:8081/docs        # admin plane via nginx
# or hit the admin-api container directly on its mapped port

# provisioning plane (what phones hit), via nginx:
curl http://localhost:8080/provisioning/0004f2000000.cfg
```

Point a phone (or the simulator) at `http://<host>:8080/provisioning/` via DHCP
option 160 — see `docs/dhcp/README.md`.

---

## Provisioning flow

1. Phone boots, reads **DHCP option 160** (Poly URL), falls back to 161 then 66.
2. Requests `000000000000.cfg` (master), then `<MAC>.cfg` (per-device).
3. NGINX rate-limits (per-IP + per-MAC) and proxies to a prov worker.
4. Worker builds cache key `mac:type:generation`, checks Redis.
   - **Hit** → return bytes, buffer a check-in, **no DB**.
   - **Miss** → resolve the inheritance chain
     (`global → model → tenant → site → group(s) → mac`), render the Poly XML,
     cache it, return, buffer a check-in.
5. Admin edits bump a generation counter, which invalidates the cache key on the
   next fetch.

DHCP details and per-server config (ISC, Windows, Cisco, MikroTik) live in
`docs/dhcp/README.md`.

---

## Template inheritance

Templates store **parameter maps** (JSONB), not raw files, so configs inherit
and diff cleanly. The engine deep-merges all applicable templates (later wins)
and renders the Poly `.cfg` files phones expect. A `raw_override` key is the
escape hatch for verbatim file bodies. See `app/provisioning/resolver.py` and
`renderer.py`; the order and merge semantics are unit-tested in
`tests/test_resolver.py`.

---

## Firmware & rollouts

- `firmware_image` (model+version → object-store key, sha256).
- `firmware_assignment` binds an image to a scope and a **ring**
  (`test → pilot → production`); production is gated by a `rollout_window`.
- **Rollback** = flip the assignment state and bump generation; because phones
  *pull*, the next check-in advertises the previous good version.
- Every firmware fetch is logged (batched). See `app/services/firmware_resolver.py`.

---

## Scaling to 100k devices

- Stateless prov/admin workers scale horizontally behind the LB (HPA in K8s,
  `replicas` in Compose).
- **Cache hit ratio** should exceed ~95% steady-state; only generation bumps
  re-render. All devices of a model/scope share one rendered file.
- **Batched writes** turn 100k tiny inserts into a few bulk inserts
  (`app/worker.py`, every 2s).
- Postgres: read replicas for resolver reads, monthly **partitioning** of log
  tables (`migrations/partitioning.sql`) so pruning is an `O(1)` DROP, and
  indexes sized for 100k (`docs/ARCHITECTURE.md` §11).
- Validate with the simulator before go-live:

```bash
python tools/simulator.py --base-url http://localhost:8080 \
    --devices 10000 --concurrency 500 --duration 60
# repeat at --devices 50000 and 100000 against a production-like stack
```

---

## Security

- JWT (access+refresh) for humans, hashed API keys (prefix-shown-once) for
  automation, RBAC via role→permission, tenant row-scoping, audit log on every
  mutation. Provisioning plane uses defense-in-depth (HTTPS, rate limits,
  optional mTLS/secret-in-path) since phones can't do JWT — **MAC is an
  identifier, not a secret**.
- Hardening checklist: `docs/ARCHITECTURE.md` §14.

---

## Observability

- Structured JSON logs, Prometheus `/metrics`, `/healthz` + `/readyz`.
- Grafana dashboard JSON in `deploy/grafana-dashboard.json`.
- Key metrics: cache hit ratio, render duration, check-in rate, buffer depth,
  request latency per route.

---

## Deployment

- **Dev:** `deploy/docker/docker-compose.yml` (Postgres, Redis, MinIO,
  admin-api, 2× prov-api, worker, beat, NGINX).
- **Prod:** `deploy/k8s/manifests.yaml` (separate Deployments, HPA, PDB,
  anti-affinity) or the Helm chart in `deploy/k8s/helm/`. Use managed
  Postgres (primary+replicas), managed Redis, and S3 for firmware.

---

## Project layout

```
app/            backend (core, models, schemas, api, services, provisioning)
ui/             React + Vite admin console (14 pages)
migrations/     Alembic env + partitioning SQL
nginx/          provisioning + admin + ui vhosts (traffic split, rate limits)
deploy/docker/  Dockerfile + docker-compose
deploy/k8s/     manifests + Helm chart
tools/          seed.py, simulator.py
tests/          unit (renderer/resolver/mac) + gated API tests
docs/           ARCHITECTURE.md, dhcp/, load-test-plan.md
provisioning_root/  sample Poly CCX configs + firmware dir
```

## Running tests

```bash
pip install -r requirements.txt pytest
pytest tests/test_renderer.py tests/test_resolver.py tests/test_mac.py   # no stack needed
POLYPROV_TEST_STACK=1 pytest tests/test_api.py                            # needs compose up
```

---

## Phase status (v0.1.0)

| Phase | Status |
|-------|--------|
| 1 Architecture & spec | Complete (`docs/ARCHITECTURE.md`) |
| 2 Backend foundation (auth, RBAC, OpenAPI) | Implemented |
| 3 Device inventory (import/export, search, MAC norm) | Implemented |
| 4 Provisioning engine (inheritance, caching, CCX render, DHCP) | Implemented + unit-tested |
| 5 Firmware (rings, windows, rollback, logging) | Implemented |
| 6 Check-in & logging (batched) | Implemented |
| 7 Admin UI (14 pages) | Implemented |
| 8 Observability (metrics, health, dashboard) | Implemented |
| 9 Deployment (compose, nginx, k8s, helm) | Implemented |
| 10 Testing & simulator | Unit + integration tests, simulator, load-test plan |

### Known limitations

These are documented and deferred beyond 0.1 (full list in
[ROADMAP.md](ROADMAP.md)):

- Firmware binaries are uploaded to object storage out-of-band and registered by
  key; in-UI multipart upload is deferred.
- Dev creates the schema via `tools/seed.py` (`create_all`); a formal Alembic
  migration chain and the partitioned-table DDL should be finalized for prod.
- The 50k–100k load runs have a plan and simulator but must be executed on
  production-like infrastructure.
- MFA has a schema field but no enrollment flow yet; the audit log has no
  dedicated UI browser.

Validation note: the backend compiles cleanly and the UI bundles cleanly; the
correctness-critical core is unit-tested. End-to-end exercising of the full
stack is done by standing up the Docker Compose environment (see
[INSTALL.md](INSTALL.md)).
