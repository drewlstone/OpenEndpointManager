import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

export default function Users() {
  const users = useFetch(() => api.users(), []);
  const roles = useFetch(() => api.roles(), []);
  const [show, setShow] = useState(false);
  const [toast, setToast] = useState(null);

  return (
    <div>
      <div className="page-head">
        <div><h1>Users &amp; RBAC</h1><div className="sub">Admin accounts, roles, and permissions</div></div>
        <button className="primary" onClick={() => setShow(true)}>New user</button>
      </div>

      <div className="card">
        <h2>Users</h2>
        <ErrorBanner error={users.error} />
        {users.loading ? <Loading what="users" /> : users.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Email</th><th>Tenant</th><th>Roles</th><th>Active</th></tr></thead>
              <tbody>
                {users.data.map((u) => (
                  <tr key={u.id}>
                    <td className="mono">{u.id}</td><td>{u.email}</td>
                    <td className="mono">{u.tenant_id ?? "all"}</td>
                    <td>{u.roles.map((r) => <span key={r} className="badge" style={{ marginRight: 4 }}>{r}</span>)}</td>
                    <td>{u.is_active ? <span className="badge ok">active</span> : <span className="badge bad">disabled</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No users.</Empty>}
      </div>

      <div className="card">
        <h2>Roles &amp; permissions</h2>
        {roles.loading ? <Loading what="roles" /> : roles.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>ID</th><th>Role</th><th>Permissions</th></tr></thead>
              <tbody>
                {roles.data.map((r) => (
                  <tr key={r.id}>
                    <td className="mono">{r.id}</td><td><span className="badge info">{r.name}</span></td>
                    <td className="mono muted">{r.permissions.join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>No roles defined.</Empty>}
      </div>

      {show && <CreateUser roles={roles.data || []} onClose={() => setShow(false)}
        onSaved={() => { setShow(false); users.reload(); setToast({ msg: "User created", kind: "ok" }); }} />}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function CreateUser({ roles, onClose, onSaved }) {
  const tenants = useFetch(() => api.tenants(), []);
  const [form, setForm] = useState({ email: "", password: "", tenant_id: "", role_ids: [] });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function toggleRole(id) {
    setForm((f) => ({
      ...f,
      role_ids: f.role_ids.includes(id) ? f.role_ids.filter((r) => r !== id) : [...f.role_ids, id],
    }));
  }

  async function save() {
    setBusy(true); setError(null);
    try {
      await api.createUser({
        email: form.email, password: form.password,
        tenant_id: form.tenant_id ? Number(form.tenant_id) : null,
        role_ids: form.role_ids,
      });
      onSaved();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <Modal title="New user" onClose={onClose}>
      <ErrorBanner error={error} />
      <div className="field"><label>Email</label>
        <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
      <div className="field"><label>Password</label>
        <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
      <div className="field"><label>Tenant (blank = all tenants)</label>
        <select value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}>
          <option value="">All tenants</option>
          {tenants.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select></div>
      <div className="field"><label>Roles</label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {roles.map((r) => (
            <label key={r.id} style={{ display: "flex", alignItems: "center", gap: 6, margin: 0, fontSize: 13 }}>
              <input type="checkbox" style={{ width: "auto" }} checked={form.role_ids.includes(r.id)} onChange={() => toggleRole(r.id)} />
              {r.name}
            </label>
          ))}
        </div></div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={busy || !form.email || !form.password}>Create</button>
      </div>
    </Modal>
  );
}
