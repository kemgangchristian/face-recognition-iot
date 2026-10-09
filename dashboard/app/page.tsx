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
  getStreamUrl,
  type Stats,
  type AccessLog,
  type Health,
} from "@/lib/api";

const POLL_MS = 2000;
const FRESH_MS = 45000;

type DoorState = "idle" | "granted" | "denied";

function doorStateFromLog(log: AccessLog | undefined, now: number): DoorState {
  if (!log) return "idle";
  const age = now - new Date(log.timestamp).getTime();
  if (Number.isNaN(age) || age > FRESH_MS) return "idle";
  return log.matched ? "granted" : "denied";
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [now, setNow] = useState(() => Date.now());
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
        setNow(Date.now());
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
  const latest = logs[0];
  const door: DoorState = doorStateFromLog(latest, now);
  const streamUrl = `${getStreamUrl(true)}?t=${streamKey}`;

  let doorLabel: string;
  let doorName: string;
  let doorInitial: string;
  switch (door) {
    case "granted":
      doorLabel = "Autorise";
      doorName = latest?.full_name || "Identite reconnue";
      doorInitial = (latest?.full_name || "A").charAt(0).toUpperCase();
      break;
    case "denied":
      doorLabel = "Refuse";
      doorName = "Inconnu";
      doorInitial = "!";
      break;
    case "idle":
      doorLabel = "En attente";
      doorName = "Personne devant la porte";
      doorInitial = "·";
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

            {!streamFailed && <div className="stream-overlay" aria-hidden />}

            {!streamFailed && streamLoaded && (
              <div className="stream-hud">
                <span
                  className={`avatar ${
                    door === "granted"
                      ? "avatar-ok"
                      : door === "denied"
                        ? "avatar-no"
                        : ""
                  }`}
                >
                  {doorInitial}
                </span>
                <div>
                  <div className="stream-hud-name">{doorName}</div>
                  <div className="stream-hud-meta">{doorLabel}</div>
                </div>
              </div>
            )}

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
            <span className="door-badge">{doorInitial}</span>
            <span className="door-label">{doorLabel}</span>
            <span className="door-name">{doorName}</span>
            <span className="door-meta">
              {latest && door !== "idle" ? (
                <>
                  {new Date(latest.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                  {typeof latest.confidence === "number"
                    ? ` · score ${latest.confidence.toFixed(2)}`
                    : null}
                </>
              ) : latest ? (
                <>Dernier passage : {latest.matched ? latest.full_name : "inconnu"}</>
              ) : (
                "En attente d un visage"
              )}
            </span>
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
