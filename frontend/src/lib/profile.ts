/** Session CSRF stays in memory; the opaque authentication cookie is HttpOnly. */
let csrf: string | null = null;
export function setProfileCsrf(value: string | null) { csrf = value; }
export function profileHeaders(): Record<string, string> {
  return csrf ? { "X-CSRF-Token": csrf } : {};
}
export function expireProfile() {
  if (csrf) {
    csrf = null;
    window.dispatchEvent(new Event("aiswe-profile-expired"));
  }
}
export async function profileRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init, credentials: "same-origin",
    headers: { ...init?.headers, ...profileHeaders() },
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) expireProfile();
    throw new Error(typeof data.detail === "string" ? data.detail : "Solicitud rechazada");
  }
  return data as T;
}
