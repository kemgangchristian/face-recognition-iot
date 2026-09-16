"use client";

import { useEffect, useState } from "react";

type ThemeMode = "auto" | "light" | "dark";

export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>("auto");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme") as ThemeMode | null;
    if (stored === "light" || stored === "dark" || stored === "auto") {
      setMode(stored);
    }
    setMounted(true);
  }, []);

  const cycle = () => {
    setMode((prev) => {
      const next: ThemeMode =
        prev === "auto" ? "light" : prev === "light" ? "dark" : "auto";

      const root = document.documentElement;
      if (next === "auto") root.removeAttribute("data-theme");
      else root.setAttribute("data-theme", next);

      try {
        if (next === "auto") localStorage.removeItem("theme");
        else localStorage.setItem("theme", next);
      } catch {}

      return next;
    });
  };

  return { mode, cycle, mounted };
}

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { mode, cycle, mounted } = useTheme();

  return (
    <>
      <style>{toggleStyles}</style>
      <button
        type="button"
        onClick={cycle}
        className={`theme-toggle ${className}`}
        aria-label={`Thème : ${
          mode === "auto"
            ? "automatique"
            : mode === "light"
            ? "clair"
            : "sombre"
        }. Cliquer pour changer.`}
        title={
          mode === "auto"
            ? "Thème : Auto (suit l'OS)"
            : mode === "light"
            ? "Thème : Clair"
            : "Thème : Sombre"
        }
      >
        {!mounted || mode === "auto" ? (
          <IconThemeAuto />
        ) : mode === "light" ? (
          <IconSun />
        ) : (
          <IconMoon />
        )}
      </button>
    </>
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

const IconSun = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);

const IconMoon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </svg>
);

const IconThemeAuto = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" {...stroke}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 3v18" />
    <path
      d="M12 3a9 9 0 0 1 0 18"
      fill="currentColor"
      opacity="0.35"
      stroke="none"
    />
  </svg>
);

/* ---------- Styles ---------- */

const toggleStyles = `
  .theme-toggle {
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
  .theme-toggle:hover {
    color: var(--foreground);
    background: var(--surface-2);
    border-color: var(--border-hover);
  }
  .theme-toggle:active { transform: scale(.94); }
  .theme-toggle:focus-visible {
    outline: 2px solid var(--violet);
    outline-offset: 2px;
  }
`;
