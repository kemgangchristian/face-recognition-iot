"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getStats, logout } from "@/lib/api";
import ThemeToggle from "./ThemeToggle";

type NavKey = "dashboard" | "enroll" | "identities" | "logs";

export default function AppShell({
  active,
  children,
  online,
}: {
  active: NavKey;
  children: React.ReactNode;
  online?: boolean;
}) {
  const [apiOnline, setApiOnline] = useState(true);
  const [loggingOut, setLoggingOut] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (online !== undefined) return;
    let cancelled = false;
    async function ping() {
      try {
        await getStats();
        if (!cancelled) setApiOnline(true);
      } catch {
        if (!cancelled) setApiOnline(false);
      }
    }
    ping();
    const id = setInterval(ping, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [online]);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
    } catch {
      // même si le backend échoue, on redirige
    } finally {
      router.push("/login");
      router.refresh();
    }
  }

  const isOnline = online ?? apiOnline;

  return (
    <main className="dash">
      <style>{styles}</style>

      <header className="dash-header">
        <div className="dash-brand">
          <span className={`dot ${isOnline ? "dot-on" : "dot-off"}`} />
          <h1>Contrôle d&apos;accès</h1>
        </div>

        <div className="header-actions">
          <ThemeToggle />
          <span className={`pill ${isOnline ? "pill-on" : "pill-off"}`}>
            {isOnline ? "API en ligne" : "API hors ligne"}
          </span>
          <button
            type="button"
            onClick={handleLogout}
            disabled={loggingOut}
            className="logout-btn"
            aria-label="Se déconnecter"
            title="Se déconnecter"
          >
            {loggingOut ? <span className="spinner-dark" /> : <IconLogout />}
          </button>
        </div>
      </header>

      <nav className="dash-nav">
        <Link
          href="/"
          className={`nav-item ${active === "dashboard" ? "nav-active" : ""}`}
        >
          <IconGrid /> Dashboard
        </Link>
        <Link
          href="/enroll"
          className={`nav-item ${active === "enroll" ? "nav-active" : ""}`}
        >
          <IconUserPlus /> Enrôler
        </Link>
        <Link
          href="/identities"
          className={`nav-item ${active === "identities" ? "nav-active" : ""}`}
        >
          <IconUsers /> Identités
        </Link>
        <Link
          href="/logs"
          className={`nav-item ${active === "logs" ? "nav-active" : ""}`}
        >
          <IconList /> Journal
        </Link>
      </nav>

      {children}
    </main>
  );
}

/* ---------- Icônes ---------- */

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export const IconGrid = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </svg>
);
export const IconUserPlus = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
    <path d="M19 8v6M16 11h6" />
  </svg>
);
export const IconUsers = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
    <path d="M16 4.5a3.5 3.5 0 0 1 0 7" />
    <path d="M17 14.2c2.3.5 4 2.5 4 5.8" />
  </svg>
);
export const IconList = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <path d="M8 6h13M8 12h13M8 18h13" />
    <circle cx="3.5" cy="6" r="1" />
    <circle cx="3.5" cy="12" r="1" />
    <circle cx="3.5" cy="18" r="1" />
  </svg>
);
export const IconCamera = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <path d="M3 8.5A2.5 2.5 0 0 1 5.5 6h9A2.5 2.5 0 0 1 17 8.5v7A2.5 2.5 0 0 1 14.5 18h-9A2.5 2.5 0 0 1 3 15.5z" />
    <path d="M17 10l4-2v8l-4-2" />
  </svg>
);
export const IconVideoOff = () => (
  <svg viewBox="0 0 24 24" width="28" height="28" {...stroke}>
    <path d="M3 8.5A2.5 2.5 0 0 1 5.5 6h9A2.5 2.5 0 0 1 17 8.5v7A2.5 2.5 0 0 1 14.5 18h-9A2.5 2.5 0 0 1 3 15.5z" />
    <path d="M17 10l4-2v8l-4-2" />
    <path d="M3 3l18 18" />
  </svg>
);
export const IconClock = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
export const IconAlert = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" {...stroke}>
    <path d="M12 3 2 20h20z" />
    <path d="M12 10v4M12 17.5v.01" />
  </svg>
);
export const IconKey = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <circle cx="8" cy="15" r="4" />
    <path d="m10.8 12.2 8.2-8.2M15 6l3 3M17 4l3 3" />
  </svg>
);
export const IconCheck = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <path d="m4 12.5 5 5L20 6.5" />
  </svg>
);
export const IconTrash = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14" />
    <path d="M10 11v6M14 11v6" />
  </svg>
);
export const IconLogout = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5" />
    <path d="M21 12H9" />
  </svg>
);

