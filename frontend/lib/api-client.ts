/**
 * Client-side wrappers around the backend REST API. Same-origin: the browser
 * attaches the Auth.js session cookie automatically.
 */

import {
  API_BASE,
  type AgentCreateResponse,
  type MeResponse,
  parseError,
} from './api-types'

export {
  ApiCallError,
  type AgentCreateResponse,
  type AgentPublic,
  type ApiError,
  type MeResponse,
} from './api-types'

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    cache: 'no-store',
  })
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as T
}

export const api = {
  me: () => call<MeResponse>('/api/v1/me'),
  createAgent: (body: { name: string; description?: string; model_hint?: string }) =>
    call<AgentCreateResponse>('/api/v1/me/agent', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  rotateToken: () =>
    call<{ token: string; token_prefix: string; rotated_at: string }>(
      '/api/v1/me/agent/rotate-token',
      { method: 'POST' },
    ),
  retireAgent: () =>
    call<{ ok: boolean; is_retired: boolean }>('/api/v1/me/agent/retire', {
      method: 'POST',
    }),
}
