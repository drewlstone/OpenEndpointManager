# Provisioning Validation

## Purpose

This document is the Milestone 0.2 validation procedure for the PolyProv
provisioning engine. It verifies the appliance stack, global master handling,
per-device config behavior, cache behavior, check-in flushing, and provisioning
logs before firmware registration and rollout work begins.

These steps were validated on the Ubuntu host with the project at:

```bash
~/Projects/SipProv/Source/polyprov
```

## Prerequisites

- Docker and Docker Compose v2 are installed.
- The project is checked out at `~/Projects/SipProv/Source/polyprov`.
- The Compose stack lives at `~/Projects/SipProv/Source/polyprov/deploy/docker`.
- Admin credentials are available:
  - Email: `admin@example.com`
  - Password: `changeme123`
- The server is reachable as `localhost` from Ubuntu.
- The latest tested commits include:
  - `520955d Handle global master provisioning correctly`
  - `6f85788 Make provisioning nginx vhost the default server`
  - `9bf8aea Add appliance restart and health checks`

## Validation Steps

### 1. Confirm Repository State

```bash
cd ~/Projects/SipProv/Source/polyprov
git status --short && git log --oneline -3
```

Expected result:

- `git status --short` prints nothing.
- Latest commits include the global master fix and appliance hardening commits.

Observed result:

- Passed. Working tree was clean.

### 2. Validate Docker Compose Configuration

```bash
cd ~/Projects/SipProv/Source/polyprov/deploy/docker
docker compose config --quiet
```

Expected result:

- No output.
- Exit code `0`.

Observed result:

- Passed.

### 3. Start The Stack

```bash
docker compose up -d --build
```

Expected result:

- Images build successfully.
- Containers start.

Observed result:

- Passed.
- Non-fatal warning observed: buildx was not installed, so Compose used the
default builder.

### 4. Check Compose Service Health

```bash
docker compose ps
```

Expected result:

- `db` is up and healthy.
- `redis` is up and healthy.
- `admin-api` is up and healthy.
- `prov-api` containers are up and healthy.
- `nginx`, `ui`, `worker`, `beat`, and `minio` are up.

Observed result:

- Passed.

### 5. Seed The Database

Use `PYTHONPATH=/app` when running `tools/seed.py` inside the API container:

```bash
docker compose exec -e PYTHONPATH=/app admin-api python tools/seed.py
```

Expected result:

```text
Seed complete.
  admin user: admin@example.com / changeme123
  sample tenant 'acme' with 3 CCX devices (0004f2000000..02)
```

Observed result:

- Passed with the adjusted `PYTHONPATH=/app` command.

Failure indicator:

Running the documented command without `PYTHONPATH=/app` failed in this lab:

```bash
docker compose exec admin-api python tools/seed.py
```

Observed error:

```text
ModuleNotFoundError: No module named 'app'
```

Documentation correction:

- Future install/deployment docs should use the adjusted seed command or run the
seed as a module/runtime that has `/app` on `PYTHONPATH`.

### 6. Validate HTTP Health Through NGINX

The Compose NGINX container preserves standard HTTP on container port `80` and
routes by virtual host. The stock nginx image `default.conf` is overridden, so
plain `localhost` falls through to the provisioning `default_server`. Use the
admin Host header for admin-plane checks.

Provisioning plane through NGINX:

```bash
curl -fsS http://localhost:8080/healthz && echo
```

Expected result:

```json
{"status":"ok"}
```

Admin plane through NGINX:

```bash
curl -fsS -H 'Host: admin.example.com' http://localhost:8081/readyz && echo
```

Expected result:

```text
{'db': True, 'redis': True}
```

UI:

```bash
curl -fsS http://localhost:3000/ >/dev/null && echo "UI OK"
```

Expected result:

```text
UI OK
```

Observed result:

- Passed.

Routing note:

The stock nginx image `default.conf` is intentionally overridden by the Compose
stack so `Host: localhost` no longer matches the image's default static site.
Because both host ports still enter the same NGINX listener on container port
`80`, admin-plane requests must use the admin virtual host name. Plain
`localhost:8081` is not a reliable admin-plane signal in the current
single-NGINX Compose model.

### 7. Validate API Containers Directly

Admin API container:

```bash
docker compose exec admin-api curl -fsS http://localhost:8000/readyz && echo
```

Expected result:

```text
{'db': True, 'redis': True}
```

Provisioning API container:

```bash
docker compose exec prov-api curl -fsS http://localhost:8000/readyz && echo
```

Expected result:

```text
{'db': True, 'redis': True}
```

Observed result:

- Passed.