/* ---------- Styles ---------- */

const styles = `
  .dash {
    max-width: 720px;
    margin: 0 auto;
    padding: 20px 16px 40px;
    color: var(--foreground);
    background: var(--background);
    min-height: 100vh;
    font-family: var(--font-sans), ui-sans-serif, system-ui, -apple-system,
      "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .dash * { box-sizing: border-box; }

  .page-title {
    font-size: 20px;
    font-weight: 650;
    margin: 0 0 16px;
    letter-spacing: -0.01em;
  }

  .dash-header {
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px; margin-bottom: 16px; flex-wrap: wrap;
  }
  .dash-brand { display: flex; align-items: center; gap: 10px; }
  .dash-brand h1 {
    font-size: 18px; font-weight: 650; margin: 0;
    letter-spacing: -0.01em;
  }
  .header-actions { display: flex; align-items: center; gap: 8px; }

  .dot {
    width: 10px; height: 10px; border-radius: 50%;
    box-shadow: 0 0 0 4px rgba(127,127,127,0.08);
  }
  .dot-on { background: var(--green); box-shadow: 0 0 12px var(--green); }
  .dot-off { background: var(--red); box-shadow: 0 0 12px var(--red); }

  .logout-btn {
    display: inline-flex; align-items: center; justify-content: center;
    width: 34px; height: 34px;
    border-radius: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--muted);
    cursor: pointer;
    transition: background .15s ease, color .15s ease,
                border-color .15s ease, transform .1s ease;
  }
  .logout-btn:hover:not(:disabled) {
    color: var(--red);
    background: color-mix(in srgb, var(--red) 10%, transparent);
    border-color: color-mix(in srgb, var(--red) 35%, transparent);
  }
  .logout-btn:active:not(:disabled) { transform: scale(.94); }
  .logout-btn:disabled { opacity: .55; cursor: not-allowed; }
  .logout-btn:focus-visible {
    outline: 2px solid var(--violet);
    outline-offset: 2px;
  }

  .spinner-dark {
    width: 14px; height: 14px;
    border-radius: 50%;
    border: 2px solid color-mix(in srgb, var(--muted) 40%, transparent);
    border-top-color: var(--muted);
    animation: spin .8s linear infinite;
  }

  .pill {
    font-size: 12px; font-weight: 600;
    padding: 6px 10px; border-radius: 999px;
    border: 1px solid var(--border);
  }
  .pill-on {
    color: var(--green);
    background: color-mix(in srgb, var(--green) 12%, transparent);
    border-color: color-mix(in srgb, var(--green) 35%, transparent);
  }
  .pill-off {
    color: var(--red);
    background: color-mix(in srgb, var(--red) 12%, transparent);
    border-color: color-mix(in srgb, var(--red) 35%, transparent);
  }

  .dash-nav {
    display: flex; gap: 6px; margin-bottom: 18px;
    overflow-x: auto; padding: 4px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px;
    scrollbar-width: none;
  }
  .dash-nav::-webkit-scrollbar { display: none; }
  .nav-item {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 9px 14px; border-radius: 10px;
    font-size: 13.5px; color: var(--muted); text-decoration: none;
    white-space: nowrap; transition: background .15s ease, color .15s ease;
  }
  .nav-item:hover { color: var(--foreground); background: var(--surface-2); }
  .nav-active {
    color: var(--foreground);
    background: color-mix(in srgb, var(--violet) 15%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--violet) 40%, transparent);
  }

  .alert {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 14px; margin-bottom: 16px;
    border-radius: 12px; font-size: 13.5px; font-weight: 500;
    border: 1px solid transparent;
  }
  .alert-error {
    background: color-mix(in srgb, var(--red) 10%, transparent);
    border-color: color-mix(in srgb, var(--red) 35%, transparent);
    color: var(--red);
  }
  .alert-success {
    background: color-mix(in srgb, var(--green) 10%, transparent);
    border-color: color-mix(in srgb, var(--green) 35%, transparent);
    color: var(--green);
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 14px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-card);
  }
  .card-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 13.5px; font-weight: 600;
    color: var(--foreground); margin-bottom: 12px;
  }
  .card-title svg { color: var(--muted); }
  .see-all {
    margin-left: auto; font-size: 12px; color: var(--violet);
    text-decoration: none; font-weight: 600;
  }
  .see-all:hover { text-decoration: underline; }

  .live {
    margin-left: auto;
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 10.5px; font-weight: 700; letter-spacing: .08em;
    color: var(--red);
    background: color-mix(in srgb, var(--red) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--red) 35%, transparent);
    padding: 3px 8px; border-radius: 999px;
  }
  .live-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--red); box-shadow: 0 0 8px var(--red);
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .35 } }

  .stream-wrap {
    position: relative;
    border-radius: 12px;
    overflow: hidden;
    background: var(--surface-2);
    border: 1px solid var(--border);
    aspect-ratio: 16 / 10;
    display: flex; align-items: center; justify-content: center;
  }
  .stream { width: 100%; height: 100%; object-fit: cover; display: block; }
  .stream-overlay {
    position: absolute; inset: 0; pointer-events: none;
    background: radial-gradient(120% 80% at 50% 0%, transparent 50%, rgba(0,0,0,.35));
  }
  .stream-placeholder {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 14px;
    color: var(--muted);
    font-size: 12.5px;
    text-align: center;
    padding: 20px;
    background:
      radial-gradient(ellipse 60% 70% at 50% 50%,
        color-mix(in srgb, var(--surface-2) 90%, transparent),
        color-mix(in srgb, var(--surface) 100%, transparent) 75%),
      repeating-linear-gradient(
        45deg,
        transparent 0 12px,
        color-mix(in srgb, var(--border) 35%, transparent) 12px 13px
      );
  }
  .stream-placeholder-icon {
    width: 72px; height: 72px;
    border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    color: var(--muted);
    background: color-mix(in srgb, var(--muted) 10%, transparent);
    box-shadow:
      inset 0 0 0 1px color-mix(in srgb, var(--border) 80%, transparent),
      0 4px 16px rgba(0,0,0,.08);
  }
  .stream-placeholder strong {
    color: var(--foreground);
    font-weight: 600;
    font-size: 14px;
    margin-top: 2px;
  }
  .stream-placeholder span:last-child {
    max-width: 260px;
    line-height: 1.5;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px; margin-bottom: 16px;
  }
  .stat {
    position: relative; overflow: hidden;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 12px;
    display: flex; flex-direction: column; gap: 6px;
    transition: transform .15s ease, border-color .15s ease;
  }
  .stat:hover { transform: translateY(-2px); }
  .stat-violet { border-color: color-mix(in srgb, var(--violet) 35%, var(--border)); }
  .stat-blue   { border-color: color-mix(in srgb, var(--blue)   35%, var(--border)); }
  .stat-green  { border-color: color-mix(in srgb, var(--green)  35%, var(--border)); }
  .stat-violet .stat-icon { color: var(--violet); background: color-mix(in srgb, var(--violet) 15%, transparent); }
  .stat-blue   .stat-icon { color: var(--blue);   background: color-mix(in srgb, var(--blue)   15%, transparent); }
  .stat-green  .stat-icon { color: var(--green);  background: color-mix(in srgb, var(--green)  15%, transparent); }
  .stat-icon {
    width: 28px; height: 28px; border-radius: 8px;
    display: inline-flex; align-items: center; justify-content: center;
  }
  .stat-value {
    font-size: 22px; font-weight: 700; line-height: 1;
    letter-spacing: -0.02em;
  }
  .stat-label {
    font-size: 11.5px; color: var(--muted); font-weight: 500;
    text-transform: uppercase; letter-spacing: .06em;
  }

  .skeleton-num {
    display: inline-block; width: 32px; height: 20px; border-radius: 6px;
    background: linear-gradient(90deg,
      var(--skeleton-base), var(--skeleton-highlight), var(--skeleton-base));
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  .skeleton {
    height: 52px; border-radius: 10px;
    background: linear-gradient(90deg,
      var(--skeleton-base), var(--skeleton-highlight), var(--skeleton-base));
    background-size: 200% 100%;
    animation: shimmer 1.4s ease-in-out infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0 }
    100% { background-position: -200% 0 }
  }

  .log-list {
    list-style: none; padding: 0; margin: 0;
    display: flex; flex-direction: column; gap: 6px;
  }
  .log-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 12px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 12px;
    transition: background .15s ease, border-color .15s ease;
  }
  .log-row:hover { border-color: var(--border-hover); }
  .avatar {
    width: 34px; height: 34px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; flex-shrink: 0;
  }
  .avatar-ok {
    background: color-mix(in srgb, var(--green) 18%, transparent);
    color: var(--green);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--green) 40%, transparent);
  }
  .avatar-no {
    background: color-mix(in srgb, var(--red) 18%, transparent);
    color: var(--red);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--red) 40%, transparent);
  }
  .log-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
  .log-name {
    font-size: 13.5px; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .log-name.ok { color: var(--green); }
  .log-name.no { color: var(--red); }
  .log-sub { font-size: 11.5px; color: var(--muted); }
  .log-time {
    font-size: 12px; color: var(--muted);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .empty {
    padding: 24px; text-align: center; color: var(--muted); font-size: 13px;
  }

  .field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .field-label {
    font-size: 12px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: .06em;
  }
  .input {
    width: 100%;
    padding: 11px 13px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--foreground);
    font-size: 14px;
    font-family: inherit;
    outline: none;
    transition: border-color .15s ease, background .15s ease, box-shadow .15s ease;
  }
  .input::placeholder { color: var(--muted); opacity: .7; }
  .input:focus {
    border-color: var(--violet);
    background: var(--surface);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--violet) 20%, transparent);
  }
  .input:disabled { opacity: .6; cursor: not-allowed; }

  .btn {
    width: 100%;
    padding: 12px 16px;
    border-radius: 10px;
    border: 1px solid transparent;
    font-size: 14px; font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    transition: transform .1s ease, filter .15s ease, opacity .15s ease;
  }
  .btn:active:not(:disabled) { transform: scale(.98); }
  .btn:focus-visible {
    outline: 2px solid var(--violet);
    outline-offset: 2px;
  }
  .btn:disabled { opacity: .55; cursor: not-allowed; }
  .btn-primary {
    color: #fff;
    background: linear-gradient(180deg,
      color-mix(in srgb, var(--violet) 92%, #fff),
      var(--violet));
    box-shadow: 0 2px 8px color-mix(in srgb, var(--violet) 35%, transparent);
  }
  .btn-primary:hover:not(:disabled) { filter: brightness(1.08); }
  .btn-danger {
    width: auto;
    padding: 8px 10px;
    border-radius: 8px;
    color: var(--red);
    background: color-mix(in srgb, var(--red) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--red) 30%, transparent);
  }
  .btn-danger:hover:not(:disabled) {
    background: color-mix(in srgb, var(--red) 18%, transparent);
  }

  .spinner {
    width: 14px; height: 14px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,.35);
    border-top-color: #fff;
    animation: spin .8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg) } }

  .filters {
    display: flex; gap: 6px;
    margin-bottom: 16px;
    overflow-x: auto;
    padding-bottom: 2px;
    scrollbar-width: none;
  }
  .filters::-webkit-scrollbar { display: none; }
  .filter {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 12px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    font-size: 12.5px; font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    transition: background .15s ease, color .15s ease, border-color .15s ease;
  }
  .filter:hover {
    color: var(--foreground);
    border-color: var(--border-hover);
  }
  .filter-active {
    color: var(--foreground);
    background: color-mix(in srgb, var(--violet) 15%, transparent);
    border-color: color-mix(in srgb, var(--violet) 40%, transparent);
  }

  .dash-footer {
    margin-top: 24px; text-align: center;
    font-size: 11.5px; color: var(--muted);
  }

  @media (max-width: 480px) {
    .dash { padding: 16px 12px 32px; }
    .dash-brand h1 { font-size: 16px; }
    .page-title { font-size: 17px; }
    .stat-value { font-size: 19px; }
    .stat { padding: 10px; }
    .card { padding: 12px; border-radius: 14px; }
    .nav-item { padding: 8px 11px; font-size: 12.5px; }
    .log-time { font-size: 11.5px; }
    .stream-placeholder-icon { width: 60px; height: 60px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .live-dot, .skeleton, .skeleton-num, .spinner, .spinner-dark { animation: none; }
    .stat, .log-row, .nav-item, .btn, .logout-btn { transition: none; }
  }
`;
