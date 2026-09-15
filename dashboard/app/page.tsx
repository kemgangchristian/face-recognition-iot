"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import AppShell, {
  IconCamera,
  IconUsers,
  IconKey,
  IconCheck,
  IconClock,
  IconAlert,
  IconVideoOff,
} from "@/components/AppShell";
import {
  getStats,
  getLogs,
  getStreamUrl,
  type Stats,
  type AccessLog,
} from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [streamFailed, setStreamFailed] = useState(false);
  const [streamLoaded, setStreamLoaded] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const imgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      try {
        const [statsData, logsData] = await Promise.all([
          getStats(),
          getLogs(5),
        ]);
        if (cancelled) return;
        setStats(statsData);
        setLogs(logsData.logs);
        setError(null);
      } catch {
        if (cancelled) return;
        setError(
          "Impossible de contacter l'API. Vérifiez que le Pi est accessible."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadData();
    const id = setInterval(loadData, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (streamFailed || streamLoaded) return;
    const id = setTimeout(() => setStreamFailed(true), 6000);
    return () => clearTimeout(id);
  }, [streamFailed, streamLoaded, streamKey]);

  useEffect(() => {
    if (streamFailed || streamLoaded) return;
    const check = setInterval(() => {
      const el = imgRef.current;
      if (el && el.naturalWidth > 0 && el.naturalHeight > 0) {
        setStreamLoaded(true);
        clearInterval(check);
      }
    }, 500);
    return () => clearInterval(check);
  }, [streamFailed, streamLoaded, streamKey]);

  useEffect(() => {
    if (!streamFailed) return;
    const id = setInterval(() => {
      setStreamFailed(false);
      setStreamLoaded(false);
      setStreamKey((k) => k + 1);
    }, 10000);
    return () => clearInterval(id);
  }, [streamFailed]);

  const online = !error;

  const streamUrl = (() => {
    const base = getStreamUrl(true);
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}t=${streamKey}`;
  })();

  return (
    <AppShell active="dashboard" online={online}>
      {error && (
        <div className="alert alert-error" role="alert">
          <IconAlert />
          <span>{error}</span>
        </div>
      )}

      <section className="card stream-card">
        <div className="card-title">
          <IconCamera />
          {streamFailed
            ? "Flux caméra indisponible"
            : "Flux caméra avec détection"}
          {!streamFailed && streamLoaded && (
            <span className="live">
              <span className="live-dot" /> LIVE
            </span>
          )}
        </div>

        <div className="stream-wrap">
          <img
            ref={imgRef}
            key={streamKey}
            src={streamUrl}
            alt="Flux caméra avec détection"
            className="stream"
            style={{ visibility: streamFailed ? "hidden" : "visible" }}
            onError={() => setStreamFailed(true)}
          />

          {!streamFailed && <div className="stream-overlay" aria-hidden />}

          {streamFailed && (
            <div className="stream-placeholder" role="status">
              <span className="stream-placeholder-icon">
                <IconVideoOff />
              </span>
              <strong>Aucun signal vidéo</strong>
              <span>
                Vérifiez que la caméra et l&apos;API sont accessibles.
              </span>
            </div>
          )}
        </div>
      </section>

      <section className="stats-grid">
        <StatCard
          label="Enrôlés"
          value={stats?.enrolled_count}
          loading={loading}
          accent="violet"
          icon={<IconUsers />}
        />
        <StatCard
          label="Accès jour"
          value={stats?.accesses_today}
          loading={loading}
          accent="blue"
          icon={<IconKey />}
        />
        <StatCard
          label="Reconnus"
          value={stats?.matched_today}
          loading={loading}
          accent="green"
          icon={<IconCheck />}
        />
      </section>

      <section className="card">
        <div className="card-title">
          <IconClock /> Derniers accès
          <Link href="/logs" className="see-all">
            Tout voir
          </Link>
        </div>

        {loading && logs.length === 0 ? (
          <div className="log-list">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skeleton" />
            ))}
          </div>
        ) : logs.length === 0 ? (
          <div className="empty">Aucun accès enregistré</div>
        ) : (
          <ul className="log-list">
            {logs.map((log) => (
              <li key={log.id} className="log-row">
                <span
                  className={`avatar ${
                    log.matched ? "avatar-ok" : "avatar-no"
                  }`}
                >
                  {log.matched
                    ? (log.full_name || "?").charAt(0).toUpperCase()
                    : "?"}
                </span>
                <div className="log-info">
                  <span className={`log-name ${log.matched ? "ok" : "no"}`}>
                    {log.matched ? log.full_name : "Inconnu"}
                  </span>
                  <span className="log-sub">
                    {log.matched ? "Accès autorisé" : "Accès refusé"}
                  </span>
                </div>
                <time className="log-time">
                  {new Date(log.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="dash-footer">
        Mise à jour automatique toutes les 5 s
      </footer>
    </AppShell>
  );
}

function StatCard({
  label,
  value,
  loading,
  accent,
  icon,
}: {
  label: string;
  value?: number;
  loading: boolean;
  accent: "violet" | "blue" | "green";
  icon: React.ReactNode;
}) {
  return (
    <div className={`stat stat-${accent}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-value">
        {loading && value === undefined ? (
          <span className="skeleton-num" />
        ) : (
          value ?? 0
        )}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
