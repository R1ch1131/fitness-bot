// Display the last confirmed response while the server refreshes it.
const prefix = 'fitpulse_snapshot_v1_';
export function omskDay(now = new Date()): string {
  return new Date(now.getTime() + 6 * 3600000).toISOString().slice(0, 10);
}

export function readSnapshot<T>(name: string, validate: (value: unknown) => boolean): T | null {
  try {
    const value = JSON.parse(localStorage.getItem(prefix + name) || 'null');
    if (!value || value.day !== omskDay() || !validate(value.data)) return null;
    return value.data as T;
  } catch { return null; }
}

export function writeSnapshot(name: string, data: unknown): void {
  try { localStorage.setItem(prefix + name, JSON.stringify({ day: omskDay(), data })); }
  catch { /* Storage can be unavailable or full; network loading still works. */ }
}

export function isHabits(value: unknown): boolean {
  return Array.isArray(value) && value.every(h => h && typeof h.id === 'string' && typeof h.title === 'string' && h.history && typeof h.history === 'object');
}

export function isDashboard(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const data = value as Record<string, unknown>;
  return data.date === omskDay() && !!data.nutrition && !!data.profile && !!data.workout;
}
