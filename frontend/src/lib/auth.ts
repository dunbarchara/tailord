import { NextAuthOptions } from "next-auth"
import { decode, encode } from "next-auth/jwt"
import GoogleProvider from "next-auth/providers/google"

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],

  pages: {
    signIn: "/login",
  },

  session: {
    strategy: "jwt",
  },

  // Graceful secret rotation: new sessions are always signed with NEXTAUTH_SECRET.
  // During a rotation window, set NEXTAUTH_SECRET_PREVIOUS to the old value so
  // existing sessions remain valid. Remove it once session maxAge has elapsed.
  jwt: {
    async encode(params) {
      return encode({ ...params, secret: process.env.NEXTAUTH_SECRET! })
    },
    async decode(params) {
      const secrets = [
        process.env.NEXTAUTH_SECRET!,
        process.env.NEXTAUTH_SECRET_PREVIOUS,
      ].filter(Boolean) as string[]

      for (const secret of secrets) {
        try {
          const decoded = await decode({ ...params, secret })
          if (decoded) return decoded
        } catch {
          // Secret did not match — try the next one.
        }
      }
      return null
    },
  },

  callbacks: {
    async redirect({ url, baseUrl }) {
      // Always send users to dashboard after sign-in
      if (url.startsWith("/")) return `${baseUrl}${url}`
      if (new URL(url).origin === baseUrl) return url
      return `${baseUrl}/dashboard`
    },

    async jwt({ token, trigger }) {
      // Fetch user status on sign-in and on explicit session update
      // (e.g. when the pending page calls update() to re-check approval)
      if (trigger === "signIn" || trigger === "update") {
        try {
          const res = await fetch(`${process.env.API_BASE_URL}/users/me`, {
            method: "POST",
            headers: {
              "X-API-Key": process.env.API_KEY!,
              "X-User-Id": token.sub!,
              "X-User-Email": token.email ?? "",
              "X-User-Name": token.name ?? "",
            },
          })
          if (res.ok) {
            const data = await res.json()
            token.status = data.status
            token.isAdmin = data.is_admin === true
          }
        } catch {
          // Backend unreachable (e.g. cold start) — mark as checking so the
          // client can poll and show a loading UI instead of blocking here
          token.status = "checking"
        }
      }
      return token
    },

    async session({ session, token }) {
      if (session.user && token.sub) {
        session.user.id = token.sub
        session.user.status = (token.status as string) ?? "pending"
        session.user.isAdmin = token.isAdmin === true
      }
      return session
    },
  },
}
