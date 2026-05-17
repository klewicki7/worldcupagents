'use client'

import { useState } from 'react'

export function TokenDisplay({ token }: { token: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    await navigator.clipboard.writeText(token)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-amber-500/40 bg-amber-500/5 p-5">
      <div className="text-sm font-medium text-amber-700 dark:text-amber-300">
        Copiá este token ahora. No lo vas a ver de nuevo.
      </div>
      <code className="block break-all rounded-lg bg-black/80 px-3 py-2 text-xs text-zinc-100">
        {token}
      </code>
      <button
        type="button"
        onClick={copy}
        className="self-start rounded-full border border-amber-700/30 px-4 py-2 text-sm transition-colors hover:bg-amber-500/10"
      >
        {copied ? '¡Copiado!' : 'Copiar al portapapeles'}
      </button>
      <p className="text-xs text-amber-800/80 dark:text-amber-200/80">
        Si lo perdés, vas a tener que rotarlo desde acá. La rotación invalida el token
        anterior inmediatamente.
      </p>
    </div>
  )
}
