import { redirect } from "next/navigation"
import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { env } from "@/lib/env"
import { AdminView } from "./AdminView"

export interface AdminUser {
  id: string
  email: string
  name: string | null
  avatar_url: string | null
  status: string
  is_admin: boolean
  created_at: string
}

async function fetchAdminUsers(userId: string, userEmail: string): Promise<AdminUser[]> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/admin/users`, {
      headers: {
        "X-API-Key": env.apiKey,
        "X-User-Id": userId,
        "X-User-Email": userEmail,
      },
      cache: "no-store",
    })
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export default async function AdminPage() {
  const session = await getServerSession(authOptions)

  if (!session?.user?.isAdmin) {
    redirect("/dashboard")
  }

  const users = await fetchAdminUsers(session.user.id, session.user.email ?? "")

  return <AdminView users={users} />
}
