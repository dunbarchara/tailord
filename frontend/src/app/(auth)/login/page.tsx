
import { getServerSession } from "next-auth"
import { redirect } from "next/navigation"
import { authOptions } from "@/lib/auth"
import { AuthCard } from "@/components/AuthCard"

export default async function LoginPage() {
  const session = await getServerSession(authOptions)

  if (session) {
    redirect("/dashboard")
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-100">
      <AuthCard
        title="Sign in"
        googleText="Sign in with Google"
        emailText="Continue with email"
        authAction="Login"
      />
    </div>
  )
}