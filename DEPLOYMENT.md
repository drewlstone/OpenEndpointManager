# Deployment

Production deployment guidance for PolyProv. For local setup see
[INSTALL.md](INSTALL.md). Architectural rationale is in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Topology

PolyProv runs as two planes that share one PostgreSQL system of record but are
deployed and scaled independently:

- **Provisioning plane** (`POLYPROV_PLANE=provisioning`) — scaled high, serves
  the phone fleet, cache-first so it rarely touches the database.
- **Admin plane** (`POLYPROV_PLANE=admin`) — small, authenticated, serves the
  UI and management API.
- **Workers** — Celery worker (batched check-in flush, imports) and Celery beat
  (scheduled partition creation, flush cadence).
- **Admin UI** — static SPA served by NGINX.

Back these with **managed PostgreSQL** (primary + read replicas), **managed
Redis**, and **S3-compatible object storage** for firmware.

## Kubernetes (manifests)

The manifests in `deploy/k8s/manifests.yaml` define everything:

| Kind | Name | Notes |
|------|------|-------|
| ConfigMap | polyprov-config | Non-secret config |
| Secret | polyprov-secrets | DB DSNs, SECRET_KEY — replace with your secret manager |
| Deployment/Service | prov-api | 4 replicas, anti-affinity |
| HorizontalPodAutoscaler | prov-api-hpa | 4–30 replicas on CPU |
| PodDisruptionBudget | prov-api-pdb | minAvailable 2 |
| Deployment/Service | admin-api | 2 replicas |
| Deployment | celery-worker | 2 replicas |
| Deployment | celery-beat | 1 replica (singleton) |
| Deployment/Service | ui | 2 replicas, static SPA |
| Ingress | polyprov-console | Routes `/api`,`/healthz`,`/readyz`,`/metrics` → admin-api; `/` → ui |

```bash
# build and push images
docker build -t <registry>/polyprov:0.1.0 -f deploy/docker/Dockerfile .
docker build -t <registry>/polyprov-ui:0.1.0 ./ui
docker push <registry>/polyprov:0.1.0
docker push <registry>/polyprov-ui:0.1.0

# edit image references + secrets, then apply
kubectl apply -f deploy/k8s/manifests.yaml

# run the seed once as a Job or one-off pod
kubectl run polyprov-seed --rm -it --image=<registry>/polyprov:0.1.0 \
  --env-from=secret/polyprov-secrets -- python tools/seed.py
```

> Configure a **separate Ingress/host** for the provisioning plane
> (`prov-api`) pointed at by DHCP option 160. Keep it off the admin host so
> phone traffic and admin traffic never share a path. The provisioning NGINX
> config with rate-limit zones is in `nginx/provisioning.conf`.

## Kubernetes (Helm)

`deploy/k8s/helm/` contains a chart skeleton. `values.yaml` exposes replica
counts, image tags, resources, external service endpoints, and the UI host.
Source secrets from your secret manager rather than committing them.

```bash
helm install polyprov deploy/k8s/helm \
  --set image.tag=0.1.0 \
  --set secrets.secretKey=$SECRET_KEY \
  --set provApi.minReplicas=6
```

## Traffic separation and NGINX

Three NGINX configs are provided:

- `nginx/provisioning.conf` — provisioning vhost: serves firmware statically
  from the object-store mount, proxies dynamic config to `prov-api`, enforces
  per-IP and per-MAC rate limits.
- `nginx/admin.conf` — admin vhost: proxies to `admin-api` with stricter limits;
  HSTS/TLS blocks ready to uncomment.
- `nginx/ui.conf` — shared-NGINX option that serves the UI and proxies `/api`.
  (In Compose the UI image carries its own `ui/nginx-ui.conf` instead.)

## TLS / HTTPS

- Terminate TLS at the ingress or NGINX. Sample 443 server blocks are in the
  NGINX configs (commented).
- Phones using HTTPS provisioning (option 160 with `https://`) must trust your
  CA. Use a publicly-trusted cert, or push a private CA cert to devices via the
  `sec.TLS.customCaCert.x` config parameter.

## Scaling to 100k devices

- Scale `prov-api` horizontally (HPA handles this). Cache hit ratio should stay
  above ~95% in steady state; only config/firmware changes (generation bumps)
  cause re-renders.
- Add PostgreSQL **read replicas** and route resolver reads there.
- Enable monthly **partitioning** of the log tables
  (`migrations/partitioning.sql`); the beat task pre-creates partitions.
- Tune `CHECKIN_FLUSH_BATCH` and worker replica count if the check-in buffer
  depth grows (watch `polyprov_checkin_buffer_depth`).
- Validate with the simulator before go-live — see
  [docs/load-test-plan.md](docs/load-test-plan.md).

## Backups and DR

- **PostgreSQL:** nightly base backup + WAL archiving to object storage. RPO is
  minutes; RTO is restore + WAL replay. **Test the restore.**
- **Firmware bucket:** enable versioning; it's independently durable.
- **Redis:** AOF persistence for the check-in buffer, or accept bounded loss
  with NGINX access logs as the backstop. The config cache is rebuildable from
  PostgreSQL; a cold start raises DB load briefly (mitigated by the cache-warm
  Celery task).
- **DR region:** ship WAL to a standby; firmware bucket cross-region replication.

## Production hardening

Work through the checklist in [SECURITY.md](SECURITY.md) and
`docs/ARCHITECTURE.md` §14 before exposing the system.
