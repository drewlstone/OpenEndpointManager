import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { endpointHref } from "../lib/endpoints";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

export default function DeviceDetail() {
  const { mac } = useParams();
  const { data: device, error, loading, reload } = useFetch(() => api.device(mac), [mac]);
  const checkins = useFetch(() => api.checkins(`?mac=${mac}&limit=20`), [mac]);
  const logs = useFetch(() => api.provisioningLogs(`?mac=${mac}&limit=20`), [mac]);
  const [showAssign, setShowAssign] = useState(false);
  const [toast, setToast] = useState(null);

  if (loading) return <Loading what="device" />;
  if (error) return <ErrorBanner error={error} />;
  if (!device) return <Empty>Device not found.</Empty>;

  const endpoint = endpointHref(device.endpoint_ip);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="mono">{device.mac}</h1>
          <div className="sub"><Link to="/devices">← All devices</Link></div>
        </div>
        <button className="primary" onClick={() => setShowAssign(true)}>Assign config profile</button>
      </div>

      <div className="card">
        <h2>Device</h2>
        <dl className="kv">
          <dt>MAC</dt><dd>{device.mac}</dd>
          <dt>Model</dt><dd>{device.model}</dd>
          <dt>Software</dt><dd>{device.software_version || "—"}</dd>
          <dt>Serial</dt><dd>{device.serial || "—"}</dd>
          <dt>Label</dt><dd>{device.label || "—"}</dd>
          <dt>Tenant ID</dt><dd>{device.tenant_id}</dd>
          <dt>Site ID</dt><dd>{device.site_id ?? "—"}</dd>
          <dt>Status</dt><dd>{device.status}</dd>
          <dt>Endpoint IP</dt><dd>{endpoint ? <a href={endpoint} target="_blank" rel="noreferrer">{device.endpoint_ip}</a> : "—"}</dd>
          <dt>Proxy IP</dt><dd>{device.proxy_ip || "—"}</dd>
          <dt>Reachability</dt><dd>{device.reachability_status || "unknown"}</dd>
          <dt>Last check-in</dt><dd>{(device.last_checkin_at || device.last_seen_at) ? (device.last_checkin_at || device.last_seen_at).replace("T", " ").slice(0, 19) : "never"}</dd>
        </dl>
      </div>

      <div className="card">
        <h2>Recent check-ins</h2>
        {checkins.loading ? <Loading /> : checkins.data?.length ? (
          <div className="table-wrap">
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
      </div>

      <div className="card">
        <h2>Provisioning requests</h2>
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

      {showAssign && (
        <AssignProfile mac={mac} onClose={() => setShowAssign(false)}
          onSaved={() => { setShowAssign(false); reload(); setToast({ msg: "Profile assigned", kind: "ok" }); }} />
      )}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
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
