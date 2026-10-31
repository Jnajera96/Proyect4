type Visit = { path: string; at: number };
const storageKey = 'workspace.navigation';
export function readVisits(): Visit[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(storageKey) ?? '[]');
    if (!Array.isArray(value)) return [];
    return value.filter((row): row is Visit => Boolean(row)
      && typeof row.path === 'string' && typeof row.at === 'number');
  } catch { return []; }
}
export function remember(path: string, now = Date.now()): Visit[] {
  if (!path.startsWith('/')) throw new Error('Invalid local path');
  const visits = [{ path, at: now }, ...readVisits()].slice(0, 50);
  localStorage.setItem(storageKey, JSON.stringify(visits));
  return visits;
}
export function clearVisits() { localStorage.removeItem(storageKey); }
