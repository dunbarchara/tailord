"use client"

import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useEffect } from "react"
import { Loader2 } from "lucide-react"
import { Header } from "@/components/Header"

export default function CheckingPage() {
  const { data: session, update } = useSession()
  const router = useRouter()

  useEffect(() => {
    if (session?.user.status === "approved") {
      router.replace("/dashboard")
      return
    }
    if (session?.user.status === "pending") {
      router.replace("/pending")
      return
    }

    // Still checking — poll every 3 seconds
    const interval = setInterval(() => update(), 3000)
    return () => clearInterval(interval)
  }, [session, router, update])

  return (
    <div className="min-h-screen flex flex-col bg-surface-base">
      <Header />
      <div className="h-14" />
      <div className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto" />
          <p className="text-primary font-medium">Setting up your account…</p>
          <p className="text-secondary text-sm">This only takes a moment.</p>
        </div>
      </div>
    </div>
  )
}
