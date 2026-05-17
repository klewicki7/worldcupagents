import { DashboardClient } from '@/components/dashboard-client'
import { ApiCallError, type MeResponse } from '@/lib/api-client'
import { fetchMeFromServer } from '@/lib/api-server'

export const dynamic = 'force-dynamic'

type FetchResult =
  | { kind: 'ok'; me: MeResponse }
  | { kind: 'unauth' }
  | { kind: 'error' }

async function loadMe(): Promise<FetchResult> {
  try {
    const me = await fetchMeFromServer()
    return { kind: 'ok', me }
  } catch (err) {
    if (err instanceof ApiCallError && err.status === 401) return { kind: 'unauth' }
    return { kind: 'error' }
  }
}

export default async function DashboardPage() {
  const mcpUrl = process.env.NEXT_PUBLIC_MCP_BASE_URL ?? 'http://localhost:8000'
  const result = await loadMe()

  if (result.kind === 'ok') {
    return <DashboardClient initialAgent={result.me.agent} mcpUrl={mcpUrl} />
  }
  if (result.kind === 'unauth') {
    return (
      <section className="rounded-2xl border border-red-500/30 bg-red-500/5 p-5 text-sm">
        Tu sesión no se sincronizó con el backend. Cerrá sesión y volvé a ingresar.
      </section>
    )
  }
  return (
    <section className="rounded-2xl border border-foreground/10 p-5 text-sm">
      No pudimos cargar tu perfil. Probá recargar la página.
    </section>
  )
}
