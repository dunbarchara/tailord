function requireEnv(key: string): string {
  const val = process.env[key]
  if (!val) throw new Error(`Missing required env var: ${key}`)
  return val
}

export const env = {
  apiBaseUrl: requireEnv('API_BASE_URL'),
  apiKey: requireEnv('API_KEY'),
} as const
