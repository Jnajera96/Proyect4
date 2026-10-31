type Envelope<T> = { ok: boolean; data: T; error?: { message: string } };
export class HttpError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function loadResource<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(path, { signal: controller.signal });
    if (!response.ok) throw new HttpError(response.status, 'Request failed');
    const envelope = await response.json() as Envelope<T>;
    if (!envelope.ok) throw new HttpError(400, envelope.error?.message ?? 'Unknown error');
    return envelope.data;
  } finally {
    clearTimeout(timeout);
  }
}
export async function loadCatalog() {
  return loadResource<Array<{ name: string; price: string }>>('/inventory');
}
