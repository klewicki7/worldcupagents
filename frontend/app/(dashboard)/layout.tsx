import Link from 'next/link'
import { redirect } from 'next/navigation'

import { auth, signOut } from '@/auth'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await auth()
  if (!session?.user) redirect('/signin?callbackUrl=/dashboard')

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-10 sm:px-8">
      <header className="flex items-center justify-between border-b border-foreground/10 pb-4">
        <Link href="/" className="font-mono text-sm tracking-tight">
          worldcupagents
        </Link>
        <div className="flex items-center gap-3 text-sm">
          <span className="opacity-70">{session.user.email}</span>
          <form
            action={async () => {
              'use server'
              await signOut({ redirectTo: '/' })
            }}
          >
            <button type="submit" className="opacity-70 underline-offset-2 hover:underline">
              Salir
            </button>
          </form>
        </div>
      </header>
      {children}
    </div>
  )
}
