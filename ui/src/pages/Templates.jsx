import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

const SCOPES = ["global", "model", "tenant", "site", "group", "mac"];

export default function Templates() {
  const { data, error, loading, reload } = useFetch(() => api.templates(), []);
  const [show, setShow] = useState(false);
  const [view, setView] = useState(null);
  const [toast, setToast] = useState(null);

  return (
    <div>
      <div className="page-head">
        <div><h1>Templates</h1><div className="sub">Parameter maps merged by scope: global → model → tenant → site → group → mac</div></div>
        <button className="primary" onClick={() => setShow(true)}>New template</button>
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="templates" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Name</th><th>Scope</th><th>Scope ref</th><th>Priority</th><th></th></tr></thead>
            <tbody>
              {data.map((t) => (
                <tr key={t.id}>
                  <td className="mono">{t.id}</td><td>{t.name}</td>
                  <td><span className="badge info">{t.scope}</span></td>
                  <td className="mono">{t.scope_ref || "—"}</td>
                  <td className="mono">{t.priority}</td>
                  <td><button className="ghost" onClick={() => setView(t)}>View body</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No templates yet. Create a global default to start.</Empty>}

      {show && <CreateTemplate onClose={() => setShow(false)}
        onSaved={() => { setShow(false); reload(); setToast({ msg: "Template created", kind: "ok" }); }} />}
      {view && (
        <Modal title={`${view.name} — body`} onClose={() => setView(null)}>
          <textarea className="mono" readOnly value={JSON.stringify(view.body, null, 2)} />
          <div className="modal-actions"><button className="ghost" onClick={() => setView(null)}>Close</button></div>
        </Modal>
      )}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function CreateTemplate({ onClose, onSaved }) {
  const tenants = useFetch(() => api.tenants(), []);
  const [form, setForm] = useState({
    name: "", scope: "global", scope_ref: "", tenant_id: "", priority: 100,
    bodyText: JSON.stringify({ voIpProt: { server: { 1: { address: "sip.example.com" } } } }, null, 2),
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true); setError(null);
    let body;
    try { body = JSON.parse(form.bodyText); }
    catch (e) { setError("Body must be valid JSON: " + e.message); setBusy(false); return; }
    try {
      await api.createTemplate({
        name: form.name, scope: form.scope,
        scope_ref: form.scope_ref || null,
        tenant_id: form.tenant_id ? Number(form.tenant_id) : null,
        priority: Number(form.priority), body,
      });
      onSaved();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <Modal title="New template" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="field"><label>Name</label>
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="row">
        <div className="field"><label>Scope</label>
          <select value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}>
            {SCOPES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select></div>
        <div className="field"><label>Scope ref (model/id/mac)</label>
          <input placeholder={form.scope === "global" ? "(none)" : "e.g. CCX"} value={form.scope_ref}
            onChange={(e) => setForm({ ...form, scope_ref: e.target.value })} /></div>
        <div className="field"><label>Priority</label>
          <input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} /></div>
      </div>
      <div className="field"><label>Body (JSON parameter map)</label>
        <textarea className="mono" value={form.bodyText} onChange={(e) => setForm({ ...form, bodyText: e.target.value })} /></div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.name}>Create</button>
      </div>
    </Modal>
  );
}
