import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { endpointHref } from "../lib/endpoints";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

function formatTime(value) {
  return value ? value.replace("T", " ").slice(0, 19) : "never";
}

function optionalNumber(value) {
  return value ? Number(value) : null;
}

function namedValue(name, id, empty = "—") {
  if (name) return name;
  if (id) return `#${id}`;
  return empty;
}

export default function DeviceDetail() {
  const { mac } = useParams();
  const { data: device, error, loading, reload } = useFetch(() => api.device(mac), [mac]);
  const checkins = useFetch(() => api.checkins(`?mac=${mac}&limit=20`), [mac]);
  const logs = useFetch(() => api.provisioningLogs(`?mac=${mac}&limit=20`), [mac]);
  const [showAssign, setShowAssign] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [toast, setToast] = useState(null);

  if (loading) return <Loading what="device" />;
  if (error) return <ErrorBanner error={error} />;
  if (!device) return <Empty>Device not found.</Empty>;

  const title = device.label || device.mac;
  const displayModel = device.model_display || device.model;
  const httpEndpoint = endpointHref(device.endpoint_ip, "http");
  const httpsEndpoint = endpointHref(device.endpoint_ip, "https");

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>{title}</h1>
          <div className="sub">
            {displayModel || "Unknown model"} <span className="muted">·</span> <span className="mono">{device.mac}</span>
            <span className="muted"> · </span><Link to="/devices">All devices</Link>
          </div>
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="ghost" onClick={() => setShowEdit(true)}>Edit device</button>
          <button className="primary" onClick={() => setShowAssign(true)}>Assign config profile</button>
        </div>
      </div>

      <div className="card">
        <h2>Identity</h2>
        <dl className="kv">
          <dt>Friendly Name</dt><dd>{device.label || "—"}</dd>
          <dt>MAC</dt><dd>{device.mac}</dd>
          <dt>Serial</dt><dd>{device.serial || "—"}</dd>
          <dt>Model</dt><dd>{displayModel || "—"}</dd>
          <dt>Software</dt><dd>{device.software_version || "—"}</dd>
        </dl>
      </div>

      <div className="card">
        <h2>Administrative Configuration</h2>
        <dl className="kv">
          <dt>Tenant</dt><dd>{namedValue(device.tenant_name, device.tenant_id)}</dd>
          <dt>Site</dt><dd>{namedValue(device.site_name, device.site_id)}</dd>
          <dt>Primary Group</dt><dd>{namedValue(device.primary_group_name, device.primary_group_id)}</dd>
          <dt>Config Profile</dt><dd>{namedValue(device.config_profile_name, device.config_profile_id)}</dd>
          <dt>Asset Tag</dt><dd>{device.asset_tag || "—"}</dd>
          <dt>Lifecycle</dt><dd>{device.status}</dd>
        </dl>
      </div>

      <div className="card">
        <h2>Current State</h2>
        <dl className="kv">
          <dt>Endpoint IP</dt><dd>{device.endpoint_ip || "—"}</dd>
          <dt>Web UI</dt><dd>{httpEndpoint ? <><a href={httpEndpoint} target="_blank" rel="noreferrer">Open HTTP</a><span className="muted"> · </span><a href={httpsEndpoint} target="_blank" rel="noreferrer">Open HTTPS</a></> : "—"}</dd>
          <dt>Proxy IP</dt><dd>{device.proxy_ip || "—"}</dd>
          <dt>Reachability</dt><dd>{device.reachability_status || "unknown"}</dd>
          <dt>Provisioning Health</dt><dd>{device.provisioning_health || "unknown"}</dd>
          <dt>Identity Confidence</dt><dd>{device.identity_confidence || "unknown"}</dd>
          <dt>Last Check-in</dt><dd>{formatTime(device.last_checkin_at || device.last_seen_at)}</dd>
        </dl>
      </div>

      <div className="card">
        <h2>Recent Activity</h2>
        <h3>Recent check-ins</h3>
        {checkins.loading ? <Loading /> : checkins.data?.length ? (
          <div className="table-wrap" style={{ marginBottom: 18 }}>
            <table>
              <thead><tr><th>Time</th><th>Endpoint IP</th><th>Proxy IP</th><th>User agent</th><th>Config hash</th></tr></thead>
              <tbody>
                {checkins.data.map((c) => (
                  <tr key={c.id}>
                    <td className="mono muted">{c.ts?.replace("T", " ").slice(0, 19)}</td>
                    <td className="mono">{c.endpoint_ip || c.ip || "—"}</td>
                    <td className="mono muted">{c.proxy_ip || "—"}</td>
                    <td className="muted">{c.user_agent || "—"}</td>
                    <td className="mono muted">{c.config_hash ? c.config_hash.slice(0, 12) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No check-ins recorded for this device.</Empty>}

        <h3>Provisioning requests</h3>
        {logs.loading ? <Loading /> : logs.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Time</th><th>Path</th><th>Status</th><th>Cache</th><th>Bytes</th></tr></thead>
              <tbody>
                {logs.data.map((l) => (
                  <tr key={l.id}>
                    <td className="mono muted">{l.ts?.replace("T", " ").slice(0, 19)}</td>
                    <td className="mono">{l.path}</td>
                    <td><span className={"badge " + (l.status_code >= 400 ? "bad" : "ok")}>{l.status_code}</span></td>
                    <td>{l.cache_hit ? <span className="badge info">hit</span> : <span className="badge">miss</span>}</td>
                    <td className="mono muted">{l.bytes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No provisioning requests logged.</Empty>}
      </div>

      {showEdit && (
        <EditDevice device={device} onClose={() => setShowEdit(false)}
          onSaved={() => { setShowEdit(false); reload(); setToast({ msg: "Device updated", kind: "ok" }); }} />
      )}
      {showAssign && (
        <AssignProfile mac={mac} onClose={() => setShowAssign(false)}
          onSaved={() => { setShowAssign(false); reload(); setToast({ msg: "Profile assigned", kind: "ok" }); }} />
      )}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function EditDevice({ device, onClose, onSaved }) {
  const tenantQuery = `?tenant_id=${encodeURIComponent(device.tenant_id)}`;
  const sites = useFetch(() => api.sites(tenantQuery), [device.tenant_id]);
  const groups = useFetch(() => api.groups(tenantQuery), [device.tenant_id]);
  const templates = useFetch(() => api.templates(), []);
  const [form, setForm] = useState({
    label: device.label || "",
    asset_tag: device.asset_tag || "",
    site_id: device.site_id ? String(device.site_id) : "",
    primary_group_id: device.primary_group_id ? String(device.primary_group_id) : "",
    config_profile_id: device.config_profile_id ? String(device.config_profile_id) : "",
    status: device.status || "enrolled",
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  async function save() {
    setBusy(true); setError(null);
    try {
      await api.updateDevice(device.mac, {
        label: form.label || null,
        asset_tag: form.asset_tag || null,
        site_id: optionalNumber(form.site_id),
        primary_group_id: optionalNumber(form.primary_group_id),
        config_profile_id: optionalNumber(form.config_profile_id),
        status: form.status,
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Edit device" onClose={onClose}>
      <ErrorBanner error={error || sites.error || groups.error || templates.error} />

      <h3>Editable Administrative Settings</h3>
      <div className="field"><label>Label / Friendly Name</label>
        <input value={form.label} onChange={(e) => update({ label: e.target.value })} /></div>
      <div className="field"><label>Asset Tag</label>
        <input value={form.asset_tag} onChange={(e) => update({ asset_tag: e.target.value })} /></div>
      <div className="field">
        <label>Site</label>
        <select value={form.site_id} onChange={(e) => update({ site_id: e.target.value })} disabled={sites.loading}>
          <option value="">No site</option>
          {sites.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      <div className="row">
        <div className="field">
          <label>Primary Group</label>
          <select value={form.primary_group_id} onChange={(e) => update({ primary_group_id: e.target.value })} disabled={groups.loading}>
            <option value="">No group</option>
            {groups.data?.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Config Profile / Template</label>
          <select value={form.config_profile_id} onChange={(e) => update({ config_profile_id: e.target.value })} disabled={templates.loading}>
            <option value="">No explicit profile</option>
            {templates.data?.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.scope})</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label>Administrative Lifecycle</label>
        <select value={form.status} onChange={(e) => update({ status: e.target.value })}>
          <option value="enrolled">enrolled</option>
          <option value="disabled">disabled</option>
          <option value="retired">retired</option>
        </select>
      </div>

      <h3>Read-only Device Identity</h3>
      <dl className="kv" style={{ marginBottom: 18 }}>
        <dt>MAC</dt><dd>{device.mac}</dd>
        <dt>Serial</dt><dd>{device.serial || "—"}</dd>
        <dt>Model</dt><dd>{device.model_display || device.model}</dd>
        <dt>Software</dt><dd>{device.software_version || "—"}</dd>
        <dt>Tenant</dt><dd>{namedValue(device.tenant_name, device.tenant_id)}</dd>
        <dt>Endpoint IP</dt><dd>{device.endpoint_ip || "—"}</dd>
        <dt>Proxy IP</dt><dd>{device.proxy_ip || "—"}</dd>
        <dt>Last check-in</dt><dd>{formatTime(device.last_checkin_at || device.last_seen_at)}</dd>
        <dt>Reachability</dt><dd>{device.reachability_status || "unknown"}</dd>
      </dl>

      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy}>Save</button>
      </div>
    </Modal>
  );
}

function AssignProfile({ mac, onClose, onSaved }) {
  const templates = useFetch(() => api.templates(), []);
  const [tid, setTid] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true); setError(null);
    try { await api.assignProfile(mac, tid); onSaved(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <Modal title="Assign config profile" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="field">
        <label>Template</label>
        <select value={tid} onChange={(e) => setTid(e.target.value)}>
          <option value="">Select template…</option>
          {templates.data?.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.scope})</option>)}
        </select>
      </div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !tid}>Assign</button>
      </div>
    </Modal>
  );
}
