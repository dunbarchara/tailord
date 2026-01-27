import { ActionCard } from "@/components/ActionCard"

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-semibold">What would you like to do?</h1>
      <div className="grid sm:grid-cols-2 gap-6">
        <ActionCard title="Update Experience" href="/dashboard/experience" />
        <ActionCard title="Analyze Job Posting" href="/dashboard/jobs" />
      </div>
    </div>
  )
}
