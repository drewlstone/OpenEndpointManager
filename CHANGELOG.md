# Changelog

All notable changes to PolyProv are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
semantic versioning.

## [Unreleased]

_Nothing yet._

## [0.1.0] — 2026-06-25

First feature-complete release. A Poly provisioning and device management
platform designed for up to 100,000 endpoints (Poly CCX first, extensible to
other Poly models).

### Added

**Architecture & design**
- Complete architecture document covering system overview, data model,
  provisioning and DHCP workflows, template inheritance, firmware model,
  security, scaling, monitoring, deployment, and a production hardening
  checklist.
- Two-plane design: a cache-first provisioning plane that keeps phones off the
  database, and a separate authenticated admin plane.

**Backend (FastAPI)**
- JWT authentication (access + refresh) and hashed API keys.
- Role-based access control with role → permission mapping and tenant scoping.
- Device inventory: CRUD, search/filter, CSV/JSON import and export, MAC
  normalization, config-profile assignment, last-seen tracking.
- Tenant, site, and group management with group kinds and priorities.
- Template engine: parameter maps merged by scope
  (global → model → tenant → site → group → mac) with parent chaining, rendered
  to Poly-compatible XML and cached in Redis.
- Provisioning endpoint with cache-first serving, generation-based
  invalidation, and per-IP / per-MAC rate limiting.
- Firmware repository, ring-based rollouts (test/pilot/production), rollout
  windows, and rollback.
- Reporting endpoints: dashboard aggregates, provisioning logs, check-in
  history, error logs.
- User and RBAC management endpoints.
- Batched check-in / log writer via Celery, plus scheduled partition
  maintenance.
- Structured JSON logging, Prometheus `/metrics`, and `/healthz` + `/readyz`.

**Admin UI (React + Vite)**
- 14 pages: Login, Dashboard, Devices, Device Detail, Tenants, Sites, Groups,
  Templates, Firmware Repository, Rollout Rings, Provisioning Logs, Check-in
  History, Users & RBAC, System Health.
- Central API client with transparent token refresh; shared data-fetch hook,
  modal, toast, and error components.
- Operator-console visual design with a persistent fleet-status strip.

**Provisioning & DHCP**
- Sample Poly CCX configuration files.
- DHCP option 160 / 161 / 66 guidance for ISC dhcpd, Windows Server, Cisco IOS,
  and MikroTik.

**Deployment & operations**
- Docker Compose stack (PostgreSQL, Redis, MinIO, admin-api, prov-api, worker,
  beat, provisioning NGINX, UI).
- NGINX configs for provisioning, admin, and UI planes with traffic separation
  and rate-limit zones.
- Kubernetes manifests (Deployments, Services, HPA, PDB, Ingress) and a Helm
  chart skeleton.
- Grafana dashboard example.
- Database partitioning SQL for high-volume log tables.

**Testing & tooling**
- Unit tests for the renderer, resolver, and MAC normalization (the
  correctness-critical core).
- Integration tests for auth, devices, provisioning, dashboard, templates,
  users/RBAC, and firmware rings (gated behind a running stack).
- Synthetic device check-in simulator and a load-test plan for 10k / 50k / 100k.

### Known limitations

See [ROADMAP.md](ROADMAP.md) and the "Known limitations" section of the README
for items deferred beyond 0.1, including object-store binary upload through the
UI, Alembic migration history (dev uses `create_all`), and end-to-end load
validation on production-like infrastructure.

[Unreleased]: https://example.com/polyprov/compare/v0.1.0...HEAD
[0.1.0]: https://example.com/polyprov/releases/tag/v0.1.0
