// lib/api.ts
//
// Point d'entrée unique pour tous les appels au backend Pi.
//
// En production, le dashboard est servi par FastAPI (même origine) : les URLs
// sont relatives et le cookie de session est transmis naturellement.
// En développement (`next dev` sur :3000), NEXT_PUBLIC_PI_URL pointe vers le Pi
// et CORS côté FastAPI autorise localhost:3000 avec credentials.

const API_BASE_URL = process.env.NEXT_PUBLIC_PI_URL ?? "";

/**
 * Extrait un message lisible d'une réponse d'erreur FastAPI : le champ
 * `detail` quand le corps est du JSON de la forme {"detail": "..."},
 * sinon le texte brut.
 */
async function readErrorDetail(response: Response): Promise<string> {
  const raw = await response.text();
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // corps non JSON : on retombe sur le texte brut
  }
  return raw;
}

async function apiFetch<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
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
    throw new Error(`Erreur API (${response.status}): ${await readErrorDetail(response)}`);
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
}

export interface AccessLog {
  id: number;
  full_name: string | null;
  matched: boolean;
  confidence: number;
  timestamp: string;
}

export interface FaceStatus {
  ready: boolean;
  reason: string;
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

/**
 * Indique si le visage devant la caméra est bien placé pour une capture
 * d'enrôlement. Lecture seule : le serveur analyse la frame sans la
 * conserver.
 */
export function getFaceStatus(): Promise<FaceStatus> {
  return apiFetch("/camera/face-status");
}

/* ---------- Flux vidéo (appel direct au Pi, même origine ou CORS) ---------- */

export function getStreamUrl(detected: boolean = true): string {
  const endpoint = detected ? "/stream/detected" : "/stream/raw";
  return `${API_BASE_URL}${endpoint}`;
}
