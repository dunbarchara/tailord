"use client"

import { AuthCard } from "@/components/AuthCard"

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-100">
      <AuthCard
        title="Sign in"
        googleText="Sign in with Google"
        emailText="Continue with email"
        onEmailSubmit={(email) => alert(`Login submitted for: ${email}`)}
      />
    </div>
  )
}
