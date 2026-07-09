import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Empty, ErrorBanner, Loading } from "../lib/ui.jsx";

// The /metrics and /healthz endpoints live at the app root, not under /api/v1.
async function fetchText(path) {
  const res = await fetch(path);
  return { ok: res.ok, status: res.status, text: await res.text() };
}

function parseProm(text, name) {
  // sum all samples for a metric family (ignoring labels) - good enough for a
  // lightweight ops view; Grafana is the real dashboard.
  let total = 0;
  let found = false;
  for (const line of text.split("\n")) {
    if (line.startsWith("#") || !line.trim()) continue;
    const sp = line.lastIndexOf(" ");
    const key = line.slice(0, sp);
    const val = parseFloat(line.slice(sp + 1));
    if (key.startsWith(name)) { total += isNaN(val) ? 0 : val; found = true; }
  }
  return found ? total : null;
}

function formatTime(value) {
  return value ? value.replace("T", " ").slice(0, 19) : "-";
}

function formatSeconds(value) {
  return value === null || value === undefined ? "-" : `${value}s`;
}

function StatusBadge({ status, children }) {
  return <span className={`badge ${status}`}><span className={`pip ${status}`} />{children}</span>;
}

function connectionBadge(connected) {
  return connected
    ? <StatusBadge status="ok">Connected</StatusBadge>
    : <StatusBadge status="bad">Disconnected</StatusBadge>;
}

function enabledBadge(enabled) {
  if (enabled === true) return <StatusBadge status="ok">Enabled</StatusBadge>;
  if (enabled === false) return <StatusBadge status="warn">Disabled</StatusBadge>;
  return <StatusBadge status="bad">Unknown</StatusBadge>;
}

function schedulerBadge(engine) {
  if (!engine) return <StatusBadge status="bad">Unknown</StatusBadge>;
  if (!engine.health_probe_scheduler_enabled) return <StatusBadge status="warn">Stopped</StatusBadge>;
  return engine.beat_connected
    ? <StatusBadge status="ok">Running</StatusBadge>
    : <StatusBadge status="bad">Stopped</StatusBadge>;
}

export default function Health() {
  const [health, setHealth] = useState(null);
  const [ready, setReady] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [engine, setEngine] = useState(null);
  const [engineError, setEngineError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const [h, r, m, e] = await Promise.all([
          fetchText("/healthz").catch(() => ({ ok: false })),
          fetchText("/readyz").catch(() => ({ ok: false })),
          fetchText("/metrics").catch(() => ({ ok: false, text: "" })),
          api.healthEngine().then((data) => ({ data })).catch((err) => ({ error: err.message })),
        ]);
        if (!alive) return;
        setHealth(h); setReady(r); setMetrics(m.text || "");
        setEngine(e.data || null); setEngineError(e.error || null);
      } finally { if (alive) setLoading(false); }
    }
    load();
    const t = setInterval(load, 10000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (loading) return <Loading what="health" />;

  const hits = metrics != null ? parseProm(metrics, "polyprov_cache_hits_total") : null;
  const misses = metrics != null ? parseProm(metrics, "polyprov_cache_misses_total") : null;
  const checkins = metrics != null ? parseProm(metrics, "polyprov_checkins_total") : null;
  const hitRatio = hits != null && misses != null && hits + misses > 0
    ? ((hits / (hits + misses)) * 100).toFixed(1) + "%" : "-";

  return (
    <div>
      <div className="page-head">
        <div><h1>System Health</h1><div className="sub">Liveness, readiness, and live metrics (auto-refresh 10s)</div></div>
      </div>

      <div className="tiles">
        <div className="tile"><div className="label">Liveness</div>
          <div className={"value " + (health?.ok ? "ok" : "bad")}>{health?.ok ? "OK" : "DOWN"}</div></div>
        <div className="tile"><div className="label">Readiness</div>
          <div className={"value " + (ready?.ok ? "ok" : "bad")}>{ready?.ok ? "READY" : "NOT READY"}</div></div>
        <div className="tile"><div className="label">Cache hit ratio</div><div className="value">{hitRatio}</div></div>
        <div className="tile"><div className="label">Cache hits</div><div className="value">{hits ?? "-"}</div></div>
        <div className="tile"><div className="label">Cache misses</div><div className="value">{misses ?? "-"}</div></div>
        <div className="tile"><div className="label">Check-ins</div><div className="value">{checkins ?? "-"}</div></div>
      </div>

      <div className="card">
        <h2>Health Engine</h2>
        <ErrorBanner error={engineError} />
        <dl className="kv">
          <dt>Scheduler</dt><dd>{schedulerBadge(engine)}</dd>
          <dt>Worker</dt><dd>{engine ? connectionBadge(engine.worker_connected) : <StatusBadge status="bad">Unknown</StatusBadge>}</dd>
          <dt>Redis</dt><dd>{engine ? connectionBadge(engine.redis_connected) : <StatusBadge status="bad">Unknown</StatusBadge>}</dd>
          <dt>ICMP</dt><dd>{enabledBadge(engine?.health_probe_icmp_enabled)}</dd>
          <dt>TCP</dt><dd><StatusBadge status="ok">Enabled</StatusBadge></dd>
          <dt>Web UI</dt><dd><StatusBadge status="ok">Enabled</StatusBadge></dd>
          <dt>Probe Interval</dt><dd>{formatSeconds(engine?.health_probe_interval_seconds)}</dd>
          <dt>Batch Size</dt><dd>{engine?.health_probe_batch_size ?? "-"}</dd>
          <dt>Concurrency</dt><dd>{engine?.health_probe_concurrency ?? "-"}</dd>
          <dt>Last Scheduler Run</dt><dd>{formatTime(engine?.scheduler_last_run)}</dd>
          <dt>Next Scheduler Run</dt><dd>{formatTime(engine?.scheduler_next_run)}</dd>
          <dt>Worker Hosts</dt><dd>{engine?.worker_hostnames?.length ? engine.worker_hostnames.join(", ") : "-"}</dd>
          <dt>Celery Version</dt><dd>{engine?.celery_worker_version || "-"}</dd>
        </dl>
      </div>

      <div className="card">
        <h2>Readiness detail</h2>
        <div className="mono muted">{ready?.text || "(no detail - endpoint may require the provisioning/admin plane to be up)"}</div>
      </div>

      <div className="card">
        <h2>Raw metrics</h2>
        {metrics ? (
          <textarea className="mono" readOnly style={{ minHeight: 280 }}
            value={metrics.split("\n").filter((l) => l.startsWith("polyprov_") && !l.startsWith("#")).join("\n") || metrics.slice(0, 4000)} />
        ) : <Empty>Metrics endpoint unavailable. Grafana provides the full dashboard (see deploy/grafana-dashboard.json).</Empty>}
      </div>
    </div>
  );
}
