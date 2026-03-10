import ReactMarkdown from 'react-markdown'
import Link from 'next/link'

interface PublicTailoring {
  title: string | null
  company: string | null
  job_url: string | null
  generated_output: string
  created_at: string
}

async function fetchPublicTailoring(slug: string): Promise<PublicTailoring | null> {
  const baseUrl = process.env.NEXTAUTH_URL ?? 'http://localhost:3000'
  try {
    const res = await fetch(`${baseUrl}/api/tailorings/public/${slug}`, {
      cache: 'no-store',
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export default async function PublicTailoringPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const tailoring = await fetchPublicTailoring(slug)

  if (!tailoring) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-base">
        <div className="text-center space-y-3">
          <p className="text-xl font-semibold text-text-primary">Not available</p>
          <p className="text-text-secondary text-sm">
            This tailoring is not publicly available.
          </p>
        </div>
      </div>
    )
  }

  const createdDate = new Date(tailoring.created_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return (
    <div className="min-h-screen bg-surface-base print:bg-white">
      <div className="max-w-3xl mx-auto px-6 py-12 print:py-6">
        {/* Header */}
        <header className="mb-10 pb-6 border-b border-border-subtle print:mb-6">
          <h1 className="text-3xl font-semibold text-text-primary">
            {tailoring.title ?? 'Tailoring'}
          </h1>
          <p className="text-text-secondary mt-2">
            {[tailoring.company, createdDate].filter(Boolean).join(' · ')}
          </p>
          {tailoring.job_url && (
            <a
              href={tailoring.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-2 text-sm text-text-link hover:underline print:hidden"
            >
              View job posting →
            </a>
          )}
        </header>

        {/* Content */}
        <main className="prose prose-sm max-w-none text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-strong:text-text-primary prose-hr:border-border-subtle">
          <ReactMarkdown>{tailoring.generated_output}</ReactMarkdown>
        </main>

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-border-subtle text-center print:hidden">
          <p className="text-text-tertiary text-xs">
            Generated with{' '}
            <Link href="/" className="text-text-link hover:underline">
              Tailord
            </Link>
          </p>
        </footer>
      </div>
    </div>
  )
}
