# Architecture Decision Records

Architecture Decision Records, or ADRs, are short documents that capture important architectural decisions, the context that led to them, the alternatives considered, and the consequences of the chosen direction.

ADRs are intentionally lightweight. They are not full design documents. They exist to preserve decision history so future contributors understand why OpenUC Manager is shaped the way it is.

## Why OpenUC Manager Uses ADRs

OpenUC Manager is evolving into a vendor-neutral Enterprise Unified Communications Operations Platform. Some decisions will be expensive to reverse after adapters, deployments, security models, and operational workflows depend on them.

ADRs help maintain long-term clarity for decisions such as:

- On-premises first and cloud optional architecture
- Air-gapped deployment support
- Admin and provisioning plane separation
- Vendor adapter boundaries
- Firmware trust model
- RBAC and tenant isolation
- API compatibility expectations
- Security and audit requirements
- Database and migration strategy

ADRs improve maintainability by recording the reasoning behind architectural choices, not only the final implementation.

## Numbering Convention

ADRs use a four-digit sequence number followed by a lowercase kebab-case title:

```text
0001-use-markdown-first-documentation.md
0002-on-premises-first-cloud-optional.md
0003-vendor-adapter-architecture.md
```

Numbers are assigned sequentially and are never reused.

## Status Values

Use one of the following status values:

- `Proposed`: The decision is under review.
- `Accepted`: The decision is approved and should guide implementation.
- `Superseded`: A newer ADR replaces this decision.
- `Deprecated`: The decision is no longer recommended, but no direct replacement exists yet.

Accepted ADRs should not be rewritten to change history. If a decision changes, create a new ADR and mark the old one as superseded.

## Standard ADR Template

```markdown
# ADR 0000: Title

## Status

Proposed

## Context

What problem, constraint, or decision pressure exists?

## Decision

What decision is being made?

## Consequences

What improves, what gets harder, and what tradeoffs are accepted?

## Alternatives Considered

What other options were evaluated?

## Related Documents

- Link to related architecture sections, issues, pull requests, or previous ADRs.
```
