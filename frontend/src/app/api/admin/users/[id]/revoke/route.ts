import { getServerSession } from "next-auth"
import { authOptions } from "@/lib/auth"
import { proxyToBackendWithUser } from "@/lib/proxy"

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions)
  if (!session?.user?.isAdmin) {
    return new Response(JSON.stringify({ error: "Forbidden" }), { status: 403 })
  }

  const { id } = await params
  return proxyToBackendWithUser(`admin/users/${id}/revoke`, {
    userId: session.user.id,
    userEmail: session.user.email ?? "",
    userName: session.user.name,
  })
}