### 8. Confirm No Fake Global-Master Device Exists

```bash
docker compose exec db psql -U polyprov -d polyprov \
  -c "select id, mac, model from device where mac='000000000000';"
```

Expected result:

```text
(0 rows)
```

Observed result:

- Passed.

### 9. Validate Global Master Request

Request the global master twice through NGINX on the provisioning port:

```bash
curl -fsS \
  http://localhost:8080/provisioning/000000000000.cfg \
  -o /tmp/polyprov-master-1.xml

curl -fsS \
  http://localhost:8080/provisioning/000000000000.cfg \
  -o /tmp/polyprov-master-2.xml

diff -u /tmp/polyprov-master-1.xml /tmp/polyprov-master-2.xml
sed -n '1,20p' /tmp/polyprov-master-1.xml
```

Expected result:

- Both requests succeed.
- `diff` prints no output.
- Response contains `<APPLICATION` and `CONFIG_FILES=`.
- Response does not contain `device not enrolled`.

Observed result:

- Passed.
- Response body began with:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!-- PolyProv master config for global -->
<APPLICATION
  CONFIG_FILES=""
  MISC_FILES=""
  LOG_FILE_DIRECTORY=""
  OVERRIDES_DIRECTORY=""
  CONTACTS_DIRECTORY=""
