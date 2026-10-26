const KEY = 'fitpulse_apple_health_key';

export function healthHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem(KEY);
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch { return {}; }
}

export function saveHealthKey(token: string) {
  if (token) localStorage.setItem(KEY, token);
  else localStorage.removeItem(KEY);
  window.dispatchEvent(new Event('fitpulse:health-changed'));
}

export async function responseError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null);
  return new Error(typeof body?.detail === 'string' ? body.detail : 'Не удалось получить данные. Повтори попытку.');
}
