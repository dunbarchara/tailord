import { withAuth } from "next-auth/middleware"

export default withAuth(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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
// AUTH TEMPORARILY DISABLED FOR TROUBLESHOOTING — re-enable before merging 
export const config = {
  //matcher: ["/dashboard/:path*"],
  matcher: [], 
}
