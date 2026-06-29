import React, { useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading, Modal, Toast, useFetch } from "../lib/ui.jsx";

function formatTime(value) {
  return value ? value.replace("T", " ").slice(0, 19) : "-";
}

export default function Discoveries() {
  const [mac, setMac] = useState("");
  const [approving, setApproving] = useState(null);
  const [toast, setToast] = useState(null);
  const q = new URLSearchParams({ limit: "200", status: "pending" });
  const { data, error, loading, reload } = useFetch(() => api.discoveries(`?${q}`), []);
  const needle = mac.replace(/[:-]/g, "").toLowerCase();
  const rows = needle ? (data || []).filter((d) => d.mac.includes(needle)) : data;

  return (
    <div>
      <div className="page-head">
        <div><h1>Pending Approval</h1><div className="sub">Unknown Poly endpoints discovered from MAC-scoped provisioning requests</div></div>
      </div>
      <div className="toolbar">
        <input placeholder="Filter by MAC" value={mac} onChange={(e) => setMac(e.target.value)} />
      </div>
      <ErrorBanner error={error} />
      {loading ? <Loading what="discoveries" /> : rows?.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Last Seen</th><th>MAC</th><th>Model</th><th>Firmware</th>
                <th>Endpoint IP</th><th>Proxy IP</th><th>Requests</th><th>Last Path</th><th>Status</th><th>User Agent</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id}>
                  <td className="mono muted">{formatTime(d.last_seen_at)}</td>
                  <td className="mono">{d.mac}</td>
                  <td className="mono">{d.model || "-"}</td>
                  <td className="mono muted">{d.firmware_version || "-"}</td>
                  <td className="mono">{d.endpoint_ip || "-"}</td>
                  <td className="mono muted">{d.proxy_ip || "-"}</td>
                  <td className="mono">{d.request_count}</td>
                  <td className="mono">{d.last_path}</td>
                  <td><span className={"badge " + (d.last_status >= 400 ? "bad" : "ok")}>{d.last_status}</span></td>
                  <td className="muted">{d.user_agent || "-"}</td>
                  <td><button className="primary" onClick={() => setApproving(d)}>Approve</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Empty>No pending discoveries. Unknown Poly devices will appear here after a valid MAC-scoped provisioning request.</Empty>}

      {approving && (
        <ApproveDiscovery
          discovery={approving}
          onClose={() => setApproving(null)}
          onSaved={() => {
            setApproving(null);
            reload();
            setToast({ msg: "Device approved", kind: "ok" });
          }}
        />
      )}
      <Toast message={toast?.msg} kind={toast?.kind} onDone={() => setToast(null)} />
    </div>
  );
}

function ApproveDiscovery({ discovery, onClose, onSaved }) {
  const tenants = useFetch(() => api.tenants(), []);
  const [form, setForm] = useState({
    tenant_id: "",
    site_id: "",
    primary_group_id: "",
    config_profile_id: "",
    model: discovery.model || "CCX",
    serial: discovery.serial || "",
    label: "",
  });
  const tenantQuery = form.tenant_id ? `?tenant_id=${encodeURIComponent(form.tenant_id)}` : "";
  const sites = useFetch(() => form.tenant_id ? api.sites(tenantQuery) : Promise.resolve([]), [form.tenant_id]);
  const groups = useFetch(() => form.tenant_id ? api.groups(tenantQuery) : Promise.resolve([]), [form.tenant_id]);
  const templates = useFetch(() => api.templates(), []);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function update(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function selectTenant(value) {
    setForm((current) => ({
      ...current, tenant_id: value, site_id: "", primary_group_id: "", config_profile_id: "",
    }));
  }

  async function approve() {
    setBusy(true); setError(null);
    try {
      await api.approveDiscovery(discovery.id, {
        tenant_id: Number(form.tenant_id),
        site_id: Number(form.site_id),
        primary_group_id: form.primary_group_id ? Number(form.primary_group_id) : null,
        config_profile_id: form.config_profile_id ? Number(form.config_profile_id) : null,
        model: form.model || null,
        serial: form.serial || null,
        label: form.label || null,
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const filteredTemplates = (templates.data || []).filter((tpl) => {
    if (!form.tenant_id) return tpl.scope === "global";
    return tpl.scope === "global" || tpl.scope === "tenant" || tpl.scope === "site" || tpl.scope === "group" || tpl.scope === "mac" || tpl.scope === "model";
  });

  return (
    <Modal title={`Approve ${discovery.mac}`} onClose={onClose}>
      <ErrorBanner error={error || tenants.error || sites.error || groups.error || templates.error} />
      <dl className="kv" style={{ marginBottom: 18 }}>
        <dt>MAC</dt><dd>{discovery.mac}</dd>
        <dt>Endpoint IP</dt><dd>{discovery.endpoint_ip || "-"}</dd>
        <dt>Proxy IP</dt><dd>{discovery.proxy_ip || "-"}</dd>
        <dt>Firmware</dt><dd>{discovery.firmware_version || "-"}</dd>
        <dt>Last seen</dt><dd>{formatTime(discovery.last_seen_at)}</dd>
      </dl>

      <div className="field">
        <label>Tenant</label>
        <select value={form.tenant_id} onChange={(e) => selectTenant(e.target.value)}>
          <option value="">Select tenant...</option>
          {tenants.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Site</label>
        <select value={form.site_id} onChange={(e) => update({ site_id: e.target.value })} disabled={!form.tenant_id || sites.loading}>
          <option value="">Select site...</option>
          {sites.data?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      <div className="row">
        <div className="field">
          <label>Group</label>
          <select value={form.primary_group_id} onChange={(e) => update({ primary_group_id: e.target.value })} disabled={!form.tenant_id || groups.loading}>
            <option value="">No group</option>
            {groups.data?.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Template/Profile</label>
          <select value={form.config_profile_id} onChange={(e) => update({ config_profile_id: e.target.value })} disabled={templates.loading}>
            <option value="">No explicit profile</option>
            {filteredTemplates.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.scope})</option>)}
          </select>
        </div>
      </div>
      <div className="row">
        <div className="field"><label>Model</label>
          <input value={form.model} onChange={(e) => update({ model: e.target.value })} /></div>
        <div className="field"><label>Serial</label>
          <input value={form.serial} onChange={(e) => update({ serial: e.target.value })} /></div>
      </div>
      <div className="field"><label>Friendly Name</label>
        <input value={form.label} onChange={(e) => update({ label: e.target.value })} /></div>
      <div className="modal-actions">
        <button className="ghost" onClick={onClose}>Cancel</button>
        <button className="primary" onClick={approve} disabled={busy || !form.tenant_id || !form.site_id}>Approve</button>
      </div>
    </Modal>
  );
}
