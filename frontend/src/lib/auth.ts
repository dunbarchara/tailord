import { NextAuthOptions } from "next-auth"
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
      }
      return session
    },
  },
}
