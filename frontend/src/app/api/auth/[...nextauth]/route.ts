import NextAuth from "next-auth"
import { authOptions } from "@/lib/auth"
import { NextRequest } from "next/server"

const authHandler = NextAuth(authOptions)

// Rewrite the request URL using forwarded headers so NextAuth sees the
// correct public-facing URL (https://tailord.app) instead of the internal
// container URL. Required when running behind Cloudflare + Azure Container Apps.
function trustProxy(req: NextRequest): NextRequest {
  const proto = req.headers.get("x-forwarded-proto") ?? "https"
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host")
  if (!host) return req
  const url = new URL(req.url)
  url.protocol = proto + ":"
  url.host = host
  return new NextRequest(url.toString(), req)
}

export function GET(req: NextRequest, context: { params: Promise<{ nextauth: string[] }> }) {
  return authHandler(trustProxy(req), context)
}

export function POST(req: NextRequest, context: { params: Promise<{ nextauth: string[] }> }) {
  return authHandler(trustProxy(req), context)
}
