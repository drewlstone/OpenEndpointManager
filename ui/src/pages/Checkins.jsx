import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, useFetch } from "../lib/ui.jsx";

export default function Checkins() {
  const [mac, setMac] = useState("");
  const q = new URLSearchParams({ limit: "200" });
  if (mac) q.set("mac", mac);
  const { data, error, loading } = useFetch(() => api.checkins(`?${q}`), [mac]);

  return (
    <div>
      <div className="page-head">
        <div><h1>Check-in History</h1><div className="sub">Device contact events, newest first</div></div>
      </div>
      <div className="toolbar">
        <input placeholder="Filter by MAC" value={mac} onChange={(e) => setMac(e.target.value)} />
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="check-ins" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Time</th><th>MAC</th><th>Endpoint IP</th><th>Proxy IP</th><th>User agent</th><th>Config hash</th></tr></thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.id}>
                  <td className="mono muted">{c.ts?.replace("T", " ").slice(0, 19)}</td>
                  <td className="mono">{c.mac ? <Link to={`/devices/${c.mac}`}>{c.mac}</Link> : "—"}</td>
                  <td className="mono">{c.endpoint_ip || c.ip || "—"}</td>
                  <td className="mono muted">{c.proxy_ip || "—"}</td>
                  <td className="muted">{c.user_agent || "—"}</td>
                  <td className="mono muted">{c.config_hash ? c.config_hash.slice(0, 12) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No check-ins recorded yet.</Empty>}
    </div>
  );
}
