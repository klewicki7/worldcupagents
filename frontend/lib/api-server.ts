import 'server-only'

import { headers as nextHeaders } from 'next/headers'

import { API_BASE, type MeResponse, parseError } from './api-types'

async function forwardedCookieHeader(): Promise<Record<string, string>> {
  const headerList = await nextHeaders()
  const cookie = headerList.get('cookie')
  return cookie ? { cookie } : {}
}

export async function fetchMeFromServer(): Promise<MeResponse> {
  const res = await fetch(`${API_BASE}/api/v1/me`, {
    headers: {
      'Content-Type': 'application/json',
      ...(await forwardedCookieHeader()),
    },
    cache: 'no-store',
  })
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as MeResponse
}
