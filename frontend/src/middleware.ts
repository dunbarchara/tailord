import { withAuth } from "next-auth/middleware"
import { NextResponse } from "next/server"

export default withAuth(
  function middleware(req) {
    const { pathname } = req.nextUrl
    const status = req.nextauth.token?.status

    // Approved users landing on /pending should go to dashboard
    if (pathname === "/pending" && status === "approved") {
      return NextResponse.redirect(new URL("/dashboard", req.url))
    }

    // Pending users cannot access the dashboard
    if (pathname.startsWith("/dashboard") && status !== "approved") {
      return NextResponse.redirect(new URL("/pending", req.url))
    }
  },
  {
    pages: {
      signIn: "/login",
    },
    callbacks: {
      // Handles unauthenticated users → redirect to /login
      authorized: ({ token }) => !!token,
    },
  }
)

export const config = {
  matcher: ["/dashboard/:path*", "/pending"],
}
