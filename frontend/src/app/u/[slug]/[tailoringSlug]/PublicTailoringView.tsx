'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { cn } from '@/lib/utils'
import { JobPosting } from '@/components/dashboard/JobPosting'
import type { ChunksResponse } from '@/types'

interface PublicTailoringViewProps {
  letterPublic: boolean
  postingPublic: boolean
  generatedOutput: string
  chunksData: ChunksResponse | null
  title: string | null
  company: string | null
  jobUrl: string | null
}

function extractBriefFooter(generatedOutput: string): string | null {
  const lastLine = generatedOutput.split('\n').map(l => l.trim()).filter(Boolean).at(-1) ?? ''
  // The brief footer is always the last line, formatted as *Name · ...*
  return lastLine.startsWith('*') && lastLine.endsWith('*') ? lastLine : null
}

export function PublicTailoringView({
  letterPublic,
  postingPublic,
  generatedOutput,
  chunksData,
  title,
  company,
  jobUrl,
}: PublicTailoringViewProps) {
  const bothPublic = letterPublic && postingPublic
  const [activeTab, setActiveTab] = useState<'letter' | 'posting'>(
    postingPublic ? 'posting' : 'letter'
  )

  const showLetter = letterPublic && (!bothPublic || activeTab === 'letter')
  const showPosting = postingPublic && (!bothPublic || activeTab === 'posting')
  const briefFooter = extractBriefFooter(generatedOutput)

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
        <main className="px-6 py-10 prose prose-sm max-w-none text-text-primary prose-headings:text-text-primary prose-headings:font-semibold prose-p:text-text-secondary prose-p:leading-relaxed prose-strong:text-text-primary prose-hr:border-border-subtle prose-hr:my-6 prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs prose-a:text-text-link prose-a:underline prose-a:underline-offset-2">
          <ReactMarkdown>{generatedOutput}</ReactMarkdown>
        </main>
      )}

      {/* Posting view — JobPosting handles its own px-6 py-10 padding */}
      {showPosting && (
        <>
          <JobPosting
            data={chunksData}
            error={null}
            title={title}
            company={company}
            jobUrl={jobUrl}
            publicMode={true}
            hideHeader={true}
          />
          {briefFooter && (
            <div className="px-6 pb-8 prose prose-sm max-w-none prose-p:text-text-secondary prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs prose-a:text-text-link prose-a:underline prose-a:underline-offset-2">
              <ReactMarkdown>{briefFooter}</ReactMarkdown>
            </div>
          )}
        </>
      )}
    </>
  )
}
