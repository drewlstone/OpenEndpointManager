# Contributing

Thanks for your interest in PolyProv. This guide covers how to set up, make
changes, and submit them.

## Development setup

See [INSTALL.md](INSTALL.md) — Option B (run components directly) is best for
active development since it gives you hot reload on both backend and frontend.

```bash
# backend
pip install -r requirements.txt pytest
uvicorn app.main:app --reload --port 8000

# frontend
cd ui && npm install && npm run dev
```

## Project layout

```
app/                FastAPI backend
  core/             config, db, redis, security, logging, metrics
  models/           SQLAlchemy models
  schemas/          Pydantic request/response models
  api/              admin-plane routers (auth, devices, admin, reports, users)
  provisioning/     provisioning-plane router, resolver, renderer
  services/         business logic (import, firmware resolution)
  worker.py         Celery tasks
ui/                 React + Vite admin console
tests/              pytest unit + integration tests
deploy/             Docker, Kubernetes, Helm, Grafana
docs/               architecture, DHCP, load-test plan
tools/              seed + device simulator
```

## Coding standards

**Backend (Python):**
- Target Python 3.12. Use type hints throughout.
- Keep the provisioning hot path allocation-light and cache-first — a cache hit
  must never hit the database.
- Validate input at the boundary with Pydantic; normalize MACs with
  `app.core.security.normalize_mac`.
- Parameterized queries only (SQLAlchemy) — no string-built SQL.
- Every admin mutation should be auditable.

**Frontend (React):**
- Functional components and hooks. Shared helpers live in `ui/src/lib/ui.jsx`
  (`useFetch`, `Modal`, `Toast`, `ErrorBanner`, etc.).
- All API access goes through `ui/src/lib/api.js` — don't call `fetch` directly
  from pages.
- Reserve saturated color for device state; keep the rest of the UI quiet (see
  the design notes in `ui/src/styles.css`).
- No browser storage beyond the auth tokens already handled in `api.js`.

## Tests

```bash
# unit tests need no running services
pytest tests/test_renderer.py tests/test_resolver.py tests/test_mac.py

# integration tests need the compose stack up + seeded
POLYPROV_TEST_STACK=1 pytest tests/test_api.py
```

Add unit tests for any new pure logic (rendering, resolution, normalization)
and an integration test for any new endpoint. The renderer and resolver are the
correctness-critical core — changes there must keep their tests green.

## Commit and PR guidelines

- Keep PRs focused; one logical change per PR.
- Describe the change, the rationale, and any trade-offs. If you chose a
  different design than the obvious one, say why (the codebase favors explicit
  trade-off notes).
- Update docs alongside code: if you add an endpoint, update
  [API_REFERENCE.md](API_REFERENCE.md); if you change behavior, update the
  relevant guide.
- Add a CHANGELOG entry under "Unreleased".
- Ensure backend compiles (`python -m py_compile`) and the UI bundles
  (`npm run build`) before submitting.

## Reporting bugs and security issues

- Functional bugs: open a GitHub issue with repro steps, expected vs actual,
  and relevant logs.
- Security vulnerabilities: **do not** open a public issue — see
  [SECURITY.md](SECURITY.md).

## Scope

PolyProv 0.1 is feature-complete (see [CHANGELOG.md](CHANGELOG.md)). New
features are tracked in [ROADMAP.md](ROADMAP.md); please open a discussion
before large additions so direction can be agreed first.
