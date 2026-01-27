export default function JobsPage() {
  return (
    <form className="max-w-xl space-y-6">
      <h1 className="text-2xl font-semibold">Analyze a job posting</h1>
      <input
        type="url"
        placeholder="https://company.com/jobs/..."
        className="w-full border px-4 py-3 rounded-lg"
      />
      <button className="bg-primary text-white px-6 py-3 rounded-lg">Analyze</button>
    </form>
  )
}
