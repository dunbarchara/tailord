'use client'

import { useState } from 'react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import { cn } from '@/lib/utils'
import { JobPosting } from '@/components/dashboard/JobPosting'
import type { ChunksResponse, LetterContent, AdvocacyStatement } from '@/types'

interface PublicTailoringViewProps {
  letterPublic: boolean
  postingPublic: boolean
  generatedOutput: string
  letterContent?: LetterContent | null
  chunksData: ChunksResponse | null
  title: string | null
  company: string | null
  jobUrl: string | null
  authorName: string | null
  authorSlug: string | null
  authorTitle: string | null
  authorEmail: string | null
  authorLinkedin: string | null
  authorProfilePublic: boolean
  sources?: { has_resume: boolean; github_repos: Array<{ name: string; url: string }> }
}

function stripBriefFooter(output: string): string {
  const lines = output.split('\n')
  let i = lines.length - 1
  while (i >= 0 && !lines[i].trim()) i--
  if (lines[i]?.trim().startsWith('*') && lines[i]?.trim().endsWith('*')) {
    i--
    while (i >= 0 && !lines[i].trim()) i--
    if (/^[-*_]{3,}$/.test(lines[i]?.trim() ?? '')) {
      i--
    }
    return lines.slice(0, i + 1).join('\n').trimEnd()
  }
  return output
}

function SourceTags({ sources }: { sources: string[] }) {
  if (!sources.length) return null
  return (
    <span className="text-xs text-text-tertiary ml-1">
      {sources.map((s) => `[${s}]`).join(' ')}
    </span>
  )
}

function StructuredLetterBody({
  statements,
  closing,
  company,
  jobTitle,
  jobUrl,
  candidateName,
  candidateEmail,
}: {
  statements: AdvocacyStatement[]
  closing: string
  company: string | null
  jobTitle: string | null
  jobUrl: string | null
  candidateName: string | null
  candidateEmail: string | null
}) {
  const firstName = candidateName?.split(' ')[0] ?? candidateName
  const jobTitleDisplay = jobUrl
    ? <a href={jobUrl} target="_blank" rel="noopener noreferrer">{jobTitle}</a>
    : <span>{jobTitle}</span>

  return (
    <>
      <p><strong>Hello {company},</strong></p>
      <p>
        Given the requirements in your {jobTitleDisplay} job posting, here are some reasons <strong>{candidateName}</strong> would be a strong fit for the role.
      </p>
      <hr />
      {statements.map((stmt, i) => (
        <div key={i}>
          <p><strong>{stmt.header}</strong></p>
          <p>
            <ReactMarkdown components={{ p: ({ children }) => <>{children}</> }}>
              {stmt.body}
            </ReactMarkdown>
            <SourceTags sources={stmt.sources} />
          </p>
        </div>
      ))}
      <hr />
      <ReactMarkdown>{closing}</ReactMarkdown>
      {candidateEmail && (
        <p>
          If you&apos;re interested in continuing the conversation, {firstName} can be reached at{' '}
          <a href={`mailto:${candidateEmail}`}>{candidateEmail}</a>.
        </p>
      )}
    </>
  )
}

interface CandidateFooterProps {
  authorName: string | null
  authorSlug: string | null
  authorTitle: string | null
  authorEmail: string | null
  authorLinkedin: string | null
  authorProfilePublic: boolean
  sources?: { has_resume: boolean; github_repos: Array<{ name: string; url: string }> }
}

