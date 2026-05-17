export type AgentPublic = {
  agent_id: string
  slug: string
  name: string
  description: string | null
  model_hint: string | null
  avatar_url: string | null
  token_prefix: string
  is_retired: boolean
  created_at: string
}

export type MeResponse = {
  human_id: string
  email: string
  name: string | null
  avatar_url: string | null
  is_admin: boolean
  agent: AgentPublic | null
}

export type AgentCreateResponse = AgentPublic & { token: string }

export type ApiError = {
  error: string
  message: string
  details?: Record<string, unknown>
}

export class ApiCallError extends Error {
  constructor(
    public status: number,
    public payload: ApiError,
  ) {
    super(`${payload.error}: ${payload.message}`)
  }
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export async function parseError(res: Response): Promise<ApiCallError> {
  let payload: ApiError = { error: 'INTERNAL_ERROR', message: res.statusText }
  try {
    payload = (await res.json()) as ApiError
  } catch {
    /* keep default */
  }
  return new ApiCallError(res.status, payload)
}
