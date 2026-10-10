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
  getHealth,
  getLiveAccess,
  getStreamUrl,
  type Stats,
  type AccessLog,
  type Health,
  type LiveAccess,
  type LiveState,
} from "@/lib/api";

const POLL_MS = 2000;
const LIVE_MS = 700;

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [live, setLive] = useState<LiveAccess | null>(null);
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
        const [statsData, logsData, healthData] = await Promise.all([
          getStats(),
          getLogs(8),
          getHealth().catch(() => null),
        ]);
        if (cancelled) return;
        setStats(statsData);
        setLogs(logsData.logs);
        if (healthData) setHealth(healthData);
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
    const id = setInterval(loadData, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function loadLive() {
      try {
        const data = await getLiveAccess();
        if (cancelled) return;
        setLive(data);
      } catch {
        if (!cancelled) setLive(null);
      }
    }
    loadLive();
    const id = setInterval(loadLive, LIVE_MS);
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
  const door: LiveState = live?.state ?? "idle";
  const streamUrl = `${getStreamUrl(true)}?t=${streamKey}`;

  let doorLabel: string;
  let doorName: string;
  let doorMeta: string;
  switch (door) {
    case "granted":
      doorLabel = "Accès autorisé";
      doorName = live?.name || "Identité reconnue";
      doorMeta =
        typeof live?.confidence === "number"
          ? `Score ${live.confidence.toFixed(2)}`
          : "";
      break;
    case "denied":
      doorLabel = "Accès refusé";
      doorName = "Inconnu";
      doorMeta = "Ce visage n'est pas enrôlé.";
      break;
    case "pending":
      doorLabel = "Vérification";
      doorName = live?.label ?? "Analyse en cours";
      doorMeta =
        live && live.face_count > 1 ? `${live.face_count} visages` : "";
      break;
    case "idle":
      doorLabel = "Porte fermée";
      doorName = "Aucun visage";
      doorMeta = "La caméra surveille l'entrée.";
      break;
    default: {
      const _exhaustive: never = door;
      return _exhaustive;
    }
  }

  return (
    <AppShell active="dashboard" online={online} wide>
      {error && (
        <div className="alert alert-error" role="alert">
          <IconAlert />
          <span>{error}</span>
        </div>
      )}

      <section className="hero">
        <div className="card">
          <div className="card-title">
            <IconCamera />
            {streamFailed ? "Flux caméra indisponible" : "Entrée"}
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
        </div>

        <div className="card">
          <div className="card-title">Décision</div>
          <div className={`door door-${door}`} role="status">
            <p className="door-label">{doorLabel}</p>
            <p className="door-name">{doorName}</p>
            {doorMeta ? <p className="door-meta">{doorMeta}</p> : null}
          </div>
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
          <div className="empty">Aucun accès enregistré - enrôle une personne pour commencer.</div>
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
                    {typeof log.confidence === "number"
                      ? ` · ${log.confidence.toFixed(2)}`
                      : ""}
                  </span>
                </div>
                <time className="log-time">
                  {new Date(log.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="dash-footer">
        Mise à jour toutes les {POLL_MS / 1000} s
        {health
          ? ` · seuil ${health.matcher_threshold.toFixed(2)}`
          : null}
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
