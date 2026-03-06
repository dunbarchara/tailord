import { withAuth } from "next-auth/middleware"

export default withAuth(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function middleware(req) {
    // You can add logging or role checks here later
  },
  {
    pages: {
      signIn: "/login",
    },
    callbacks: {
      authorized: ({ token }) => !!token,
    },
  }
)

// Only protect dashboard routes
export const config = {
  matcher: ["/dashboard/:path*"],
}
