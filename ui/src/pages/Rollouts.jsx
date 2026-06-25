import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

const RINGS = ["test", "pilot", "production"];

export default function Rollouts() {
  const { data, error, loading, reload } = useFetch(() => api.assignments(), []);
  const [show, setShow] = useState(false);
  const [toast, setToast] = useState(null);

  async function doRollback(id) {
    try { await api.rollback(id); reload(); setToast({ msg: `Assignment ${id} rolled back`, kind: "ok" }); }
    catch (err) { setToast({ msg: err.message, kind: "bad" }); }
  }

  return (
    <div>
      <div className="page-head">
        <div><h1>Rollout Rings</h1><div className="sub">Stage firmware through test → pilot → production with rollback</div></div>
        <button className="primary" onClick={() => setShow(true)}>New assignment</button>
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="rollouts" /> : data?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Scope</th><th>Ref</th><th>Firmware</th><th>Ring</th><th>State</th><th></th></tr></thead>
            <tbody>
              {data.map((a) => (
                <tr key={a.id}>
                  <td className="mono">{a.id}</td><td>{a.scope}</td><td className="mono">{a.scope_ref}</td>
                  <td className="mono">#{a.firmware_image_id}</td>
                  <td><span className={"badge ring-" + a.ring}>{a.ring}</span></td>
                  <td><span className={"badge " + (a.state === "rolled_back" ? "bad" : a.state === "active" ? "ok" : "")}>{a.state}</span></td>
                  <td>{a.state !== "rolled_back" &&
                    <button className="danger" onClick={() => doRollback(a.id)}>Roll back</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No rollout assignments. Assign a firmware image to a ring to begin.</Empty>}

      <div className="card" style={{ marginTop: 18 }}>
        <h2>How rings work</h2>
        <p className="muted" style={{ marginBottom: 0 }}>
          <strong>test</strong> and <strong>pilot</strong> advertise the new version immediately to their devices.
          <strong> production</strong> only advertises during its rollout window. Because phones pull firmware,
          a <strong>rollback</strong> simply stops advertising the new version — the next check-in returns the
          previous known-good image.
        </p>
      </div>

      {show && <CreateAssignment onClose={() => setShow(false)}
        onSaved={() => { setShow(false); reload(); setToast({ msg: "Assignment created", kind: "ok" }); }} />}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function CreateAssignment({ onClose, onSaved }) {
  const firmware = useFetch(() => api.firmware(), []);
  const [form, setForm] = useState({ scope: "model", scope_ref: "CCX", firmware_image_id: "", ring: "test" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true); setError(null);
    try {
      await api.createAssignment({ ...form, firmware_image_id: Number(form.firmware_image_id) });
      onSaved();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return (
    <Modal title="New rollout assignment" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="row">
        <div className="field"><label>Scope</label>
          <select value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })}>
            <option value="model">model</option><option value="group">group</option><option value="site">site</option>
          </select></div>
        <div className="field"><label>Scope ref</label>
          <input value={form.scope_ref} onChange={(e) => setForm({ ...form, scope_ref: e.target.value })} /></div>
      </div>
      <div className="field"><label>Firmware image</label>
        <select value={form.firmware_image_id} onChange={(e) => setForm({ ...form, firmware_image_id: e.target.value })}>
          <option value="">Select image…</option>
          {firmware.data?.map((f) => <option key={f.id} value={f.id}>{f.model} {f.version} (#{f.id})</option>)}
        </select></div>
      <div className="field"><label>Ring</label>
        <select value={form.ring} onChange={(e) => setForm({ ...form, ring: e.target.value })}>
          {RINGS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select></div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.firmware_image_id}>Create</button>
      </div>
    </Modal>
  );
}
