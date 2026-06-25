import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, useFetch } from "../lib/ui.jsx";

export default function ProvLogs() {
  const [mac, setMac] = useState("");
  const [errorsOnly, setErrorsOnly] = useState(false);

  const q = new URLSearchParams({ limit: "200" });
  if (mac) q.set("mac", mac);
  if (errorsOnly) q.set("status_min", "400");

  const { data, error, loading } = useFetch(() => api.provisioningLogs(`?${q}`), [mac, errorsOnly]);

  return (
    <div>
      <div className="page-head">
        <div><h1>Provisioning Logs</h1><div className="sub">Every config request served, newest first</div></div>
      </div>
      <div className="toolbar">
        <input placeholder="Filter by MAC" value={mac} onChange={(e) => setMac(e.target.value)} />
        <label style={{ display: "flex", alignItems: "center", gap: 6, margin: 0 }}>
          <input type="checkbox" style={{ width: "auto" }} checked={errorsOnly} onChange={(e) => setErrorsOnly(e.target.checked)} />
          Errors only
        </label>
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="logs" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Time</th><th>MAC</th><th>Path</th><th>Status</th><th>Cache</th><th>Bytes</th></tr></thead>
            <tbody>
              {data.map((l) => (
                <tr key={l.id}>
                  <td className="mono muted">{l.ts?.replace("T", " ").slice(0, 19)}</td>
                  <td className="mono">{l.mac ? <Link to={`/devices/${l.mac}`}>{l.mac}</Link> : "—"}</td>
                  <td className="mono">{l.path}</td>
                  <td><span className={"badge " + (l.status_code >= 400 ? "bad" : "ok")}>{l.status_code}</span></td>
                  <td>{l.cache_hit ? <span className="badge info">hit</span> : <span className="badge">miss</span>}</td>
                  <td className="mono muted">{l.bytes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No matching log entries.</Empty>}
    </div>
  );
}
