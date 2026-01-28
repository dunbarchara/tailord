import { withAuth } from "next-auth/middleware"

export default withAuth(
  function middleware(req) {
    // You can add logging or role checks here later
  },
  {
    callbacks: {
      authorized: ({ token }) => {
        // If there is a session token, user is authenticated
        return !!token
      },
    },
  }
)

// Only protect dashboard routes
export const config = {
  matcher: ["/dashboard/:path*"],
}
