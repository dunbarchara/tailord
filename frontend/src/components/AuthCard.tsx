"use client"

import Image from "next/image"
import { signIn } from "next-auth/react"
import { Button } from "@/components/ui/button"

interface AuthCardProps {
  title: string
  googleText?: string
}

export function AuthCard({
  title,
  googleText = "Continue with Google",
}: AuthCardProps) {
  return (
    <div className="mt-8 mx-auto p-7 max-w-md min-w-xs text-center border border-border-default rounded-2xl flex flex-col bg-surface-elevated space-y-6 text-text-primary">
      <h1 className="text-2xl font-semibold">{title}</h1>

      <Button
        variant="outline"
        className="w-full h-11 gap-2"
        onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
      >
        <Image src="/images/google.svg" alt="Google logo" width={16} height={16} />
        {googleText}
      </Button>

      <p className="text-xs text-text-tertiary leading-relaxed">
        By continuing, you acknowledge our{" "}
        <a
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2"
          href="/"
        >
          Privacy Policy
        </a>{" "}
        and agree to get occasional product updates.
      </p>
    </div>
  )
}
