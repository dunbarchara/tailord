import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { ChunksResponse, JobChunk } from '@/types'
import { PublicTailoringView } from './PublicTailoringView'

interface PublicTailoring {
  title: string | null
  company: string | null
  job_url: string | null
  generated_output: string
  letter_public: boolean
  posting_public: boolean
  chunks?: JobChunk[]
  created_at: string
  author_slug: string | null
  author_name: string | null
}

async function fetchPublicTailoring(
  userSlug: string,
  tailoringSlug: string
): Promise<PublicTailoring | null> {
  const baseUrl = process.env.NEXTAUTH_URL ?? 'http://localhost:3000'
  try {
    const res = await fetch(
      `${baseUrl}/api/tailorings/public/${userSlug}/${tailoringSlug}`,
      { cache: 'no-store' }
    )
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export default async function PublicTailoringPage({
  params,
}: {
  params: Promise<{ slug: string; tailoringSlug: string }>
}) {
  const { slug, tailoringSlug } = await params

  // Validate that the tailoring belongs to this user — if not, 404
  const tailoring = await fetchPublicTailoring(slug, tailoringSlug)
  if (!tailoring) {
    notFound()
  }

  // Verify the author slug in the response matches the URL slug
  if (tailoring.author_slug && tailoring.author_slug !== slug) {
    notFound()
  }

  const chunksData: ChunksResponse | null = tailoring.posting_public && tailoring.chunks
    ? { enrichment_status: 'complete', chunks: tailoring.chunks }
    : null

  return (
    <div className="min-h-screen bg-surface-base print:bg-white">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="px-6">
          <header className="pt-12 pb-5 border-b border-border-subtle print:pt-6">
            <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary mb-1">
              {tailoring.company ?? 'Tailoring'}
            </p>
            <h1 className="text-xl font-semibold text-text-primary">
              {tailoring.title ?? ''}
            </h1>
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
        </div>

        {/* Content */}
        <PublicTailoringView
          letterPublic={tailoring.letter_public}
          postingPublic={tailoring.posting_public}
          generatedOutput={tailoring.generated_output}
          chunksData={chunksData}
          title={tailoring.title}
          company={tailoring.company}
          jobUrl={tailoring.job_url}
        />

        {/* Footer */}
        <div className="px-6">
          <footer className="pt-6 pb-6 border-t border-border-subtle text-center print:hidden">
            <p className="text-text-tertiary text-xs">
              {tailoring.author_slug && tailoring.author_name && (
                <>
                  <Link href={`/u/${tailoring.author_slug}`} className="text-text-link hover:underline">
                    {tailoring.author_name}
                  </Link>
                  {' · '}
                </>
              )}
              Generated with{' '}
              <Link href="/" target="_blank" rel="noopener noreferrer" className="text-text-link hover:underline">
                Tailord
              </Link>
            </p>
          </footer>
        </div>
      </div>
    </div>
  )
}
