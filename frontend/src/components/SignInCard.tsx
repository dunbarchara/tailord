"use client"

import { signIn } from "next-auth/react"
import { useState } from "react"

export function SignInCard() {
  const [email, setEmail] = useState("")

  const handleEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    alert(`Email login submitted: ${email}`)
  }

  return (
    <div className="mt-8 mx-4 sm:mx-auto p-7 max-w-md min-w-xs text-center border border-border rounded-2xl flex flex-col bg-bg-100 shadow-lg space-y-4">
      <div className="flex flex-col gap-5">
        {/* Google login button */}
        <button
          onClick={() => signIn("google")}
          className="inline-flex items-center justify-center relative h-11 rounded-lg px-5 w-full gap-2 border border-border hover:bg-gray-50 transition active:scale-95 cursor-pointer"
        >
          <img
            src="/images/google.svg"
            alt="Google logo"
            className="w-4 h-4"
          />
          Continue with Google
        </button>

        <p className="text-text-300 text-xs uppercase">or</p>

        {/* Email login form */}
        <form onSubmit={handleEmailSubmit} className="flex flex-col gap-4">
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
            className="inline-flex items-center justify-center relative h-11 rounded-lg px-5 w-full bg-primary text-white font-semibold active:scale-95"
          >
            Continue with email
          </button>

          {/* Optional hidden SSO button (expandable) */}
          <div className="overflow-hidden transition-[max-height,opacity] duration-200 max-h-0 opacity-0">
            <button
              type="button"
              className="inline-flex items-center justify-center h-11 rounded-lg px-5 w-full border border-border active:scale-95 cursor-pointer"
            >
              Continue with SSO
            </button>
          </div>
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
