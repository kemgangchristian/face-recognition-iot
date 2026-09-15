"use client";

import { useEffect, useState } from "react";
import AppShell, {
  IconList,
  IconAlert,
  IconCheck,
} from "@/components/AppShell";
import { getLogs, type AccessLog } from "@/lib/api";

const PAGE_SIZE = 50;

export default function LogsPage() {
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "matched" | "denied">("all");

  async function loadData() {
    try {
      const data = await getLogs(PAGE_SIZE);
      setLogs(data.logs ?? []);
      setError(null);
    } catch {
      setError(
        "Impossible de contacter l'API. Vérifiez que le Pi est accessible."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 10000);
    return () => clearInterval(id);
  }, []);

  const filtered = logs.filter((log) => {
    if (filter === "matched") return log.matched;
    if (filter === "denied") return !log.matched;
    return true;
  });

  const online = !error;

  return (
    <AppShell active="logs" online={online}>
      <h1 className="page-title">Journal des accès</h1>

      {error && (
        <div className="alert alert-error" role="alert">
          <IconAlert />
          <span>{error}</span>
        </div>
      )}

      <div className="filters">
        <button
          type="button"
          className={`filter ${filter === "all" ? "filter-active" : ""}`}
          onClick={() => setFilter("all")}
        >
          Tous ({logs.length})
        </button>
        <button
          type="button"
          className={`filter ${filter === "matched" ? "filter-active" : ""}`}
          onClick={() => setFilter("matched")}
        >
          <IconCheck /> Reconnus ({logs.filter((l) => l.matched).length})
        </button>
        <button
          type="button"
          className={`filter ${filter === "denied" ? "filter-active" : ""}`}
          onClick={() => setFilter("denied")}
        >
          Inconnus ({logs.filter((l) => !l.matched).length})
        </button>
      </div>

      <section className="card">
        <div className="card-title">
          <IconList /> {filtered.length} entrée
          {filtered.length > 1 ? "s" : ""}
        </div>

        {loading && logs.length === 0 ? (
          <div className="log-list">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty">Aucune entrée à afficher.</div>
        ) : (
          <ul className="log-list">
            {filtered.map((log) => (
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
                  <span
                    className={`log-name ${log.matched ? "ok" : "no"}`}
                  >
                    {log.matched ? log.full_name : "Inconnu"}
                  </span>
                  <span className="log-sub">
                    {log.matched ? "Accès autorisé" : "Accès refusé"}
                    {typeof log.confidence === "number"
                      ? ` • ${(log.confidence * 100).toFixed(0)}%`
                      : ""}
                  </span>
                </div>
                <time className="log-time">
                  {new Date(log.timestamp).toLocaleString([], {
                    day: "2-digit",
                    month: "2-digit",
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
        Mise à jour automatique toutes les 10 s
      </footer>
    </AppShell>
  );
}
