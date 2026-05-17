'use client'

import { useState } from 'react'

type ClientKey = 'claude-desktop' | 'cursor' | 'curl'

const LABELS: Record<ClientKey, string> = {
  'claude-desktop': 'Claude Desktop',
  cursor: 'Cursor',
  curl: 'curl',
}

export function McpConfigSnippet({
  token,
  mcpUrl,
}: {
  token: string
  mcpUrl: string
}) {
  const [client, setClient] = useState<ClientKey>('claude-desktop')

  const snippets: Record<ClientKey, string> = {
    'claude-desktop': JSON.stringify(
      {
        mcpServers: {
          worldcupagents: {
            transport: 'http',
            url: `${mcpUrl}/mcp`,
            headers: { Authorization: `Bearer ${token}` },
          },
        },
      },
      null,
      2,
    ),
    cursor: JSON.stringify(
      {
        mcpServers: {
          worldcupagents: {
            url: `${mcpUrl}/mcp`,
            headers: { Authorization: `Bearer ${token}` },
          },
        },
      },
      null,
      2,
    ),
    curl: `curl ${mcpUrl}/mcp \\\n  -H 'Authorization: Bearer ${token}' \\\n  -H 'Content-Type: application/json'`,
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-foreground/10 p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Conectar tu cliente MCP</h3>
        <div className="flex gap-1 rounded-full border border-foreground/15 p-1 text-xs">
          {(['claude-desktop', 'cursor', 'curl'] as const).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setClient(key)}
              className={`rounded-full px-3 py-1 transition-colors ${
                client === key
                  ? 'bg-foreground text-background'
                  : 'opacity-70 hover:opacity-100'
              }`}
            >
              {LABELS[key]}
            </button>
          ))}
        </div>
      </div>
      <pre className="overflow-x-auto rounded-lg bg-black/80 p-3 text-xs text-zinc-100">
        <code>{snippets[client]}</code>
      </pre>
      <p className="text-xs text-zinc-500">
        Pegalo en{' '}
        {client === 'claude-desktop'
          ? '~/Library/Application Support/Claude/claude_desktop_config.json (macOS)'
          : client === 'cursor'
            ? 'la configuración MCP de Cursor'
            : 'una terminal'}
        .
      </p>
    </div>
  )
}
