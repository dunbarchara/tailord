"use client"

import { signOut, useSession } from "next-auth/react"

export function UserMenu() {
  const { data: session } = useSession()

  if (!session) {
    return null
  }

  return (
    <div className="flex items-center gap-4">
      <span>{session.user?.name}</span>
      <button
        onClick={() => signOut()}
        className="text-sm text-primary underline"
      >
        Sign out
      </button>
    </div>
  )
}
