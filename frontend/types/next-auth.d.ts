import { DefaultSession } from 'next-auth'

declare module 'next-auth' {
  interface Session {
    user: {
      id?: string
      isAdmin?: boolean
      hasAgent?: boolean
    } & DefaultSession['user']
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    is_admin?: boolean
    has_agent?: boolean
  }
}
