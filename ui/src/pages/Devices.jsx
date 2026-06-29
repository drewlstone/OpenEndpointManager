import React, { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

function deviceStatus(d) {
  if (d.status === "disabled") return { cls: "bad", text: "disabled" };
  if (!d.last_seen_at) return { cls: "warn", text: "never seen" };
  const ageMin = (Date.now() - new Date(d.last_seen_at).getTime()) / 60000;
  if (ageMin < 15) return { cls: "ok", text: "online" };
  if (ageMin < 1440) return { cls: "warn", text: "idle" };
  return { cls: "bad", text: "stale" };
}

function formatTime(value) {
  return value ? value.replace("T", " ").slice(0, 19) : "—";
}

function endpointHref(ip) {
  if (!ip) return null;
  return `http://${ip.includes(":") ? `[${ip}]` : ip}`;
}

const columns = [
  ["mac", "MAC"],
  ["model", "Model"],
  ["serial", "Serial"],
  ["label", "Label"],
  ["endpoint_ip", "Endpoint IP"],
  ["tenant", "Tenant"],
  ["site", "Site"],
  ["group", "Group"],
  ["status", "Status"],
  ["last_seen_at", "Last Seen"],
];

export default function Devices() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sort, setSort] = useState("mac");
  const [direction, setDirection] = useState("asc");
  const [showAdd, setShowAdd] = useState(false);
  const [toast, setToast] = useState(null);
  const fileRef = useRef();

  const q = new URLSearchParams();
  if (search.trim()) q.set("q", search.trim());
  if (statusFilter) q.set("status", statusFilter);
  q.set("sort", sort);
  q.set("direction", direction);
  const qs = `?${q}`;

  const { data, error, loading, reload } = useFetch(() => api.devices(qs), [qs]);

  function toggleSort(key) {
    if (sort === key) {
      setDirection((current) => current === "asc" ? "desc" : "asc");
    } else {
      setSort(key);
      setDirection("asc");
    }
  }

  async function onImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fmt = file.name.endsWith(".json") ? "json" : "csv";
    try {
      const res = await api.importDevices(file, fmt);
      setToast({ msg: `Imported ${res.created} new, ${res.updated} updated, ${res.errors.length} errors`, kind: "ok" });
      reload();
    } catch (err) {
      setToast({ msg: err.message, kind: "bad" });
    }
    e.target.value = "";
  }

  return (
    <div>
      <div className="page-head">
        <div><h1>Devices</h1><div className="sub">{data ? `${data.length} shown` : "Inventory"}</div></div>
        <div style={{ display: "flex", gap: 10 }}>
          <input ref={fileRef} type="file" accept=".csv,.json" style={{ display: "none" }} onChange={onImport} />
          <button className="ghost" onClick={() => fileRef.current.click()}>Import CSV/JSON</button>
          <a className="ghost" href={api.exportCsvUrl()}><button className="ghost">Export CSV</button></a>
          <button className="primary" onClick={() => setShowAdd(true)}>Add device</button>
        </div>
      </div>

      <div className="toolbar">
        <input className="wide-filter" placeholder="Search MAC, model, serial, label, IP, tenant, site, group" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="enrolled">enrolled</option>
          <option value="disabled">disabled</option>
        </select>
      </div>

      <ErrorBanner error={error} />
      {loading ? <Loading what="devices" /> :
       data && data.length ? (
        <div className="table-wrap inventory-table">
          <table>
            <thead><tr>{columns.map(([key, label]) => (
              <th key={key}>
                <button className="table-sort" onClick={() => toggleSort(key)} aria-label={`Sort by ${label}`}>
                  {label}<span>{sort === key ? (direction === "asc" ? "^" : "v") : ""}</span>
                </button>
              </th>
            ))}</tr></thead>
            <tbody>
              {data.map((d) => {
                const s = deviceStatus(d);
                const endpoint = endpointHref(d.endpoint_ip);
                return (
                  <tr key={d.id}>
                    <td className="mono"><Link to={`/devices/${d.mac}`}>{d.mac}</Link></td>
                    <td className="mono">{d.model}</td>
                    <td className="mono muted">{d.serial || "—"}</td>
                    <td>{d.label || <span className="muted">—</span>}</td>
                    <td className="mono">{endpoint ? <a href={endpoint} target="_blank" rel="noreferrer">{d.endpoint_ip}</a> : <span className="muted">—</span>}</td>
                    <td>{d.tenant_name || <span className="muted">#{d.tenant_id}</span>}</td>
                    <td>{d.site_name || <span className="muted">—</span>}</td>
                    <td>{d.primary_group_name || <span className="muted">—</span>}</td>
                    <td><span className={"badge " + s.cls}><span className={"pip " + s.cls} />{s.text}</span></td>
                    <td className="mono muted">{formatTime(d.last_seen_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : <Empty>No devices match. Add one or import a CSV.</Empty>}

      {showAdd && <AddDevice onClose={() => setShowAdd(false)} onSaved={() => { setShowAdd(false); reload(); setToast({ msg: "Device added", kind: "ok" }); }} />}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function AddDevice({ onClose, onSaved }) {
  const tenants = useFetch(() => api.tenants(), []);
  const [form, setForm] = useState({ tenant_id: "", mac: "", model: "CCX", label: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true); setError(null);
    try {
      await api.createDevice({ ...form, tenant_id: Number(form.tenant_id) });
      onSaved();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <Modal title="Add device" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="field">
        <label>Tenant</label>
        <select value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}>
          <option value="">Select tenant…</option>
          {tenants.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>
      <div className="field"><label>MAC address</label>
        <input placeholder="00:04:f2:aa:bb:cc" value={form.mac} onChange={(e) => setForm({ ...form, mac: e.target.value })} /></div>
      <div className="row">
        <div className="field"><label>Model</label>
          <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></div>
        <div className="field"><label>Label</label>
          <input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} /></div>
      </div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.tenant_id || !form.mac}>Add device</button>
      </div>
    </Modal>
  );
}
