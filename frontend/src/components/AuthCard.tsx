"use client"

import { signIn } from "next-auth/react"
import { useState } from "react"

interface AuthCardProps {
  title: string
  googleText?: string
  emailText?: string
  onEmailSubmit?: (email: string) => void
  showSSO?: boolean
}

export function AuthCard({
  title,
  googleText = "Continue with Google",
  emailText = "Continue with email",
  onEmailSubmit,
  showSSO = false,
}: AuthCardProps) {
  const [email, setEmail] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (onEmailSubmit) onEmailSubmit(email)
  }

  return (
    <div className="mt-8 mx-4 sm:mx-auto p-7 max-w-md min-w-xs text-center border border-border rounded-2xl flex flex-col bg-white space-y-4">
      <h1 className="text-2xl font-semibold">{title}</h1>

      <div className="flex flex-col gap-5">
        {/* Google button */}
        <button
          onClick={() => signIn("google")}
          className="inline-flex items-center justify-center relative h-11 rounded-lg px-5 w-full gap-2 border border-border cursor-pointer hover:bg-gray-50 transition active:scale-95"
        >
          <img src="/images/google.svg" alt="Google logo" className="w-4 h-4" />
          {googleText}
        </button>

        <p className="text-text-300 text-xs uppercase">or</p>

        {/* Email form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="bg-bg-000 border border-border hover:border-border-200 placeholder:text-text-500 h-11 px-3 rounded-lg w-full"
          />

          <button
            type="submit"
            className="inline-flex items-center justify-center relative h-11 rounded-lg px-5 w-full cursor-pointer bg-gray-900 text-white hover:bg-gray-800 font-semibold active:scale-95"
          >
            {emailText}
          </button>

          {showSSO && (
            <div className="overflow-hidden transition-[max-height,opacity] duration-200 max-h-0 opacity-0">
              <button
                type="button"
                className="inline-flex items-center justify-center h-11 rounded-lg px-5 w-full border border-border cursor-pointer active:scale-95"
              >
                Continue with SSO
              </button>
            </div>
          )}
        </form>
      </div>

      {/* Footer / Privacy */}
      <div className="text-xs text-text-400 leading-relaxed mt-2">
        By continuing, you acknowledge our{" "}
        <a
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2"
          href="https://www.example.com/privacy"
        >
          Privacy Policy
        </a>{" "}
        and agree to get occasional product updates and promotional emails.
      </div>
    </div>
  )
}
