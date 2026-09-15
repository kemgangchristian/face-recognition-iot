const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "X-API-Key": API_KEY,
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(
      `Erreur API (${response.status}): ${await response.text()}`
    );
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

/* ---------- Endpoints ---------- */

export function getIdentities(): Promise<{
  count: number;
  identities: Identity[];
}> {
  return apiFetch("/identities");
}

export function deleteIdentity(id: number): Promise<{ deleted: boolean }> {
  return apiFetch(`/identities/${id}`, { method: "DELETE" });
}

export function getStats(): Promise<Stats> {
  return apiFetch("/stats");
}

export function getLogs(
  limit = 100
): Promise<{ count: number; logs: AccessLog[] }> {
  return apiFetch(`/logs?limit=${limit}`);
}

export function enrollIdentity(
  fullName: string,
  imageFile: File
): Promise<{ identity_id: number; full_name: string; message: string }> {
  const formData = new FormData();
  formData.append("full_name", fullName);
  formData.append("image", imageFile);

  return apiFetch("/enroll", {
    method: "POST",
    body: formData,
  });
}

export function getStreamUrl(detected: boolean = true): string {
  const endpoint = detected ? "/stream/detected" : "/stream/raw";
  return `${API_BASE_URL}${endpoint}?api_key=${API_KEY}`;
}
