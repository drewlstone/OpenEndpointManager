# API Reference

Generated from the FastAPI route definitions in `app/api/` and
`app/provisioning/`. The live, always-current interactive reference is served by
the running application at **`/docs`** (Swagger UI) and **`/openapi.json`**
(raw OpenAPI). This document is a stable snapshot for the 0.1.0 release.

- **Base path (admin plane):** `/api/v1`
- **Provisioning plane:** served at root (`/provisioning/...`)
- **Auth:** send `Authorization: Bearer <access_token>` (from `/auth/login`) or
  `X-API-Key: <key>` for automation.
- **Content type:** `application/json` unless noted (import is multipart;
  export is CSV).

Every admin endpoint enforces an RBAC permission (noted per endpoint). The
`superadmin` role holds the `*` wildcard. Tenant-scoped principals only see
their tenant's resources.

---

## Authentication — `/api/v1/auth`

### POST `/auth/login`
Exchange credentials for tokens. Public.

Request: `{ "email": "admin@example.com", "password": "..." }`
Response: `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`

### POST `/auth/refresh`
Get a fresh token pair. Query param `refresh_token=<token>`. Public.

### GET `/auth/me`
Current principal. Returns kind, id, tenant_id, and permissions. Requires auth.

### POST `/auth/api-keys`
Create an API key. Permission: `api_key:create`.
Request: `{ "name": "...", "tenant_id": null, "scopes": [] }`
Response includes `api_key` **shown once** — store it securely.

---

## Devices — `/api/v1/devices`

### POST `/devices`
Create a device. Permission: `device:write`.
Request: `{ "tenant_id": 1, "mac": "00:04:f2:aa:bb:cc", "model": "CCX",
  "site_id": null, "primary_group_id": null, "serial": null, "label": null }`
The MAC is normalized to 12 lowercase hex chars. 409 if it already exists.

### GET `/devices`
List/search devices. Permission: `device:read`.
Query: `tenant_id`, `site_id`, `model`, `status`, `limit` (≤1000), `offset`.
Tenant-scoped principals are restricted to their tenant.

### GET `/devices/{mac}`
Single device by MAC (any separator format accepted). Permission: `device:read`.

### POST `/devices/{mac}/assign-profile/{template_id}`
Assign an explicit config profile to a device; bumps its cache generation.
Permission: `device:write`.

### POST `/devices/import`
Bulk import. Permission: `device:write`. Multipart file upload; query
`fmt=csv|json`. CSV columns: `mac, tenant_id, model, site_id,
primary_group_id, serial, label` (`mac`, `tenant_id` required). Upserts by MAC.
Response: `{ "total", "created", "updated", "errors": [...] }`.

### GET `/devices/export/csv`
Export devices as CSV. Permission: `device:read`.

---

## Organization — `/api/v1`

### Tenants
- **POST `/tenants`** — create. Permission `tenant:write`.
  `{ "slug": "acme", "name": "Acme Corp" }`
- **GET `/tenants`** — list. Permission `tenant:read`.

### Sites
- **POST `/sites`** — create. Permission `site:write`.
  `{ "tenant_id": 1, "name": "HQ", "region": "us-east", "timezone": "UTC" }`
- **GET `/sites`** — list (optional `tenant_id`). Permission `site:read`.

### Groups
- **POST `/groups`** — create. Permission `group:write`.
  `{ "tenant_id": 1, "name": "Lobby phones", "kind": "service_profile",
    "site_id": null, "parent_group_id": null, "priority": 100 }`
  `kind` ∈ customer, region, site, building, department, model, firmware_ring,
  service_profile.
- **GET `/groups`** — list (optional `tenant_id`). Permission `group:read`.

---

## Templates — `/api/v1/templates`

### POST `/templates`
Create a template. Permission: `template:write`. Bumps the global cache
generation.
Request: `{ "name": "...", "scope": "global|model|tenant|site|group|mac",
  "scope_ref": "CCX", "tenant_id": null, "parent_id": null,
  "body": { ...parameter map... }, "priority": 100 }`
`body` is a JSON parameter map (may be nested) merged into the effective config.

### GET `/templates`
List templates (optional `scope`). Permission: `template:read`.

---

## Firmware — `/api/v1`

### GET `/firmware`
List firmware images (optional `model`). Permission: `firmware:read`.

### POST `/firmware`
Register an image already in object storage. Permission: `firmware:write`.
Query: `model`, `version`, `object_key`. 409 if (model, version) exists.

### GET `/firmware/assignments`
List rollout assignments. Permission: `firmware:read`.

### POST `/firmware/assignments`
Create a rollout assignment. Permission: `firmware:write`. Bumps global
generation.
Request: `{ "scope": "model|group|site", "scope_ref": "CCX",
  "firmware_image_id": 1, "ring": "test|pilot|production", "window_id": null }`

### POST `/firmware/assignments/{assignment_id}/rollback`
Roll back an assignment (advertises the previous good version on next check-in).
Permission: `firmware:write`.

---

## Reports — `/api/v1/reports`

All require `device:read`.

### GET `/reports/dashboard`
Aggregate counts: `total_devices`, `online` (seen ≤15m), `stale` (≥24h or
never), `tenants`, `sites`, `provisioning_last_hour`, `errors_last_hour`,
`by_model`.

### GET `/reports/provisioning-logs`
Provisioning request log, newest first. Query: `mac`, `status_min`, `limit`
(≤1000), `offset`.

### GET `/reports/checkins`
Check-in events, newest first. Query: `mac`, `limit`, `offset`.

### GET `/reports/errors`
Error log, newest first. Query: `limit`.

---

## Users & RBAC — `/api/v1/users`

### GET `/users`
List admin users with roles. Permission: `user:read`.

### POST `/users`
Create a user. Permission: `user:write`.
`{ "email": "...", "password": "...", "tenant_id": null, "role_ids": [1] }`

### POST `/users/{user_id}/deactivate`
Deactivate a user. Permission: `user:write`.

### GET `/users/roles/all`
List roles with their permissions. Permission: `user:read`.

### POST `/users/roles`
Create a role. Permission: `user:write`.
`{ "name": "operator", "permission_names": ["device:read", "device:write"] }`

### GET `/users/permissions/all`
List all permission names. Permission: `user:read`.

---

## Provisioning plane — `/provisioning`

### GET `/provisioning/{filename}`
The endpoint Poly phones hit. Not authenticated (defense-in-depth applies:
HTTPS, rate limiting). Filenames:

- `000000000000.cfg` — master config listing per-device config files and,
  when applicable, the firmware `APP_FILE_PATH`.
- `<MAC>.cfg` — the per-device rendered configuration.

Behavior: cache-first (a hit never touches the database), with per-IP and
per-MAC rate limiting. Returns Poly-format XML (`text/xml`). Returns 404 for an
unenrolled MAC, 429 when rate-limited.

---

## Operations endpoints (app root)

Served outside `/api/v1`:

- **GET `/healthz`** — liveness. Always 200 if the process is up.
- **GET `/readyz`** — readiness. 200 when PostgreSQL and Redis are reachable,
  else 503 with a body naming the failed dependency.
- **GET `/metrics`** — Prometheus metrics.
- **GET `/docs`**, **GET `/openapi.json`** — interactive + raw API spec.

---

## Permission reference

Seeded permissions: `tenant:read/write`, `site:read/write`, `group:read/write`,
`device:read/write`, `template:read/write`, `firmware:read/write`,
`user:read/write`, `api_key:create`, and `*` (superadmin wildcard).
