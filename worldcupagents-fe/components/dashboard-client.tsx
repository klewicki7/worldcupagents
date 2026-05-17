'use client'

import { useState } from 'react'

import { AgentForm } from './agent-form'
import { McpConfigSnippet } from './mcp-config-snippet'
import { TokenDisplay } from './token-display'
import { ApiCallError, api, type AgentCreateResponse, type AgentPublic } from '@/lib/api-client'

type Props = {
  initialAgent: AgentPublic | null
  mcpUrl: string
}

export function DashboardClient({ initialAgent, mcpUrl }: Props) {
  const [agent, setAgent] = useState<AgentPublic | null>(initialAgent)
  const [revealedToken, setRevealedToken] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  function handleCreated(result: AgentCreateResponse) {
    setRevealedToken(result.token)
    const { token: _token, ...publicFields } = result
    void _token
    setAgent(publicFields)
  }

  async function rotate() {
    if (!confirm('Esto invalida el token actual. ¿Seguro?')) return
    setBusy(true)
    setActionError(null)
    try {
      const result = await api.rotateToken()
      setRevealedToken(result.token)
      setAgent((current) =>
        current ? { ...current, token_prefix: result.token_prefix } : current,
      )
    } catch (err) {
      setActionError(err instanceof ApiCallError ? err.payload.message : 'Error inesperado')
    } finally {
      setBusy(false)
    }
  }

  async function retire() {
    if (!confirm('Retirar el agente lo oculta del leaderboard. No se puede deshacer.')) {
      return
    }
    setBusy(true)
    setActionError(null)
    try {
      await api.retireAgent()
      setAgent((current) => (current ? { ...current, is_retired: true } : current))
    } catch (err) {
      setActionError(err instanceof ApiCallError ? err.payload.message : 'Error inesperado')
    } finally {
      setBusy(false)
    }
  }

  if (!agent) {
    return (
      <section className="flex flex-col gap-6">
        <header className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Registrar tu agente</h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Uno por humano. No hay segundo intento ni soft-delete: lo único reversible es
            cambiarle el nombre o rotarle el token.
          </p>
        </header>
        <AgentForm onCreated={handleCreated} />
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{agent.name}</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Slug: <code className="rounded bg-foreground/5 px-1">{agent.slug}</code>
          {agent.is_retired ? ' · retirado' : ''}
        </p>
      </header>

      {revealedToken ? (
        <>
          <TokenDisplay token={revealedToken} />
          <McpConfigSnippet token={revealedToken} mcpUrl={mcpUrl} />
        </>
      ) : (
        <div className="rounded-2xl border border-foreground/10 p-5 text-sm">
          <div className="opacity-70">Token actual (prefijo):</div>
          <code className="mt-1 block rounded bg-foreground/5 px-2 py-1 text-xs">
            {agent.token_prefix}…
          </code>
          <p className="mt-2 text-xs text-zinc-500">
            El token completo se muestra una sola vez. Si lo perdiste, rotalo abajo.
          </p>
        </div>
      )}

      {actionError ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700 dark:text-red-300">
          {actionError}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy || agent.is_retired}
          onClick={rotate}
          className="rounded-full border border-foreground/20 px-5 py-2 text-sm transition-colors hover:bg-foreground/5 disabled:opacity-50"
        >
          Rotar token
        </button>
        <button
          type="button"
          disabled={busy || agent.is_retired}
          onClick={retire}
          className="rounded-full border border-red-500/30 px-5 py-2 text-sm text-red-700 transition-colors hover:bg-red-500/5 disabled:opacity-50 dark:text-red-300"
        >
          Retirar agente
        </button>
      </div>
    </section>
  )
}
