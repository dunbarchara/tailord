'use client';

import { useState } from 'react';
import { Info, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChunksResponse, JobChunk } from '@/types';
import { InlineMarkdown } from '@/components/dashboard/InlineMarkdown';
import { TailoringErrorState } from '@/components/dashboard/TailoringErrorState';

interface JobPostingProps {
  data: ChunksResponse | null;
  error: string | null;
  title: string | null;
  company: string | null;
  jobUrl: string | null;
  publicMode?: boolean;
  hideHeader?: boolean;
  /** Whether the main tailoring generation has finished. When false, the posting analysis hasn't started yet. */
  generationReady?: boolean;
}


function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '').replace(/\*/g, '').trim();
}

function scoreBarColor(score: number | null, publicMode?: boolean): string | null {
  if (score === 2) return 'bg-score-strong';
  if (score === 1) return publicMode ? 'bg-score-partial-public' : 'bg-score-partial';
  if (score === 0) return publicMode ? null : 'bg-score-gap';
  return null;
}

function groupBySection(chunks: JobChunk[]): Map<string, JobChunk[]> {
  const groups = new Map<string, JobChunk[]>();
  for (const chunk of chunks) {
    if (!chunk.display_ready) continue;
    if (chunk.should_render === false) continue;
    const key = chunk.section!;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(chunk);
  }
  return groups;
}

function ChunkItem({
  chunk,
  expandedId,
  setExpandedId,
  publicMode,
}: {
  chunk: JobChunk;
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
  publicMode?: boolean;
}) {
  const barColor = scoreBarColor(chunk.match_score, publicMode);
  const isInteractive = barColor !== null;
  const isExpanded = expandedId === chunk.id;

  const body = chunk.chunk_type === 'bullet' ? (
    <div className="flex gap-2 text-sm text-text-secondary leading-relaxed">
      <span className="text-text-tertiary flex-shrink-0 mt-0.5">·</span>
      <span><InlineMarkdown text={chunk.content} /></span>
    </div>
  ) : (
    <p className="text-sm text-text-secondary leading-relaxed">
      <InlineMarkdown text={chunk.content} />
    </p>
  );

  if (!isInteractive) {
    return <div className="mb-1.5">{body}</div>;
  }

  return (
    <div
      className={cn(
        'relative mb-1.5 cursor-pointer select-none group transition-transform duration-200',
        isExpanded ? 'translate-x-0.5' : 'hover:translate-x-0.5',
      )}
      onClick={() => setExpandedId(isExpanded ? null : chunk.id)}
    >
      {/* Score bar — counter-translates to stay fixed while content slides; grows rightward by same amount */}
      <div className={cn(
        'absolute top-0 bottom-0 -left-3 rounded-sm transition-all duration-200',
        barColor,
        isExpanded ? 'w-1 -translate-x-0.5' : 'w-0.5 group-hover:w-1 group-hover:-translate-x-0.5',
      )} />
      {body}
      {/* Expandable advocacy blurb (public) or rationale (internal) */}
      <div className={cn(
        'grid transition-all duration-200',
        isExpanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
      )}>
        <div className="overflow-hidden">
          <div className="mt-1.5 mb-0.5 px-2 py-1.5 rounded bg-surface-sunken">
            {chunk.advocacy_blurb && (
              <p className="text-xs text-text-secondary leading-relaxed">{chunk.advocacy_blurb}</p>
            )}
            {chunk.advocacy_blurb && chunk.experience_source && chunk.match_score !== 0 && (
              <hr className="my-1.5 border-border-strong" />
            )}
            {chunk.experience_source && chunk.match_score !== 0 && (
              <p className="text-xs text-text-tertiary">
                Source:{' '}
                <span className="font-medium text-text-secondary">
                  {chunk.source_label ?? chunk.experience_source}
                </span>
              </p>
            )}
            {!publicMode && chunk.match_score === 0 && chunk.match_rationale && (
              <div className="flex items-center gap-1.5 text-text-tertiary">
                <Info className="h-3.5 w-3.5 shrink-0" />
                <p className="text-xs leading-relaxed italic">{chunk.match_rationale}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionBlock({
  section,
  chunks,
  expandedId,
  setExpandedId,
  publicMode,
}: {
  section: string;
  chunks: JobChunk[];
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
  publicMode?: boolean;
}) {
  const sorted = [...chunks].sort((a, b) => a.position - b.position);
  return (
    <div className="mb-6">
      <h2 className="text-sm font-semibold text-text-primary mb-3 pb-1 border-b border-border-subtle">
        {stripMarkdown(section)}
      </h2>
      {sorted.map(chunk => (
        <ChunkItem
          key={chunk.id}
          chunk={chunk}
          expandedId={expandedId}
          setExpandedId={setExpandedId}
          publicMode={publicMode}
        />
      ))}
    </div>
  );
}

export function JobPosting({ data, error, title, company, jobUrl, publicMode, hideHeader, generationReady }: JobPostingProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (error) return <TailoringErrorState message={error} jobUrl={jobUrl} />;

  if (!data) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading…
      </div>
    );
  }

  const groups = groupBySection(data.chunks);

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      {/* Header — matches Letter/public page style */}
      {!hideHeader && (
        <header className="mb-8 pb-5 border-b border-border-subtle">
          <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary mb-1">
            {company ?? 'Company'}
          </p>
          <h1 className="text-xl font-semibold text-text-primary">
            {title ?? 'Job Posting'}
          </h1>
          {jobUrl && (
            <a
              href={jobUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-2 text-sm text-text-link hover:underline"
            >
              View job posting →
            </a>
          )}
        </header>
      )}

      {/* Sections */}
      {groups.size === 0 ? (
        <div className="text-sm text-text-tertiary">
          {(generationReady === false) || data.enrichment_status === 'pending' || data.enrichment_status === 'processing' ? (
            <div className="flex items-start gap-2.5">
              <Loader2 className="h-4 w-4 animate-spin flex-shrink-0 mt-0.5" />
              <span>
                Deeper analysis is running in the background — this view will fill in automatically when complete.
              </span>
            </div>
          ) : (
            <p className="italic">No job posting data available.</p>
          )}
        </div>
      ) : (
        Array.from(groups.entries()).map(([section, chunks]) => (
          <SectionBlock
            key={section}
            section={section}
            chunks={chunks}
            expandedId={expandedId}
            setExpandedId={setExpandedId}
            publicMode={publicMode}
          />
        ))
      )}
    </div>
  );
}
