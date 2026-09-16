// lib/api.ts
//
// Point d'entrée unique pour tous les appels au backend.
//
// Deux chemins distincts, volontairement différents :
//   - Toutes les routes de données (stats, logs, identités, enrôlement,
//     login/logout) passent par le proxy Next.js (/api/*), en même origine
//     que le navigateur : pas de CORS, cookie de session transmis
//     naturellement, aucune adresse ni secret exposé côté client.
//   - Le flux vidéo (streaming MJPEG) contacte le Pi DIRECTEMENT : un flux
//     continu à travers une route serverless Next.js est fragile (limites
//     de durée de connexion, mise en tampon). Nécessite CORS côté FastAPI
//     (déjà configuré) et credentials: "include" pour transmettre le
//     cookie malgré l'origine différente.

const PROXY_BASE_URL = "/api";

// Exposé au navigateur (préfixe NEXT_PUBLIC_ obligatoire) : seule variable
// d'environnement nécessaire côté client, pour construire l'URL du flux.
const PI_PUBLIC_URL = process.env.NEXT_PUBLIC_PI_URL || "http://192.168.1.191:8000";

async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${PROXY_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: { ...options.headers },
  });

  // Un 401 sur une route d'authentification (login) signifie "mauvais mot
  // de passe" : on laisse l'appelant afficher ce message. Un 401 ailleurs
  // signifie "session absente ou expirée" : on redirige vers la connexion.
  const isAuthRoute = path.startsWith("/login") || path.startsWith("/logout");

  if (response.status === 401) {
    if (!isAuthRoute && typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expirée.");
  }

  if (!response.ok) {
    throw new Error(`Erreur API (${response.status}): ${await response.text()}`);
  }

  return response.json() as Promise<T>;
}

/* ---------- Types ---------- */

export interface Identity {
  id: number;
  full_name: string;
  enrolled_at: string;
  pose_count: number;
}

export interface Stats {
  enrolled_count: number;
  accesses_today: number;
  matched_today: number;
  unmatched_today: number;
}

export interface AccessLog {
  id: number;
  full_name: string | null;
  matched: boolean;
  confidence: number;
  timestamp: string;
}

/* ---------- Authentification ---------- */

export function login(password: string): Promise<{ authenticated: boolean }> {
  const formData = new FormData();
  formData.append("password", password);
  return apiFetch("/login", { method: "POST", body: formData });
}

export function logout(): Promise<{ logged_out: boolean }> {
  return apiFetch("/logout", { method: "POST" });
}

/* ---------- Données ---------- */

export function getIdentities(): Promise<{ count: number; identities: Identity[] }> {
  return apiFetch("/identities");
}

export function deleteIdentity(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/identities/${id}`, { method: "DELETE" });
}

export function getStats(): Promise<Stats> {
  return apiFetch("/stats");
}

export function getLogs(limit = 100): Promise<{ count: number; logs: AccessLog[] }> {
  return apiFetch(`/logs?limit=${limit}`);
}

export function enrollIdentity(
  fullName: string,
  imageFile: File
): Promise<{ identity_id: number; message: string; full_name: string }> {
  const formData = new FormData();
  formData.append("full_name", fullName);
  formData.append("image", imageFile);

  return apiFetch("/enroll", { method: "POST", body: formData });
}

/* ---------- Flux vidéo (appel direct au Pi, hors proxy) ---------- */

export function getStreamUrl(detected: boolean = true): string {
  const endpoint = detected ? "/stream/detected" : "/stream/raw";
  return `${PI_PUBLIC_URL}${endpoint}`;
}
