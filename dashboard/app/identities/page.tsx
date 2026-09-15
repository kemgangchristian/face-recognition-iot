"use client";

import { useEffect, useState } from "react";
import AppShell, {
  IconUsers,
  IconTrash,
  IconAlert,
  IconCheck,
} from "@/components/AppShell";
import {
  getIdentities,
  deleteIdentity,
  type Identity,
} from "@/lib/api";

type Status =
  | { type: "success"; message: string }
  | { type: "error"; message: string }
  | null;

export default function IdentitiesPage() {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<Status>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function loadData() {
    try {
      const data = await getIdentities();
      setIdentities(data.identities ?? []);
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
  }, []);

  async function handleDelete(id: number, name: string) {
    if (!confirm(`Supprimer « ${name} » ? Cette action est irréversible.`)) {
      return;
    }
    setDeletingId(id);
    setStatus(null);
    try {
      await deleteIdentity(id);
      setStatus({
        type: "success",
        message: `« ${name} » a été supprimé.`,
      });
      setIdentities((prev) => prev.filter((i) => i.id !== id));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur inconnue.";
      setStatus({ type: "error", message: `Échec : ${message}` });
    } finally {
      setDeletingId(null);
    }
  }

  const online = !error;

  return (
    <AppShell active="identities" online={online}>
      <h1 className="page-title">Identités enrôlées</h1>

      {error && (
        <div className="alert alert-error" role="alert">
          <IconAlert />
          <span>{error}</span>
        </div>
      )}

      {status && (
        <div
          className={`alert ${
            status.type === "success" ? "alert-success" : "alert-error"
          }`}
          role="alert"
        >
          {status.type === "success" ? <IconCheck /> : <IconAlert />}
          <span>{status.message}</span>
        </div>
      )}

      <section className="card">
        <div className="card-title">
          <IconUsers /> {identities.length} identité
          {identities.length > 1 ? "s" : ""}
        </div>

        {loading && identities.length === 0 ? (
          <div className="log-list">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton" />
            ))}
          </div>
        ) : identities.length === 0 ? (
          <div className="empty">
            Aucune identité enrôlée pour l&apos;instant.
          </div>
        ) : (
          <ul className="log-list">
            {identities.map((identity) => (
              <li key={identity.id} className="log-row">
                <span className="avatar avatar-ok">
                  {(identity.full_name || "?").charAt(0).toUpperCase()}
                </span>
                <div className="log-info">
                  <span className="log-name">{identity.full_name}</span>
                  <span className="log-sub">
                    ID {identity.id}
                    {identity.enrolled_at
                      ? ` • enrôlé le ${new Date(
                          identity.enrolled_at
                        ).toLocaleDateString()}`
                      : ""}
                    {typeof identity.pose_count === "number"
                      ? ` • ${identity.pose_count} pose${
                          identity.pose_count > 1 ? "s" : ""
                        }`
                      : ""}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() =>
                    handleDelete(identity.id, identity.full_name)
                  }
                  disabled={deletingId === identity.id}
                  aria-label={`Supprimer ${identity.full_name}`}
                  title="Supprimer"
                >
                  {deletingId === identity.id ? (
                    <span className="spinner" />
                  ) : (
                    <IconTrash />
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="dash-footer">
        Les identités supprimées ne peuvent pas être récupérées.
      </footer>
    </AppShell>
  );
}
