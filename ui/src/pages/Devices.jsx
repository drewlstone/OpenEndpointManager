import React, { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

function deviceStatus(d) {
  if (!d.last_seen_at) return { cls: "warn", text: "never seen" };
  const ageMin = (Date.now() - new Date(d.last_seen_at).getTime()) / 60000;
  if (ageMin < 15) return { cls: "ok", text: "online" };
  if (ageMin < 1440) return { cls: "warn", text: "idle" };
  return { cls: "bad", text: "stale" };
}

export default function Devices() {
  const [model, setModel] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [toast, setToast] = useState(null);
  const fileRef = useRef();

  const q = new URLSearchParams();
  if (model) q.set("model", model);
  if (statusFilter) q.set("status", statusFilter);
  const qs = q.toString() ? `?${q}` : "";

  const { data, error, loading, reload } = useFetch(() => api.devices(qs), [qs]);

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
        <input placeholder="Filter model (e.g. CCX)" value={model} onChange={(e) => setModel(e.target.value)} />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="enrolled">enrolled</option>
          <option value="disabled">disabled</option>
        </select>
      </div>

      <ErrorBanner error={error} />
      {loading ? <Loading what="devices" /> :
       data && data.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>MAC</th><th>Model</th><th>Label</th><th>Status</th><th>Last seen</th></tr></thead>
            <tbody>
              {data.map((d) => {
                const s = deviceStatus(d);
                return (
                  <tr key={d.id}>
                    <td className="mono"><Link to={`/devices/${d.mac}`}>{d.mac}</Link></td>
                    <td className="mono">{d.model}</td>
                    <td>{d.label || <span className="muted">—</span>}</td>
                    <td><span className={"badge " + s.cls}><span className={"pip " + s.cls} />{s.text}</span></td>
                    <td className="mono muted">{d.last_seen_at ? d.last_seen_at.replace("T", " ").slice(0, 19) : "—"}</td>
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
