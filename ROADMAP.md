# Roadmap

PolyProv 0.1 is feature-complete for its scope: provisioning and managing Poly
CCX (and other Poly models) at up to 100,000 endpoints. This roadmap captures
what's deliberately deferred and candidate directions beyond 0.1. It is
indicative, not a commitment.

Items explicitly labeled as approved requirements have been accepted into the
product roadmap, but remain future work until implementation and delivery are
separately documented. They must not be represented as current capabilities.

## Known limitations in 0.1

These are documented gaps, not bugs:

- **Firmware binary upload** is registered by object key; the binary is uploaded
  to object storage out-of-band. In-UI multipart upload with server-side hashing
  is deferred.
- **Migrations:** development creates the schema via `tools/seed.py`
  (`create_all`). An Alembic migration history and the partitioned log-table DDL
  (`migrations/partitioning.sql`) should be formalized into versioned
  migrations for production.
- **End-to-end load validation** at 50k–100k has a documented plan and a
  simulator, but the runs must be executed on production-like infrastructure.
- **MFA** has a schema field (`mfa_secret`) but the TOTP enrollment/verification
  flow is not wired up.
- **Audit log UI:** audit records are written; a dedicated browse/search page is
  not yet in the UI.

## Candidate work beyond 0.1

### Provisioning & devices
- Auto-enrollment policies for unknown MACs (currently 404 by design).
- Broader model coverage with model-specific renderers (Edge, Trio, VVX) and
  per-model file naming conventions.
- Encrypted configuration support where the device model allows it.
- Bulk device operations (reassign, retire) from the inventory view.

### Firmware & rollouts
- In-UI firmware upload with progress and server-side sha256.
- Percentage-based and canary rollouts within the production ring.
- Rollout health gating (auto-pause on error-rate spike).

### Observability & operations
- Audit log browser in the UI.
- Alerting rules packaged alongside the Grafana dashboard.
- Per-tenant usage reporting and export.

### Platform & scale
- Formal Alembic migration chain and a managed partition lifecycle job.
- Optional tenant sharding for deployments beyond a single primary's comfort.
- Read-replica routing made explicit in the data layer.

### Security
- TOTP MFA enrollment and enforcement.
- API key scoping UI and rotation reminders.
- Optional mTLS for the provisioning plane.

## Approved Enterprise UX requirements

The following requirements are approved roadmap items, not implemented
capabilities.

### EP-UX-01 — Persistent Pending Approval Notification

- Sidebar badge with the pending approval count.
- Visible on every page when the count is greater than zero.
- Auto-refresh.
- Amber styling.
- Hidden when the count is zero.
- Links to Pending Approval.

### EP-UX-02 — Enterprise Device Removal Workflow

- Recycle Bin for real managed devices.
- Restore from the Recycle Bin.
- Privileged permanent purge.
- Immutable audit record of device removal and purge actions.
- Immediate cleanup path for seed, simulator, demo, and load-test devices.
- Bulk purge by test tenant or load-test run.
- Future `device_origin` metadata to distinguish device provenance.

### EP-UX-03 — Configurable Fleet Table

- Reorder columns.
- Show or hide columns.
- Resize columns.
- Per-user saved layouts.
- Named views.
- Default view.
- Asset Tag as an available column.
- RBAC remains authoritative; hidden columns are not security controls.

## How priorities are set

Items move from this roadmap into a release when there's a concrete use case
driving them. Open a GitHub discussion to propose or champion an item; see
[CONTRIBUTING.md](CONTRIBUTING.md).
