import { proxyToBackend } from '@/lib/proxy'

export async function POST(req: Request) {
  return proxyToBackend('generate', await req.text())
}
