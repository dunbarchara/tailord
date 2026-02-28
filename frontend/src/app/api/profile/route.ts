import { proxyToBackend } from '@/lib/proxy'

export async function POST(req: Request) {
  return proxyToBackend('profile', await req.text())
}
