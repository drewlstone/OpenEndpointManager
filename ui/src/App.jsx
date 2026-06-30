import React, { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./lib/api";
import { Loading, useAuth } from "./lib/ui.jsx";

import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Devices from "./pages/Devices.jsx";
import DeviceDetail from "./pages/DeviceDetail.jsx";
import Tenants from "./pages/Tenants.jsx";
import Sites from "./pages/Sites.jsx";
import Groups from "./pages/Groups.jsx";
import Templates from "./pages/Templates.jsx";
import Firmware from "./pages/Firmware.jsx";
import Rollouts from "./pages/Rollouts.jsx";
import ProvLogs from "./pages/ProvLogs.jsx";
import Checkins from "./pages/Checkins.jsx";
import Discoveries from "./pages/Discoveries.jsx";
import Users from "./pages/Users.jsx";
import Health from "./pages/Health.jsx";

function FleetStrip() {
  const [stats, setStats] = useState(null);
  useEffect(() => {
    let alive = true;
    const load = () => api.dashboard().then((d) => alive && setStats(d)).catch(() => {});
    load();
    const t = setInterval(load, 15000); // refresh situational awareness
    return () => { alive = false; clearInterval(t); };
  }, []);
  if (!stats) return <div className="fleet-strip muted">fleet status…</div>;
  return (
    <div className="fleet-strip">
      <span className="fleet-stat"><span className="pip ok" /> <span className="num">{stats.recent_checkins ?? stats.online}</span> recent check-ins</span>
      <span className="fleet-stat"><span className="pip warn" /> <span className="num">{stats.stale}</span> stale</span>
      <span className="fleet-stat"><span className="pip bad" /> <span className="num">{stats.errors_last_hour}</span> errors/hr</span>
      <span className="fleet-stat muted"><span className="num">{stats.total_devices}</span> total</span>
    </div>
  );
}

const NAV = [
  { section: "Fleet" },
  { to: "/", label: "Dashboard", end: true },
  { to: "/devices", label: "Devices" },
  { to: "/discoveries", label: "Pending Approval" },
  { to: "/checkins", label: "Check-in History" },
  { to: "/logs", label: "Provisioning Logs" },
  { section: "Configuration" },
  { to: "/templates", label: "Templates" },
  { to: "/firmware", label: "Firmware Repository" },
  { to: "/rollouts", label: "Rollout Rings" },
  { section: "Organization" },
  { to: "/tenants", label: "Tenants" },
  { to: "/sites", label: "Sites" },
  { to: "/groups", label: "Groups" },
  { section: "Administration" },
  { to: "/users", label: "Users & RBAC" },
  { to: "/health", label: "System Health" },
];

function Shell({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">poly<span className="dot">·</span>prov</div>
        <nav>
          {NAV.map((item, i) =>
            item.section ? (
              <div key={i} className="nav-section">{item.section}</div>
            ) : (
              <NavLink key={item.to} to={item.to} end={item.end}
                className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}>
                {item.label}
              </NavLink>
            )
          )}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <FleetStrip />
          <div className="userbox">
            <span>{user?.kind === "user" ? user?.id && `user #${user.id}` : user?.kind}</span>
            <button className="ghost" onClick={() => { logout(); nav("/login"); }}>Sign out</button>
          </div>
        </header>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="login-wrap"><Loading what="session" /></div>;

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Shell>
      <Routes>
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="/" element={<Dashboard />} />
        <Route path="/devices" element={<Devices />} />
        <Route path="/devices/:mac" element={<DeviceDetail />} />
        <Route path="/discoveries" element={<Discoveries />} />
        <Route path="/checkins" element={<Checkins />} />
        <Route path="/logs" element={<ProvLogs />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/firmware" element={<Firmware />} />
        <Route path="/rollouts" element={<Rollouts />} />
        <Route path="/tenants" element={<Tenants />} />
        <Route path="/sites" element={<Sites />} />
        <Route path="/groups" element={<Groups />} />
        <Route path="/users" element={<Users />} />
        <Route path="/health" element={<Health />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
