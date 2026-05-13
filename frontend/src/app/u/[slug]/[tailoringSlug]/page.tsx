import { cache } from 'react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import type { ChunksResponse, JobChunk } from '@/types'
import { PublicTailoringView } from './PublicTailoringView'
import { TailoringHeader } from '@/components/dashboard/TailoringHeader'

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
  sources?: {
    has_resume: boolean
    github_repos: Array<{ name: string; url: string }>
  }
}

// cache() deduplicates the fetch across generateMetadata + the page component
const fetchPublicTailoring = cache(async function fetchPublicTailoring(
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
})

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; tailoringSlug: string }>
}): Promise<Metadata> {
  const { slug, tailoringSlug } = await params
  const tailoring = await fetchPublicTailoring(slug, tailoringSlug)

  if (!tailoring) {
    return { title: 'Tailoring Not Found — Tailord' }
  }

  const name = tailoring.author_name ?? slug
  const roleDesc = tailoring.title
    ? `${tailoring.title}${tailoring.company ? ` at ${tailoring.company}` : ''}`
    : tailoring.company ?? null

  return {
    title: `${name} — Tailoring — Tailord`,
    description: roleDesc
      ? `${name}'s tailored application for ${roleDesc}.`
      : `${name}'s tailored application on Tailord.`,
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
    <div className="min-h-screen bg-surface-elevated print:bg-white" style={{ fontFamily: "ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'", WebkitFontSmoothing: 'antialiased' }}>
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="px-6">
          <TailoringHeader
            company={tailoring.company}
            title={tailoring.title}
            jobUrl={tailoring.job_url}
            authorName={tailoring.author_name}
            className="pt-12 print:pt-6"
          />
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
          <footer className="pt-6 pb-6 border-t border-border-subtle text-center print:hidden space-y-1.5">
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
            {tailoring.sources && (tailoring.sources.has_resume || tailoring.sources.github_repos.length > 0) && (
              <p className="text-text-disabled text-xs flex items-center justify-center flex-wrap gap-x-2 gap-y-1">
                <span>Sources:</span>
                {tailoring.sources.has_resume && (
                  <span>📄 Resume</span>
                )}
                {tailoring.sources.github_repos.map((repo) => (
                  <a
                    key={repo.url}
                    href={repo.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-link hover:underline"
                  >
                    {repo.url.replace(/^https?:\/\//, '')}
                  </a>
                ))}
              </p>
            )}
          </footer>
        </div>
      </div>
    </div>
  )
}
