import React from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, useFetch } from "../lib/ui.jsx";

function formatPercent(value) {
  return value === null || value === undefined ? "-" : `${(value * 100).toFixed(1)}%`;
}

function formatRate(value) {
  return value === null || value === undefined ? "-" : `${(value * 100).toFixed(2)}%`;
}

function statusClass(status) {
  if (status === "ready") return "ok";
  if (status === "warning") return "warn";
  return "bad";
}

function titleCase(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "Unknown";
}

export default function Dashboard() {
  const { data, error, loading } = useFetch(() => api.dashboard(), []);
  const readiness = useFetch(() => api.provisioningReadiness(), []);
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

      <div className="card">
        <h2>Provisioning Readiness</h2>
        <ErrorBanner error={readiness.error} />
        {readiness.loading ? <Loading what="readiness" /> : readiness.data ? (
          <>
            <div className="table-wrap" style={{ marginBottom: readiness.data.attention?.length ? 16 : 0 }}>
              <table>
                <thead><tr><th>Overall</th><th>Total</th><th>Recent Check-ins</th><th>Stale</th><th>Pending Approval</th><th>Requests 15m</th><th>Error Rate</th><th>Cache Hit Ratio</th><th>Check-in Buffer</th></tr></thead>
                <tbody>
                  <tr>
                    <td><span className={"badge " + statusClass(readiness.data.status)}>{titleCase(readiness.data.status)}</span></td>
                    <td className="mono">{readiness.data.fleet.total_devices}</td>
                    <td className="mono">{readiness.data.fleet.recent_checkins_15m}</td>
                    <td className="mono">{readiness.data.fleet.stale_24h}</td>
                    <td className="mono"><Link to="/discoveries">{readiness.data.fleet.pending_discoveries}</Link></td>
                    <td className="mono">{readiness.data.provisioning.requests_15m}</td>
                    <td className="mono">{formatRate(readiness.data.provisioning.error_rate_15m)}</td>
                    <td className="mono">{formatPercent(readiness.data.provisioning.cache_hit_ratio_15m)}</td>
                    <td className="mono">{readiness.data.buffers.checkin_buffer_depth ?? "-"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            {readiness.data.attention?.length ? (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Severity</th><th>Attention Item</th></tr></thead>
                  <tbody>
                    {readiness.data.attention.map((item) => (
                      <tr key={item.code}>
                        <td><span className={"badge " + (item.severity === "critical" ? "bad" : item.severity === "warning" ? "warn" : "info")}>{item.severity}</span></td>
                        <td>{item.label}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        ) : <Empty>Provisioning readiness is unavailable.</Empty>}
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
