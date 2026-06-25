import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

export default function Sites() {
  const { data, error, loading, reload } = useFetch(() => api.sites(), []);
  const [show, setShow] = useState(false);
  const [toast, setToast] = useState(null);

  return (
    <div>
      <div className="page-head">
        <div><h1>Sites</h1><div className="sub">Physical locations within a tenant</div></div>
        <button className="primary" onClick={() => setShow(true)}>New site</button>
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="sites" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Tenant</th><th>Name</th><th>Region</th><th>Timezone</th></tr></thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id}>
                  <td className="mono">{s.id}</td><td className="mono">{s.tenant_id}</td>
                  <td>{s.name}</td><td>{s.region || "—"}</td><td className="mono">{s.timezone}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No sites yet.</Empty>}

      {show && <CreateSite onClose={() => setShow(false)}
        onSaved={() => { setShow(false); reload(); setToast({ msg: "Site created", kind: "ok" }); }} />}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function CreateSite({ onClose, onSaved }) {
  const tenants = useFetch(() => api.tenants(), []);
  const [form, setForm] = useState({ tenant_id: "", name: "", region: "", timezone: "UTC" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true); setError(null);
    try { await api.createSite({ ...form, tenant_id: Number(form.tenant_id) }); onSaved(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return (
    <Modal title="New site" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="field"><label>Tenant</label>
        <select value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}>
          <option value="">Select tenant…</option>
          {tenants.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select></div>
      <div className="field"><label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="row">
        <div className="field"><label>Region</label>
          <input placeholder="us-east" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} /></div>
        <div className="field"><label>Timezone</label>
          <input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} /></div>
      </div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.tenant_id || !form.name}>Create</button>
      </div>
    </Modal>
  );
}
