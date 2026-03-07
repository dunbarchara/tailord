import { withAuth } from "next-auth/middleware"
import { NextResponse } from "next/server"

export default withAuth(
  function middleware(req) {
    const { pathname } = req.nextUrl
    const status = req.nextauth.token?.status

    // Backend was unreachable at sign-in — send to loading screen to poll
    if (status === "checking" && pathname !== "/checking") {
      return NextResponse.redirect(new URL("/checking", req.url))
    }

    // Approved users landing on /pending or /checking should go to dashboard
    if ((pathname === "/pending" || pathname === "/checking") && status === "approved") {
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
  matcher: ["/dashboard/:path*", "/pending", "/checking"],
}
