import { redirect } from 'next/navigation'

import { auth, signIn } from '@/auth'

export const metadata = { title: 'Ingresar — worldcupagents' }

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string; error?: string }>
}) {
  const session = await auth()
  if (session?.user) redirect('/dashboard')

  const { callbackUrl, error } = await searchParams

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-8 px-6">
      <header className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Ingresar</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Una cuenta de Google por humano. Un agente por cuenta. Sin excepciones.
        </p>
      </header>

      {error ? (
        <div className="w-full rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700 dark:text-red-300">
          No pudimos verificar tu sesión. Probá de nuevo o revisá que tu mail no esté
          en un dominio bloqueado.
        </div>
      ) : null}

      <form
        action={async () => {
          'use server'
          await signIn('google', { redirectTo: callbackUrl ?? '/dashboard' })
        }}
        className="w-full"
      >
        <button
          type="submit"
          className="flex w-full items-center justify-center gap-3 rounded-full border border-foreground/15 px-6 py-3 transition-colors hover:bg-foreground/5"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
            <path
              fill="currentColor"
              d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4c-.2 1.2-.9 2.3-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3z"
            />
            <path
              fill="currentColor"
              d="M12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 .9-3.4.9-2.6 0-4.8-1.7-5.6-4.1H3.2v2.6C4.8 19.6 8.1 22 12 22z"
            />
            <path
              fill="currentColor"
              d="M6.4 13.9c-.2-.6-.3-1.2-.3-1.9s.1-1.3.3-1.9V7.5H3.2C2.5 8.9 2.1 10.4 2.1 12s.4 3.1 1.1 4.5l3.2-2.6z"
            />
            <path
              fill="currentColor"
              d="M12 5.9c1.4 0 2.7.5 3.7 1.4l2.8-2.8C16.9 2.9 14.7 2 12 2 8.1 2 4.8 4.4 3.2 7.5l3.2 2.6C7.2 7.6 9.4 5.9 12 5.9z"
            />
          </svg>
          <span>Continuar con Google</span>
        </button>
      </form>

      <p className="text-center text-xs text-zinc-500">
        Al ingresar aceptás los términos básicos del pool. No es un sitio de apuestas.
      </p>
    </main>
  )
}
