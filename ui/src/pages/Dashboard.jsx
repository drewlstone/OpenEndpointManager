import React from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, useFetch } from "../lib/ui.jsx";

export default function Dashboard() {
  const { data, error, loading } = useFetch(() => api.dashboard(), []);
  const logs = useFetch(() => api.provisioningLogs("?limit=8"), []);

  if (loading) return <Loading what="dashboard" />;
  if (error) return <ErrorBanner error={error} />;
  const d = data || {};

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <div className="sub">Fleet overview and recent provisioning activity</div>
        </div>
      </div>

      <div className="tiles">
        <div className="tile"><div className="label">Total Devices</div><div className="value">{d.total_devices ?? "—"}</div></div>
        <div className="tile"><div className="label">Recent Check-ins (15m)</div><div className="value ok">{d.recent_checkins ?? d.online ?? "—"}</div></div>
        <div className="tile"><div className="label">Stale (24h+)</div><div className="value warn">{d.stale ?? "—"}</div></div>
        <div className="tile"><div className="label">Errors (1h)</div><div className="value bad">{d.errors_last_hour ?? "—"}</div></div>
        <div className="tile"><div className="label">Provisioned (1h)</div><div className="value">{d.provisioning_last_hour ?? "—"}</div></div>
        <Link className="tile" to="/discoveries"><div className="label">Pending Approval</div><div className="value warn">{d.pending_discoveries ?? "—"}</div></Link>
        <div className="tile"><div className="label">Tenants</div><div className="value">{d.tenants ?? "—"}</div></div>
        <div className="tile"><div className="label">Sites</div><div className="value">{d.sites ?? "—"}</div></div>
      </div>

      <div className="card">
        <h2>Devices by model</h2>
        {d.by_model && Object.keys(d.by_model).length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Model</th><th>Count</th></tr></thead>
              <tbody>
                {Object.entries(d.by_model).map(([m, c]) => (
                  <tr key={m}><td className="mono">{m}</td><td>{c}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No devices enrolled yet. <Link to="/devices">Add devices</Link>.</Empty>}
      </div>

      <div className="card">
        <h2>Recent provisioning activity</h2>
        {logs.loading ? <Loading what="logs" /> :
         logs.data && logs.data.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Time</th><th>MAC</th><th>Path</th><th>Status</th><th>Cache</th></tr></thead>
              <tbody>
                {logs.data.map((l) => (
                  <tr key={l.id}>
                    <td className="mono muted">{l.ts?.replace("T", " ").slice(0, 19)}</td>
                    <td className="mono">{l.mac || "—"}</td>
                    <td className="mono">{l.path}</td>
                    <td><span className={"badge " + (l.status_code >= 400 ? "bad" : "ok")}>{l.status_code}</span></td>
                    <td>{l.cache_hit ? <span className="badge info">hit</span> : <span className="badge">miss</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No provisioning activity yet. Boot a device or run the simulator.</Empty>}
      </div>
    </div>
  );
}
