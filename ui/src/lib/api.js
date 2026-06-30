// Central API client. Stores the access token in memory + localStorage,
// attaches it to every request, and transparently refreshes on 401.

const BASE = "/api/v1";

let accessToken = localStorage.getItem("polyprov_access") || null;
let refreshToken = localStorage.getItem("polyprov_refresh") || null;

export function getToken() {
  return accessToken;
}

export function setTokens(access, refresh) {
  accessToken = access;
  refreshToken = refresh;
  if (access) localStorage.setItem("polyprov_access", access);
  else localStorage.removeItem("polyprov_access");
  if (refresh) localStorage.setItem("polyprov_refresh", refresh);
  else localStorage.removeItem("polyprov_refresh");
}

export function clearTokens() {
  setTokens(null, null);
}

async function rawRequest(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  if (opts.body && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  return res;
}

async function request(path, opts = {}) {
  let res = await rawRequest(path, opts);

  // transparent refresh on expiry
  if (res.status === 401 && refreshToken && !path.includes("/auth/")) {
    const refreshed = await tryRefresh();
    if (refreshed) res = await rawRequest(path, opts);
  }

  if (res.status === 401) {
    clearTokens();
    throw new ApiError("Session expired. Please sign in again.", 401);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch (_) { /* non-json error body */ }
    throw new ApiError(detail, res.status);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

async function tryRefresh() {
  try {
    const res = await fetch(`${BASE}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
      method: "POST",
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch (_) {
    return false;
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// ---- Endpoint helpers ----

export const api = {
  // auth
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request("/auth/me"),

  // dashboard / reports
  dashboard: () => request("/reports/dashboard"),
  provisioningLogs: (q = "") => request(`/reports/provisioning-logs${q}`),
  checkins: (q = "") => request(`/reports/checkins${q}`),
  errors: () => request("/reports/errors"),
  discoveries: (q = "") => request(`/discoveries${q}`),
  approveDiscovery: (id, body) =>
    request(`/discoveries/${id}/approve`, { method: "POST", body: JSON.stringify(body) }),

  // devices
  devices: (q = "") => request(`/devices${q}`),
  device: (mac) => request(`/devices/${mac}`),
  createDevice: (body) => request("/devices", { method: "POST", body: JSON.stringify(body) }),
  updateDevice: (mac, body) =>
    request(`/devices/${mac}`, { method: "PATCH", body: JSON.stringify(body) }),
  assignProfile: (mac, templateId) =>
    request(`/devices/${mac}/assign-profile/${templateId}`, { method: "POST" }),
  importDevices: (file, fmt) => {
    const fd = new FormData();
    fd.append("file", file);
    return request(`/devices/import?fmt=${fmt}`, { method: "POST", body: fd });
  },
  exportCsvUrl: () => `${BASE}/devices/export/csv`,

  // org
  tenants: () => request("/tenants"),
  createTenant: (body) => request("/tenants", { method: "POST", body: JSON.stringify(body) }),
  sites: (q = "") => request(`/sites${q}`),
  createSite: (body) => request("/sites", { method: "POST", body: JSON.stringify(body) }),
  groups: (q = "") => request(`/groups${q}`),
  createGroup: (body) => request("/groups", { method: "POST", body: JSON.stringify(body) }),

  // templates
  templates: (q = "") => request(`/templates${q}`),
  createTemplate: (body) => request("/templates", { method: "POST", body: JSON.stringify(body) }),

  // firmware
  firmware: () => request("/firmware"),
  registerFirmware: (model, version, objectKey) =>
    request(`/firmware?model=${encodeURIComponent(model)}&version=${encodeURIComponent(version)}&object_key=${encodeURIComponent(objectKey)}`, { method: "POST" }),
  assignments: () => request("/firmware/assignments"),
  createAssignment: (body) => request("/firmware/assignments", { method: "POST", body: JSON.stringify(body) }),
  rollback: (id) => request(`/firmware/assignments/${id}/rollback`, { method: "POST" }),

  // users / rbac
  users: () => request("/users"),
  createUser: (body) => request("/users", { method: "POST", body: JSON.stringify(body) }),
  roles: () => request("/users/roles/all"),
  permissions: () => request("/users/permissions/all"),
};

export { request };
