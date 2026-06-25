import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

const KINDS = ["customer", "region", "site", "building", "department", "model", "firmware_ring", "service_profile"];

export default function Groups() {
  const { data, error, loading, reload } = useFetch(() => api.groups(), []);
  const [show, setShow] = useState(false);
  const [toast, setToast] = useState(null);

  return (
    <div>
      <div className="page-head">
        <div><h1>Groups</h1><div className="sub">Device groupings drive config inheritance by priority</div></div>
        <button className="primary" onClick={() => setShow(true)}>New group</button>
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="groups" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Tenant</th><th>Name</th><th>Kind</th><th>Priority</th></tr></thead>
            <tbody>
              {data.map((g) => (
                <tr key={g.id}>
                  <td className="mono">{g.id}</td><td className="mono">{g.tenant_id}</td>
                  <td>{g.name}</td><td><span className="badge">{g.kind}</span></td>
                  <td className="mono">{g.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No groups yet.</Empty>}

      {show && <CreateGroup onClose={() => setShow(false)}
        onSaved={() => { setShow(false); reload(); setToast({ msg: "Group created", kind: "ok" }); }} />}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function CreateGroup({ onClose, onSaved }) {
  const tenants = useFetch(() => api.tenants(), []);
  const [form, setForm] = useState({ tenant_id: "", name: "", kind: "service_profile", priority: 100 });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true); setError(null);
    try { await api.createGroup({ ...form, tenant_id: Number(form.tenant_id), priority: Number(form.priority) }); onSaved(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return (
    <Modal title="New group" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="field"><label>Tenant</label>
        <select value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}>
          <option value="">Select tenant…</option>
          {tenants.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select></div>
      <div className="field"><label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="row">
        <div className="field"><label>Kind</label>
          <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select></div>
        <div className="field"><label>Priority (lower wins later)</label>
          <input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} /></div>
      </div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.tenant_id || !form.name}>Create</button>
      </div>
    </Modal>
  );
}