/>
```

### 10. Get Admin API Token

```bash
TOKEN=$(curl -fsS -H 'Host: admin.example.com' \
  http://localhost:8081/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"changeme123"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

test -n "$TOKEN" && echo "TOKEN OK"
```

Expected result:

```text
TOKEN OK
```

Observed result:

- Passed.

### 11. Confirm Current Global-Master Requests Do Not Create Fake Check-Ins

Historical fake `000000000000` check-ins existed in the lab database from prior
testing. Treat them as pre-existing dirty lab data, not evidence that the
current fix is broken.

Use before/after counts to prove the current global-master requests do not add
new fake check-ins:

```bash
BEFORE=$(docker compose exec -T db psql -U polyprov -d polyprov -tAc \
  "select count(*) from checkin_event where mac='000000000000';")

curl -fsS http://localhost:8080/provisioning/000000000000.cfg >/dev/null
curl -fsS http://localhost:8080/provisioning/000000000000.cfg >/dev/null

sleep 3

AFTER=$(docker compose exec -T db psql -U polyprov -d polyprov -tAc \
  "select count(*) from checkin_event where mac='000000000000';")

echo "before=$BEFORE after=$AFTER"
test "$BEFORE" = "$AFTER"
```

Expected result:

```text
before=<N> after=<same N>
```

Observed result:

```text
before=7 after=7
```

Result:

- Passed.

### 12. Validate Enrolled Seeded MAC Request

The seed creates `0004f2000000`.

```bash
curl -fsS \
  http://localhost:8080/provisioning/0004f2000000.cfg \
  -o /tmp/polyprov-device-1.xml

curl -fsS \
  http://localhost:8080/provisioning/0004f2000000.cfg \
  -o /tmp/polyprov-device-2.xml

diff -u /tmp/polyprov-device-1.xml /tmp/polyprov-device-2.xml
sed -n '1,20p' /tmp/polyprov-device-1.xml
```

Expected result:

- Both requests succeed.
- `diff` prints no output.
- Response contains `<PHONE_CONFIG>`.
- Response contains expected seeded template values such as `pool.ntp.org` and
`sip.example.com`.

Observed result:

- Passed.

### 13. Validate Unknown MAC Request

```bash
curl -i http://localhost:8080/provisioning/0004f2ffffff.cfg
```

Expected result:

```text
HTTP/1.1 404 Not Found

device not enrolled
```

Observed result:

- Passed.

### 14. Validate Malformed Filename

```bash
curl -i http://localhost:8080/provisioning/not-a-mac.cfg
```

Expected result:

```text
HTTP/1.1 404 Not Found

not found
```

Observed result:

- Passed.

### 15. Validate Uppercase MAC Filename

```bash
curl -i http://localhost:8080/provisioning/0004F2000000.cfg
```

Expected result:

- `HTTP/1.1 200 OK`.
- Response contains `<PHONE_CONFIG>`.
- Rendered config is for normalized MAC `0004f2000000`.

Observed result:

- Passed.

### 16. Validate Suffix Filename Behavior

```bash
curl -i http://localhost:8080/provisioning/0004f2000000-phone.cfg
```

Expected result:

- Current behavior returns `HTTP/1.1 200 OK`.
- Response contains `<PHONE_CONFIG>`.
- Response is the same rendered device config for `0004f2000000`.

Observed result:

- Passed.

Note:

- This confirms current suffix handling, but Poly model-specific suffix files may
need more exact behavior later.

### 17. Validate Provisioning Logs And Check-In Logs

Wait for the Celery worker flush, then query logs:

```bash
sleep 3

TOKEN=$(curl -fsS -H 'Host: admin.example.com' \
  http://localhost:8081/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"changeme123"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -fsS -H 'Host: admin.example.com' \
  "http://localhost:8081/api/v1/reports/provisioning-logs?mac=0004f2000000&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

curl -fsS -H 'Host: admin.example.com' \
  "http://localhost:8081/api/v1/reports/provisioning-logs?mac=0004f2ffffff&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

curl -fsS -H 'Host: admin.example.com' \
  "http://localhost:8081/api/v1/reports/checkins?mac=0004f2000000&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected result:

- Enrolled MAC provisioning logs include `status_code: 200`.
- Enrolled MAC logs show cache miss then cache hit when using a fresh cache.
- Unknown MAC provisioning logs include `status_code: 404` and
`cache_hit: false`.
- Enrolled MAC check-ins are present after worker flush.

Observed result:

- Passed.
- Enrolled logs showed:
  - first `0004f2000000.cfg` request: `cache_hit: false`
  - second `0004f2000000.cfg` request: `cache_hit: true`
  - uppercase MAC and suffix requests: `cache_hit: true`
- Unknown MAC log showed `status_code: 404` and `cache_hit: false`.
- Enrolled check-ins were flushed and visible.

### 18. Optional Simulator Validation

Attempted command:

```bash
cd ~/Projects/SipProv/Source/polyprov
python3 tools/simulator.py --base-url http://localhost:8080 \
  --devices 3 --concurrency 3 --duration 1
```

Observed result:

```text
ModuleNotFoundError: No module named 'httpx'
```

Result:

- Optional simulator validation was blocked by missing host dependency `httpx`.
- This is not a provisioning engine failure.

Technical debt:

- **Medium:** `tools/simulator.py` says it falls back to `urllib` if `httpx` is
absent, but the implementation imports `httpx` unconditionally.

Future milestone:

- Fix the simulator fallback or provide a documented simulator runtime
environment.

## Troubleshooting Notes

### NGINX returns 404 for localhost health checks

If the admin readiness check returns `404` without a Host header:

```bash
curl http://localhost:8081/readyz
```

use the admin Host header:

```bash
curl -fsS -H 'Host: admin.example.com' http://localhost:8081/readyz
```

Reason:

- The Compose NGINX container uses one standard HTTP listener on container port
`80` with virtual hosts. Both host ports `8080` and `8081` enter that listener,
so NGINX routes admin traffic by `Host: admin.example.com`, not by the external
host port alone.

### Seed fails with `No module named 'app'`

Use:

```bash
docker compose exec -e PYTHONPATH=/app admin-api python tools/seed.py
```

### Historical fake global-master check-ins exist

A dirty lab database may contain old `checkin_event` rows for
`mac='000000000000'`. Do not use an absolute empty-list assertion unless the DB
is freshly initialized. Use the before/after count method to confirm current
requests do not create new fake check-ins.

### Cache hit/miss expectations depend on Redis state

If Redis already has cached config bytes, the first request in a manual test may
show `cache_hit: true`. To prove miss-then-hit behavior without destructive
cache clearing, use a fresh device/MAC or a clean validation environment.

## Success Criteria For Milestone 0 Provisioning Validation

Milestone 0 provisioning validation is considered successful when:

- Docker Compose config is valid.
- The stack starts successfully.
- DB, Redis, admin API, and provisioning API are healthy.
- Database seed succeeds using the documented command for this environment.
- Provisioning NGINX health passes on `localhost:8080` and admin readiness passes with `Host: admin.example.com`.
- API containers pass direct readiness checks.
- No fake `device` row exists for `000000000000`.
- `000000000000.cfg` returns `200` and renders a global master config.
- Repeated `000000000000.cfg` requests return consistent output.
- Current global-master requests do not add fake `000000000000` check-ins.
- Enrolled seeded MAC returns rendered `<PHONE_CONFIG>`.
- Unknown MAC returns `404 device not enrolled`.
- Malformed filename returns `404 not found`.
- Uppercase MAC request is normalized and succeeds.
- Suffix filename behavior is understood and documented.
- Provisioning logs show enrolled `200` and unknown `404` entries.
- Check-in logs show enrolled device requests after worker flush.

The optional simulator is not required for Milestone 0 completion until its
runtime dependency/fallback issue is addressed.
