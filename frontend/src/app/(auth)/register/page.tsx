"use client"

import { AuthCard } from "@/components/AuthCard"

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-100">
      <AuthCard
        title="Create an account"
        googleText="Sign up with Google"
        emailText="Continue with email"
        showSSO={true}
        authAction="Register"
      />
    </div>
  )
}
