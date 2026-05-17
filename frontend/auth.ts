import NextAuth from 'next-auth'
import Google from 'next-auth/providers/google'

/**
 * Auth.js v5 config. JWT strategy (no DB session table). On first sign-in we POST
 * the Google ID token to the backend `/api/v1/auth/verify`, which upserts the
 * `humans` row and returns the canonical `human_id` + `is_admin` flag. Those
 * land on the JWT (`token.sub` overridden) so server components can read them.
 *
 * The backend signs/verifies the same JWT using `JWT_SECRET == NEXTAUTH_SECRET`.
 */
export const {
  handlers: { GET, POST },
  signIn,
  signOut,
  auth,
} = NextAuth({
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID,
      clientSecret: process.env.AUTH_GOOGLE_SECRET,
    }),
  ],
  session: { strategy: 'jwt' },
  pages: { signIn: '/signin' },
  callbacks: {
    async jwt({ token, account }) {
      // Only run the verify call once, on initial sign-in.
      if (account?.provider === 'google' && account.id_token) {
        const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'
        try {
          const res = await fetch(`${apiBase}/api/v1/auth/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_token: account.id_token }),
          })
          if (res.ok) {
            const data = (await res.json()) as {
              human_id: string
              email: string
              name: string | null
              avatar_url: string | null
              is_admin: boolean
              has_agent: boolean
            }
            token.sub = data.human_id
            token.email = data.email
            token.name = data.name ?? token.name
            token.picture = data.avatar_url ?? token.picture
            token.is_admin = data.is_admin
            token.has_agent = data.has_agent
          } else {
            // Surface verification failures (e.g. BLOCKED_DOMAIN) by clearing the token.
            return null
          }
        } catch {
          return null
        }
      }
      return token
    },
    async session({ session, token }) {
      if (token.sub) session.user.id = token.sub
      session.user.isAdmin = Boolean(token.is_admin)
      session.user.hasAgent = Boolean(token.has_agent)
      return session
    },
  },
})
