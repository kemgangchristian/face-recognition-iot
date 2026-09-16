"use client";

import { useState } from "react";
import { login } from "@/lib/api";
import ThemeToggle from "@/components/ThemeToggle";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!password) {
      setError("Entre le mot de passe.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await login(password);

      if (!result.authenticated) {
        setError("Mot de passe incorrect.");
        setPassword("");
        setLoading(false);
        return;
      }

      // Petit délai pour laisser le navigateur traiter le Set-Cookie
      // avant de déclencher la navigation.
      await new Promise((r) => setTimeout(r, 150));

      // Redirection "dure" : le navigateur recharge la page /, envoie le cookie
      // dès la première requête, et le dashboard s'affiche correctement.
      window.location.href = "/";
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Erreur de connexion.";
      setError(
        message.includes("401")
          ? "Mot de passe incorrect."
          : "Impossible de contacter l'API."
      );
      setPassword("");
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <style>{styles}</style>

      <div className="login-theme">
        <ThemeToggle />
      </div>

      <div className="login-card">
        <div className="login-brand">
          <span className="login-brand-icon">
            <IconShield />
          </span>
          <h1 className="login-title">Sentinel Access</h1>
          <p className="login-subtitle">Connexion au tableau de bord</p>
        </div>

        <form onSubmit={handleLogin} className="login-form">
          <div className="field">
            <label className="field-label" htmlFor="password">
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoFocus
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || !password}
          >
            {loading ? (
              <>
                <span className="spinner" /> Connexion...
              </>
            ) : (
              <>
                <IconLock /> Se connecter
              </>
            )}
          </button>

          {error && (
            <div className="alert alert-error" role="alert">
              <IconAlert />
              <span>{error}</span>
            </div>
          )}
        </form>

        <p className="login-footer">
          Accès réservé. Toute tentative est journalisée.
        </p>
      </div>
    </main>
  );
}

/* ---------- Icons ---------- */

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const IconShield = () => (
  <svg viewBox="0 0 24 24" width="28" height="28" {...stroke}>
    <path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6z" />
    <path d="m9 12 2 2 4-4" />
  </svg>
);
const IconLock = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <rect x="4" y="10" width="16" height="11" rx="2" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
  </svg>
);
const IconAlert = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" {...stroke}>
    <path d="M12 3 2 20h20z" />
    <path d="M12 10v4M12 17.5v.01" />
  </svg>
);

/* ---------- Styles ---------- */

const styles = `
  .login-page {
    position: relative;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px 16px;
    background: var(--background);
    color: var(--foreground);
    font-family: var(--font-sans), ui-sans-serif, system-ui, -apple-system,
      "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .login-page * { box-sizing: border-box; }

  .login-page::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
      radial-gradient(60% 45% at 50% 0%,
        color-mix(in srgb, var(--violet) 18%, transparent),
        transparent 70%),
      radial-gradient(40% 35% at 50% 100%,
        color-mix(in srgb, var(--blue) 12%, transparent),
        transparent 70%);
    opacity: .9;
  }

  .login-theme {
    position: absolute;
    top: 16px; right: 16px;
    z-index: 2;
  }

  .login-card {
    position: relative;
    z-index: 1;
    width: 100%;
    max-width: 380px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 28px 22px 22px;
    box-shadow: var(--shadow-card);
  }

  .login-brand {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 8px;
    margin-bottom: 22px;
  }
  .login-brand-icon {
    width: 56px; height: 56px;
    border-radius: 16px;
    display: inline-flex; align-items: center; justify-content: center;
    color: var(--violet);
    background: color-mix(in srgb, var(--violet) 14%, transparent);
    box-shadow:
      inset 0 0 0 1px color-mix(in srgb, var(--violet) 35%, transparent),
      0 4px 16px color-mix(in srgb, var(--violet) 25%, transparent);
    margin-bottom: 4px;
  }
  .login-title {
    font-size: 20px;
    font-weight: 650;
    letter-spacing: -0.01em;
    margin: 0;
  }
  .login-subtitle {
    font-size: 13px;
    color: var(--muted);
    margin: 0;
  }

  .login-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .login-footer {
    margin: 20px 0 0;
    text-align: center;
    font-size: 11.5px;
    color: var(--muted);
  }

  .field { display: flex; flex-direction: column; gap: 6px; }
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

  .spinner {
    width: 14px; height: 14px;
    border-radius: 50%;
    border: 2px solid rgba(255,255,255,.35);
    border-top-color: #fff;
    animation: spin .8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg) } }

  .alert {
    display: flex; align-items: center; gap: 10px;
    padding: 12px 14px;
    border-radius: 12px; font-size: 13.5px; font-weight: 500;
    border: 1px solid transparent;
  }
  .alert-error {
    background: color-mix(in srgb, var(--red) 10%, transparent);
    border-color: color-mix(in srgb, var(--red) 35%, transparent);
    color: var(--red);
  }

  @media (max-width: 400px) {
    .login-card { padding: 22px 16px 18px; border-radius: 16px; }
    .login-title { font-size: 18px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner { animation: none; }
    .btn { transition: none; }
  }
`;
