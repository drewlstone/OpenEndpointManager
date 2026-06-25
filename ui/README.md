# PolyProv Admin UI

React + Vite single-page console for PolyProv. Talks to the admin REST API.

## Pages

Login, Dashboard, Devices, Device Detail, Tenants, Sites, Groups, Templates,
Firmware Repository, Rollout Rings, Provisioning Logs, Check-in History,
Users & RBAC, and System Health.

## Develop

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to http://localhost:8000
```

The dev proxy is configured in `vite.config.js`. Run the backend admin API on
port 8000 (see the repo root [INSTALL.md](../INSTALL.md)).

## Build

```bash
npm run build    # outputs static assets to dist/
```

## Container

The `Dockerfile` builds the SPA and serves it with NGINX (`nginx-ui.conf`),
which also proxies `/api` and the ops endpoints to the `admin-api` service so
the browser sees a single origin. This image is wired into the root Docker
Compose stack as the `ui` service (published on port 3000).

## Structure

```
src/
  main.jsx          entry; mounts the router + auth provider
  App.jsx           shell: sidebar nav, fleet-status strip, routes
  styles.css        design system (operator console)
  lib/
    api.js          central API client (token refresh, endpoint helpers)
    ui.jsx          auth context + shared components (Modal, Toast, useFetch…)
  pages/            one file per page
```

All API access goes through `lib/api.js`; pages never call `fetch` directly.
Shared UI primitives live in `lib/ui.jsx`.
