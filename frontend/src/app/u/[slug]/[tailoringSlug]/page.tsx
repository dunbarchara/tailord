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
  author_title: string | null
  author_email: string | null
  author_linkedin: string | null
  author_profile_public: boolean
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
            authorUrl={tailoring.author_profile_public && tailoring.author_slug ? `/u/${tailoring.author_slug}` : null}
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
          authorName={tailoring.author_name}
          authorSlug={tailoring.author_slug}
          authorTitle={tailoring.author_title}
          authorEmail={tailoring.author_email}
          authorLinkedin={tailoring.author_linkedin}
          authorProfilePublic={tailoring.author_profile_public ?? false}
          sources={tailoring.sources}
        />

        {/* Footer */}
        <div className="px-6">
          <footer className="pt-6 pb-6 border-t border-border-subtle text-center print:hidden">
            <p className="text-text-tertiary text-xs">
              Generated with{' '}
              <Link href="/" className="text-text-link hover:underline">
                Tailord
              </Link>
            </p>
          </footer>
        </div>
      </div>
    </div>
  )
}
