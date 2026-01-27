export default function ResultsPage({ params }: { params: { jobId: string } }) {
  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-semibold">Match Analysis</h1>
      <p className="text-muted">Job ID: {params.jobId}</p>
      <div className="border border-border rounded-lg p-6">
        <h2 className="font-medium">Why you’re a strong match</h2>
        <p className="mt-2 text-muted">Analysis output will appear here.</p>
      </div>
    </div>
  )
}
