import { getServerSession } from "next-auth"
import { redirect } from "next/navigation"
import { authOptions } from "@/lib/auth"
import { AuthCard } from "@/components/AuthCard"

export default async function RegisterPage() {
  const session = await getServerSession(authOptions)

  if (session) {
    redirect("/dashboard")
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-base">
      <AuthCard
        title="Create an account"
        googleText="Sign up with Google"
      />
    </div>
  )
}
