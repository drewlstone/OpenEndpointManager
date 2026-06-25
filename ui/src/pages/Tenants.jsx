import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

export default function Tenants() {
  const { data, error, loading, reload } = useFetch(() => api.tenants(), []);
  const [show, setShow] = useState(false);
  const [toast, setToast] = useState(null);

  return (
    <div>
      <div className="page-head">
        <div><h1>Tenants</h1><div className="sub">Top-level isolation boundary for customers</div></div>
        <button className="primary" onClick={() => setShow(true)}>New tenant</button>
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="tenants" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Slug</th><th>Name</th><th>Status</th></tr></thead>
            <tbody>
              {data.map((t) => (
                <tr key={t.id}>
                  <td className="mono">{t.id}</td><td className="mono">{t.slug}</td>
                  <td>{t.name}</td><td><span className="badge ok">{t.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No tenants yet. Create the first one.</Empty>}

      {show && <CreateTenant onClose={() => setShow(false)}
        onSaved={() => { setShow(false); reload(); setToast({ msg: "Tenant created", kind: "ok" }); }} />}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function CreateTenant({ onClose, onSaved }) {
  const [form, setForm] = useState({ slug: "", name: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true); setError(null);
    try { await api.createTenant(form); onSaved(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return (
    <Modal title="New tenant" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="field"><label>Slug</label>
        <input placeholder="acme" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} /></div>
      <div className="field"><label>Name</label>
        <input placeholder="Acme Corp" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.slug || !form.name}>Create</button>
      </div>
    </Modal>
  );
}
