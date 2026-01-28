import { ActionCard } from "@/components/ActionCard"
import { Header } from '@/components/Header';
import { UserMenu } from "@/components/UserMenu"

export default function DashboardPage() {
    return (
        <>
            <Header />

            <header className="border-b border-(--border)">
                <div className="mx-auto max-w-6xl px-6 py-4 flex justify-between">
                    <h1 className="font-medium">Dashboard</h1>
                    <UserMenu />
                </div>
            </header>

            <main className="mx-auto max-w-5xl px-6 py-10">
                <div className="space-y-8">
                    <h1 className="text-3xl font-semibold">What would you like to do?</h1>
                    <div className="grid sm:grid-cols-2 gap-6">
                        <ActionCard title="Update Experience" href="/dashboard/experience" />
                        <ActionCard title="Analyze Job Posting" href="/dashboard/jobs" />
                    </div>
                </div>
            </main>
        </>
    )
}
