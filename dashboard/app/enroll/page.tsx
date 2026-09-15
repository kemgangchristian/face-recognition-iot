"use client";

import { useEffect, useRef, useState } from "react";
import AppShell, {
  IconCamera,
  IconUserPlus,
  IconCheck,
  IconAlert,
  IconVideoOff,
} from "@/components/AppShell";
import { enrollIdentity, getStreamUrl } from "@/lib/api";

type Status =
  | { type: "success"; message: string }
  | { type: "error"; message: string }
  | null;

export default function EnrollPage() {
  const [fullName, setFullName] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [loading, setLoading] = useState(false);

  const [streamFailed, setStreamFailed] = useState(false);
  const [streamLoaded, setStreamLoaded] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const imgRef = useRef<HTMLImageElement | null>(null);

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

  const streamUrl = (() => {
    const base = getStreamUrl(false);
    const sep = base.includes("?") ? "&" : "?";
    return `${base}${sep}t=${streamKey}`;
  })();

  async function handleEnroll() {
    if (!fullName.trim()) {
      setStatus({ type: "error", message: "Entre un nom avant de capturer." });
      return;
    }

    const img = imgRef.current;
    if (!img) {
      setStatus({ type: "error", message: "Référence caméra introuvable." });
      return;
    }

    if (streamFailed) {
      setStatus({
        type: "error",
        message: "Le flux caméra n'est pas disponible.",
      });
      return;
    }

    if (img.naturalWidth === 0 || img.naturalHeight === 0) {
      setStatus({
        type: "error",
        message:
          "La caméra n'a pas encore envoyé d'image. Réessayez dans 1 s.",
      });
      return;
    }

    setLoading(true);
    setStatus(null);

    try {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas 2D indisponible.");
      ctx.drawImage(img, 0, 0);

      const blob: Blob = await new Promise((resolve, reject) => {
        canvas.toBlob(
          (b) => (b ? resolve(b) : reject(new Error("Capture impossible."))),
          "image/jpeg",
          0.92
        );
      });

      const file = new File([blob], "capture.jpg", { type: "image/jpeg" });
      const trimmed = fullName.trim();
      const result = await enrollIdentity(trimmed, file);

      setStatus({
        type: "success",
        message: result.message
          ? `${trimmed} — ${result.message} (ID ${result.identity_id}).`
          : `${trimmed} enrôlé avec succès (ID ${result.identity_id}).`,
      });
      setFullName("");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur inconnue.";
      setStatus({ type: "error", message: `Échec : ${message}` });
    } finally {
      setLoading(false);
    }
  }

  const canSubmit =
    !loading && !streamFailed && fullName.trim().length > 0;

  return (
    <AppShell active="enroll">
      <h1 className="page-title">Enrôler une identité</h1>

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
          <IconCamera />
          {streamFailed
            ? "Flux caméra indisponible"
            : "Flux caméra pour capture"}
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
            alt="Flux caméra pour capture d'enrôlement"
            crossOrigin="anonymous"
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

      <section className="card">
        <div className="card-title">
          <IconUserPlus /> Nouvelle identité
        </div>

        <div className="field">
          <label className="field-label" htmlFor="fullName">
            Nom complet
          </label>
          <input
            id="fullName"
            className="input"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Ex. Marie Dupont"
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && canSubmit) handleEnroll();
            }}
          />
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleEnroll}
          disabled={!canSubmit}
        >
          {loading ? (
            <>
              <span className="spinner" /> Capture en cours...
            </>
          ) : (
            <>
              <IconCamera /> Capturer et enrôler
            </>
          )}
        </button>
      </section>

      <footer className="dash-footer">
        Place le visage bien centré, face à la caméra, avant de capturer.
      </footer>
    </AppShell>
  );
}
