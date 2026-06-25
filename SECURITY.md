# Security

## Reporting a vulnerability

Please report security vulnerabilities privately. **Do not open a public GitHub
issue for security problems.**

Email the maintainers (replace with your project's real contact before public
release): `security@example.com`. Include:

- A description of the issue and its impact.
- Steps to reproduce or a proof of concept.
- Affected version(s) and configuration.

You can expect an acknowledgement and a coordinated disclosure timeline. Please
give maintainers reasonable time to remediate before public disclosure.

## Security model overview

Full detail is in `docs/ARCHITECTURE.md` §10. Summary:

- **Two planes.** The admin plane is authenticated, RBAC-gated, and audited. The
  provisioning plane is intentionally low-friction (phones can't present JWTs)
  and relies on defense in depth: HTTPS, per-IP and per-MAC rate limiting,
  optional mTLS/network policy, and optional per-device secrets. **A MAC address
  is treated as an identifier, not a secret** — it never authorizes sensitive
  config on its own.
- **Authentication.** JWT access + refresh tokens for humans (password hashing
  via bcrypt); API keys for automation, stored only as a SHA-256 hash with the
  full key shown once.
- **Authorization.** Role → permission RBAC with a `*` wildcard for superadmin.
  Tenant-scoped principals are restricted to their tenant's rows.
- **Audit.** Admin mutations write audit records with actor and before/after
  state.
- **Transport.** HTTPS everywhere in production; HSTS on the admin plane; TLS for
  firmware delivery. HTTP provisioning is supported for legacy fleets but
  logged and flagged.
- **Secrets.** Sourced from environment / secret manager — never committed to the
  repo or baked into images. `SECRET_KEY` must be set to a strong random value
  and shared across admin-api replicas.

## Hardening checklist

Before exposing PolyProv to untrusted networks, confirm:

- [ ] HTTPS enforced on both planes; valid certs; HSTS on admin.
- [ ] Provisioning and admin on separate hostnames (ideally separate node
      pools).
- [ ] Rate limiting active per-IP and per-MAC on the provisioning vhost.
- [ ] `SECRET_KEY` is strong, secret, and consistent across replicas.
- [ ] Database uses least-privilege roles; the app role cannot `DROP`;
      migrations run as a separate role.
- [ ] Read replicas configured; resolver reads routed to replicas.
- [ ] Redis persistence (AOF) for the check-in buffer, or accept bounded loss
      with NGINX logs as backstop.
- [ ] Log partitions auto-created and pruned; retention documented.
- [ ] Backups: nightly base backup + WAL archiving; firmware bucket versioned;
      **restore tested**.
- [ ] Secrets sourced from a manager, not env files in the image.
- [ ] mTLS or network policy restricting access to the admin plane.
- [ ] Audit log shipped off-box to an immutable store.
- [ ] HPA + PDB + anti-affinity; multi-AZ PostgreSQL; DR region with WAL ship.
- [ ] Dependency scan (`pip-audit`) and container image scan in CI.
- [ ] Reviewed the security test checklist in `docs/load-test-plan.md`.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

Security fixes are applied to the latest released minor version.
