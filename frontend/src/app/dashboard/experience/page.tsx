export default function ExperiencePage() {
  return (
    <div className="space-y-10">
      <h1 className="text-2xl font-semibold">
        Your Experience
      </h1>
      {/* Resume uploader */}
      {/* GitHub input */}
      <textarea
        placeholder="Paste or describe your experience..."
        className="w-full border rounded-lg p-4 min-h-[200px]"
      />
    </div>
  )
}
