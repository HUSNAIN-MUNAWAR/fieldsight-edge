export type ApiError = Error & { status?: number; requestId?: string };

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type ApiContext = { workspace: string; token?: string | null };

export async function apiFetch<T>(path: string, context: ApiContext, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('X-FieldSight-Workspace', context.workspace);
  headers.set('Accept', 'application/json');
  if (context.token) headers.set('Authorization', `Bearer ${context.token}`);
  if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: 'no-store' });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const error = new Error(typeof payload.detail === 'string' ? payload.detail : 'The operation could not be completed.') as ApiError;
    error.status = response.status;
    error.requestId = response.headers.get('X-Request-ID') || undefined;
    throw error;
  }
  return response.json() as Promise<T>;
}

export function operationalContext(workspace: string): ApiContext {
  if (typeof window === 'undefined') return { workspace };
  return { workspace, token: window.localStorage.getItem('fieldsight.access_token') };
}