function CandidateFooter({
  authorName, authorSlug, authorTitle, authorEmail, authorLinkedin, authorProfilePublic, sources,
}: CandidateFooterProps) {
  const authorProfileUrl = authorProfilePublic && authorSlug ? `/u/${authorSlug}` : null
  const hasSources = sources && (sources.has_resume || sources.github_repos.length > 0)
  const hasContactInfo = authorName || authorTitle || authorEmail || authorLinkedin

  if (!hasContactInfo && !hasSources) return null

  return (
    <div className="px-6 pb-8 space-y-1.5">
      {hasSources && (
        <p className="text-text-tertiary text-xs flex flex-wrap items-center gap-x-1.5">
          <span className="text-text-secondary">Sources:</span>
          {sources!.has_resume && <span>[Resume]</span>}
          {sources!.github_repos.map((repo) => (
            <a
              key={repo.url}
              href={repo.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-link hover:underline"
            >
              [GitHub – {repo.name}]
            </a>
          ))}
        </p>
      )}
      {hasContactInfo && (
        <p className="text-text-tertiary text-xs flex flex-wrap items-center gap-x-1.5">
          {authorName && (
            authorProfileUrl ? (
              <Link href={authorProfileUrl} className="text-text-link hover:underline">{authorName}</Link>
            ) : (
              <span>{authorName}</span>
            )
          )}
          {authorName && authorTitle && <span className="text-text-disabled">·</span>}
          {authorTitle && <span>{authorTitle}</span>}
          {(authorName || authorTitle) && authorEmail && <span className="text-text-disabled">·</span>}
          {authorEmail && (
            <a href={`mailto:${authorEmail}`} className="text-text-link hover:underline">{authorEmail}</a>
          )}
          {(authorName || authorTitle || authorEmail) && authorLinkedin && <span className="text-text-disabled">·</span>}
          {authorLinkedin && (
            <a href={authorLinkedin} target="_blank" rel="noopener noreferrer" className="text-text-link hover:underline">LinkedIn</a>
          )}
        </p>
      )}

    </div>
  )
}

export function PublicTailoringView({
  letterPublic,
  postingPublic,
  generatedOutput,
  letterContent,
  chunksData,
  title,
  company,
  jobUrl,
  authorName,
  authorSlug,
  authorTitle,
  authorEmail,
  authorLinkedin,
  authorProfilePublic,
  sources,
}: PublicTailoringViewProps) {
  const bothPublic = letterPublic && postingPublic
  const [activeTab, setActiveTab] = useState<'letter' | 'posting'>(
    postingPublic ? 'posting' : 'letter'
  )

  const showLetter = letterPublic && (!bothPublic || activeTab === 'letter')
  const showPosting = postingPublic && (!bothPublic || activeTab === 'posting')

  const candidateFooterProps: CandidateFooterProps = {
    authorName, authorSlug, authorTitle, authorEmail, authorLinkedin, authorProfilePublic, sources,
  }
  const hasCandidateFooter = !!(authorName || authorTitle || authorEmail || authorLinkedin ||
    (sources && (sources.has_resume || sources.github_repos.length > 0)))

  return (
    <>
      {/* Tab switcher — only when both views are public */}
      {bothPublic && (
        <div className="px-6">
        <div className="flex items-center gap-0 border-b border-border-subtle">
          {(['posting', 'letter'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors',
                activeTab === tab
                  ? 'border-brand-primary text-text-primary'
                  : 'border-transparent text-text-tertiary hover:text-text-secondary'
              )}
            >
              {tab === 'letter' ? 'Advocacy Letter' : 'Job Posting'}
            </button>
          ))}
        </div>
        </div>
      )}

      {/* Letter view */}
      {showLetter && (
        <main className="px-6 pt-10 mb-6 prose prose-sm max-w-none text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-strong:text-text-primary prose-hr:border-border-subtle prose-hr:my-6 prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs prose-a:text-text-link prose-a:underline prose-a:underline-offset-2">
          {letterContent ? (
            <StructuredLetterBody
              statements={letterContent.advocacy_statements}
              closing={letterContent.closing}
              company={company}
              jobTitle={title}
              jobUrl={jobUrl}
              candidateName={authorName}
              candidateEmail={authorEmail}
            />
          ) : (
            <ReactMarkdown
              components={{
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
                ),
              }}
            >
              {stripBriefFooter(generatedOutput)}
            </ReactMarkdown>
          )}
        </main>
      )}

      {/* Posting view — JobPosting handles its own px-6 py-10 padding */}
      {showPosting && (
        <JobPosting
          data={chunksData}
          error={null}
          title={title}
          company={company}
          jobUrl={jobUrl}
          publicMode={true}
          hideHeader={true}
        />
      )}

      {/* Candidate footer — hr above for both views (letter markdown no longer includes it) */}
      {hasCandidateFooter && (
        <>
          <div className="px-6">
            <hr className="border-border-subtle pb-6" />
          </div>
          <CandidateFooter {...candidateFooterProps} />
        </>
      )}
    </>
  )
}
