# Installation

This guide gets PolyProv running locally for development and evaluation. For
production deployment see [DEPLOYMENT.md](DEPLOYMENT.md).

## Prerequisites

- **Docker** and **Docker Compose v2** (the simplest path — everything is
  containerized).
- Or, for running pieces directly: **Python 3.12+**, **Node.js 22+**,
  **PostgreSQL 16**, and **Redis 7**.

## Option A — Docker Compose (recommended)

This brings up the database, cache, object store, both API planes, the
background workers, the provisioning NGINX, and the Admin UI.

```bash
cd deploy/docker
docker compose up --build -d
```

Wait for the database health check to pass (a few seconds), then create the
schema and seed an initial admin user and sample data:

```bash
docker compose exec admin-api python tools/seed.py
```

The seed prints the credentials it created (defaults below).

### What's now running

| Service | URL | Purpose |
|---------|-----|---------|
| Admin UI | http://localhost:3000 | Web console |
| Admin API (Swagger) | http://localhost:8081/docs | REST API + OpenAPI docs |
| Provisioning plane | http://localhost:8080/provisioning/ | What phones hit |
| MinIO console | http://localhost:9001 | Firmware object store (dev) |

> The Admin UI container proxies `/api` to the admin API internally, so the
> browser sees a single origin and there is no CORS configuration to manage.

### Log in

Open http://localhost:3000 and sign in with the seeded superadmin:

- **Email:** `admin@example.com`
- **Password:** `changeme123`

Override these before seeding by setting `SEED_ADMIN_EMAIL` and
`SEED_ADMIN_PASSWORD` (see `.env.example`).

### Smoke-test the provisioning path

The seed creates three sample CCX devices. Fetch one device's rendered config
exactly as a phone would:

```bash
curl http://localhost:8080/provisioning/0004f2000000.cfg
```

You should get back Poly-format XML. A second request is served from cache
(check the Provisioning Logs page in the UI — the `cache` column shows `hit`).

## Option B — Run components directly (no Docker)

Start PostgreSQL and Redis yourself, then:

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL=postgresql+asyncpg://polyprov:polyprov@localhost:5432/polyprov
export DATABASE_URL_SYNC=postgresql+psycopg2://polyprov:polyprov@localhost:5432/polyprov
export REDIS_URL=redis://localhost:6379/0
export SECRET_KEY=dev-secret-change-me

python tools/seed.py                              # create schema + seed
uvicorn app.main:app --reload --port 8000         # API (all planes)
celery -A app.worker.celery_app worker --loglevel=info   # in another shell
celery -A app.worker.celery_app beat   --loglevel=info   # in another shell
```

```bash
# Frontend (in ui/)
cd ui
npm install
npm run dev      # Vite dev server on http://localhost:5173, proxies /api to :8000
```

## Configuration

All settings are environment variables; see `.env.example` for the full list
and defaults. Copy it to `.env` and adjust. Key ones:

- `SECRET_KEY` — JWT signing key. **Change this.** Use a secret manager in prod.
- `DATABASE_URL` / `DATABASE_URL_SYNC` — async (API) and sync (Celery) DSNs.
- `REDIS_URL` — cache, rate-limit counters, Celery broker.
- `POLYPROV_PLANE` — `all` | `admin` | `provisioning`. Controls which routers a
  process mounts so you can run dedicated nodes.

## Verifying the install

```bash
# Unit tests (no running stack needed)
pip install pytest
pytest tests/test_renderer.py tests/test_resolver.py tests/test_mac.py

# Integration tests (requires the compose stack up + seeded)
POLYPROV_TEST_STACK=1 pytest tests/test_api.py
```

## Next steps

- Point DHCP option 160 at your provisioning URL — see
  [docs/dhcp/README.md](docs/dhcp/README.md).
- Import your fleet via the Devices page (CSV/JSON) or the API.
- Read [OPERATIONS.md](OPERATIONS.md) for day-2 running.
