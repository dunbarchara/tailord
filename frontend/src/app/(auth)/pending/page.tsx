"use client"

import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Header } from "@/components/Header"

export default function PendingPage() {
  const { data: session, update } = useSession()
  const router = useRouter()
  const [checking, setChecking] = useState(false)

  // If the user was approved (e.g. after calling update()), send them to dashboard
  useEffect(() => {
    if (session?.user.status === "approved") {
      router.replace("/dashboard")
    }
  }, [session, router])

  async function handleCheckStatus() {
    setChecking(true)
    await update()
    setChecking(false)
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-base">
      <Header />
      <div className="h-14" />
      <div className="flex-1 flex items-center justify-center px-6 py-16">
      <div className="max-w-md w-full mx-auto text-center space-y-6">
        <div className="flex justify-center">
          <div className="p-4 rounded-full bg-surface-elevated border border-border-strong">
            <Clock className="h-8 w-8 text-primary" />
          </div>
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-primary">Access pending</h1>
          <p className="text-primary">
            Your account{session?.user.email ? ` (${session.user.email})` : ""} is
            awaiting approval. You'll have full access once an admin reviews your request.
          </p>
        </div>

        <Button
          onClick={handleCheckStatus}
          disabled={checking}
          variant="default"
          className="w-full"
        >
          {checking ? "Checking…" : "Check approval status"}
        </Button>
      </div>
      </div>
    </div>
  )
}
