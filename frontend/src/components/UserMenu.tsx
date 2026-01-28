"use client"

import { useSession, signIn, signOut } from "next-auth/react"

export function UserMenu() {
  const { data: session } = useSession()

  if (!session) {
    return <button onClick={() => signIn()}>Sign in</button>
  }

  return (
    <div>
      <span>{session.user?.email}</span>
      <button onClick={() => signOut({ callbackUrl: "/" })}>Sign out</button>
    </div>
  )
}
