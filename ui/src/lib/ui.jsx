import React, { createContext, useContext, useEffect, useState } from "react";
import { api, clearTokens, getToken, setTokens } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) { setLoading(false); return; }
    api.me().then(setUser).catch(() => clearTokens()).finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const tokens = await api.login(email, password);
    setTokens(tokens.access_token, tokens.refresh_token);
    const me = await api.me();
    setUser(me);
    return me;
  }

  function logout() {
    clearTokens();
    setUser(null);
  }

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth() {
  return useContext(AuthCtx);
}

// ---- Small shared components ----

export function Toast({ message, kind = "ok", onDone }) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onDone, 3000);
    return () => clearTimeout(t);
  }, [message, onDone]);
  if (!message) return null;
  return <div className={`toast ${kind === "bad" ? "bad" : ""}`}>{message}</div>;
}

export function ErrorBanner({ error }) {
  if (!error) return null;
  return <div className="error-banner">{error}</div>;
}

export function Loading({ what = "data" }) {
  return <div className="loading">Loading {what}…</div>;
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

export function Modal({ title, children, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

// Async data hook used by most pages
export function useFetch(fn, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey]);

  return { data, error, loading, reload: () => setReloadKey((k) => k + 1) };
}
