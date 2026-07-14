# OpenUC Manager Documentation

OpenUC Manager documentation is the canonical design and operating reference for the project. It describes the platform vision, architecture, security posture, operational model, developer workflow, and reference material for an enterprise Unified Communications Operations Platform.

This documentation set is intentionally organized for long-term maintenance. The current implementation began with Poly voice provisioning, but the documentation architecture reflects the broader product direction: vendor-neutral, enterprise-first, security-first, on-premises first, air-gap capable, cloud optional, and adapter-based.

## Documentation as Code

OpenUC Manager uses a Documentation-as-Code approach:

- Documentation is stored with the source repository.
- Documentation changes are reviewed like code changes.
- Architecture decisions are recorded explicitly.
- Markdown is the source format.
- Diagrams should use Mermaid where practical.
- Generated outputs, such as PDFs, should be derived from Markdown rather than edited directly.
- Documentation should evolve incrementally with implementation.

The goal is to keep product intent, architecture, operations, and implementation aligned as the platform grows.

## Documentation Maturity Model

### Level 1: Project Documentation

Project documentation explains what OpenUC Manager is, why it exists, and how to orient quickly.

Expected documents:

- Project overview
- Project charter
- Roadmap
- Contributing guide
- Changelog
- License

### Level 2: Architecture Documentation

Architecture documentation explains how the system is designed and why major decisions were made.

Expected documents:

- System Architecture & Design Specification
- Security Architecture
- Vendor Adapter Architecture
- Deployment Architecture
- Data Model
- Architecture Decision Records

### Level 3: Operational Documentation

Operational documentation helps administrators deploy, run, secure, observe, back up, restore, and troubleshoot OpenUC Manager.

Expected documents:

- Deployment Guide
- Administrator Guide
- Operations Manual
- Backup and Restore Guide
- Air-Gapped Deployment Guide
- Troubleshooting Guide
- Firmware Operations Guide

### Level 4: Developer Documentation

Developer documentation helps contributors safely extend the platform.

Expected documents:

- Developer Guide
- Vendor Adapter SDK Guide
- Testing Guide
- Database Migrations Guide
- Frontend Development Guide
- Release Process

### Level 5: Reference Documentation

Reference documentation provides precise lookup material for APIs, configuration, permissions, metrics, schemas, and adapter contracts.

Expected documents:

- REST API Guide
- OpenAPI Reference
- Configuration Reference
- Environment Variables Reference
- RBAC Permissions Reference
- Adapter Contracts Reference
- Database Schema Reference
- Metrics Reference

## Documentation Index

### Project and Charter

- Project Charter: `docs/charter/project-charter.md` (planned)
- [Product Roadmap](../ROADMAP.md) — includes approved future requirements; roadmap entries are not implemented capabilities unless separately documented as delivered

### Architecture

- [Enterprise Architecture Blueprint](architecture/enterprise-architecture-blueprint.md) — authoritative target architecture, Enterprise Foundation (EF-1) roadmap, and approved Enterprise UX roadmap requirements
- [System Architecture & Design Specification](architecture/system-architecture-design-specification.md)
- Security Architecture: `docs/architecture/security-architecture.md` (planned)
- Vendor Adapter Architecture: `docs/architecture/vendor-adapter-architecture.md` (planned)
- Deployment Architecture: `docs/architecture/deployment-architecture.md` (planned)
- Data Model: `docs/architecture/data-model.md` (planned)
- [Architecture Decision Records](adr/README.md)

### Guides

- Deployment Guide: `docs/guides/deployment-guide.md` (planned)
- Administrator Guide: `docs/guides/administrator-guide.md` (planned)
- Developer Guide: `docs/guides/developer-guide.md` (planned)
- Vendor Adapter SDK Guide: `docs/guides/vendor-adapter-sdk-guide.md` (planned)
- Operations Manual: `docs/guides/operations-manual.md` (planned)
- Air-Gapped Deployment Guide: `docs/guides/air-gapped-deployment-guide.md` (planned)
- Backup and Restore Guide: `docs/guides/backup-restore-guide.md` (planned)
- Troubleshooting Guide: `docs/guides/troubleshooting-guide.md` (planned)

### Reference

- REST API Guide: `docs/reference/rest-api-guide.md` (planned)
- OpenAPI Reference: `docs/reference/openapi.md` (planned)
- Configuration Reference: `docs/reference/configuration-reference.md` (planned)
- Environment Variables Reference: `docs/reference/environment-variables.md` (planned)
- RBAC Permissions Reference: `docs/reference/rbac-permissions.md` (planned)
- Adapter Contracts Reference: `docs/reference/adapter-contracts.md` (planned)
- Database Schema Reference: `docs/reference/database-schema.md` (planned)
- Metrics Reference: `docs/reference/metrics-reference.md` (planned)

### Assets

- Images: `docs/assets/images/`
- Generated exports: `docs/assets/exports/`
- Mermaid diagram sources: `docs/architecture/diagrams/`

## Document Families

### Charter

The charter family defines project identity, mission, scope, non-goals, stakeholders, and success criteria.

### Architecture

The architecture family defines system structure, security posture, trust boundaries, adapter strategy, deployment assumptions, and long-lived technical principles.

### Guides

The guide family provides task-oriented material for administrators, operators, developers, and adapter authors.

### Reference

The reference family provides exact technical lookup material for APIs, configuration, permissions, metrics, schemas, and contracts.

### ADRs

Architecture Decision Records document significant decisions, rejected alternatives, and long-term consequences.

### Assets

The assets family stores images, generated exports, and diagram sources used by the documentation set.
