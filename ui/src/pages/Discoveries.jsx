import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, useFetch } from "../lib/ui.jsx";

function formatTime(value) {
  return value ? value.replace("T", " ").slice(0, 19) : "-";
}

export default function Discoveries() {
  const [mac, setMac] = useState("");
  const q = new URLSearchParams({ limit: "200", status: "pending" });
  const { data, error, loading } = useFetch(() => api.discoveries(`?${q}`), []);
  const needle = mac.replace(/[:-]/g, "").toLowerCase();
  const rows = needle ? (data || []).filter((d) => d.mac.includes(needle)) : data;

  return (
    <div>
      <div className="page-head">
        <div><h1>Pending Approval</h1><div className="sub">Unknown Poly endpoints discovered from MAC-scoped provisioning requests</div></div>
      </div>
      <div className="toolbar">
        <input placeholder="Filter by MAC" value={mac} onChange={(e) => setMac(e.target.value)} />
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="discoveries" /> : rows?.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Last Seen</th><th>MAC</th><th>Model</th><th>Firmware</th>
                <th>Endpoint IP</th><th>Proxy IP</th><th>Requests</th><th>Last Path</th><th>Status</th><th>User Agent</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id}>
                  <td className="mono muted">{formatTime(d.last_seen_at)}</td>
                  <td className="mono">{d.mac}</td>
                  <td className="mono">{d.model || "-"}</td>
                  <td className="mono muted">{d.firmware_version || "-"}</td>
                  <td className="mono">{d.endpoint_ip || "-"}</td>
                  <td className="mono muted">{d.proxy_ip || "-"}</td>
                  <td className="mono">{d.request_count}</td>
                  <td className="mono">{d.last_path}</td>
                  <td><span className={"badge " + (d.last_status >= 400 ? "bad" : "ok")}>{d.last_status}</span></td>
                  <td className="muted">{d.user_agent || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No pending discoveries. Unknown Poly devices will appear here after a valid MAC-scoped provisioning request.</Empty>}
    </div>
  );
}
