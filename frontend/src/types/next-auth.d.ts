// This file augments next-auth types. The export {} ensures it's treated as a module.
export {}

declare module "next-auth" {
  interface Session {
    user: {
      id: string
      status: string
      name?: string | null
      email?: string | null
      image?: string | null
    }
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    status?: string
  }
}
