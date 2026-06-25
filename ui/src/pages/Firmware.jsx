import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

export default function Firmware() {
  const { data, error, loading, reload } = useFetch(() => api.firmware(), []);
  const [show, setShow] = useState(false);
  const [toast, setToast] = useState(null);

  return (
    <div>
      <div className="page-head">
        <div><h1>Firmware Repository</h1><div className="sub">Registered images available for rollout assignment</div></div>
        <button className="primary" onClick={() => setShow(true)}>Register firmware</button>
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="firmware" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Model</th><th>Version</th><th>SHA-256</th><th>Size</th></tr></thead>
            <tbody>
              {data.map((f) => (
                <tr key={f.id}>
                  <td className="mono">{f.id}</td><td className="mono">{f.model}</td>
                  <td className="mono">{f.version}</td>
                  <td className="mono muted">{f.sha256.slice(0, 16)}…</td>
                  <td className="mono">{f.size_bytes ? `${(f.size_bytes / 1e6).toFixed(1)} MB` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No firmware registered. Upload a binary to your object store, then register its metadata here.</Empty>}

      {show && <RegisterFirmware onClose={() => setShow(false)}
        onSaved={() => { setShow(false); reload(); setToast({ msg: "Firmware registered", kind: "ok" }); }} />}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function RegisterFirmware({ onClose, onSaved }) {
  const [form, setForm] = useState({ model: "CCX", version: "", object_key: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true); setError(null);
    try { await api.registerFirmware(form.model, form.version, form.object_key); onSaved(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return (
    <Modal title="Register firmware" onClose={onClose}>
      <ErrorBanner error={error} />
      <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>
        Upload the binary to object storage out-of-band, then record its key here.
      </p>
      <div className="row">
        <div className="field"><label>Model</label>
          <input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></div>
        <div className="field"><label>Version</label>
          <input placeholder="8.1.2" value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} /></div>
      </div>
      <div className="field"><label>Object key / path</label>
        <input placeholder="ccx/8.1.2/sip.ld" value={form.object_key} onChange={(e) => setForm({ ...form, object_key: e.target.value })} /></div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.version || !form.object_key}>Register</button>
      </div>
    </Modal>
  );
}
