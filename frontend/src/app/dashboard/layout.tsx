import { UserMenu } from "@/components/UserMenu"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <header className="border-b border-border px-6 py-4">
        <div className="mx-auto max-w-5xl flex justify-between">
          <span className="font-medium">Match AI</span>
          <UserMenu />
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
    </div>
  )
}
