'use client';

import { useState } from 'react';
import { Info, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { groupBySection, scoreBarColor } from '@/lib/chunks';
import type { ChunksResponse, JobChunk } from '@/types';
import { InlineMarkdown } from '@/components/dashboard/InlineMarkdown';
import { TailoringErrorState } from '@/components/dashboard/TailoringErrorState';
import { TailoringHeader } from '@/components/dashboard/TailoringHeader';

interface JobPostingProps {
  data: ChunksResponse | null;
  error: string | null;
  title: string | null;
  company: string | null;
  jobUrl: string | null;
  authorName?: string | null;
  publicMode?: boolean;
  hideHeader?: boolean;
  /** Whether the main tailoring generation has finished. When false, the posting analysis hasn't started yet. */
  generationReady?: boolean;
  /** Controlled selection — set from outside (AnalysisView). When provided, inline accordion is suppressed. */
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}


/* ─── Constants ──────────────────────────────────────────────────────────── */

const SOURCE_LABELS: Record<string, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct Input',
  gap_response: 'Direct Input',
  additional_experience: 'Additional Context',
};


function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '').replace(/\*/g, '').trim();
}


function ChunkItem({
  chunk,
  expandedId,
  setExpandedId,
  publicMode,
  selectedId,
  onSelect,
}: {
  chunk: JobChunk;
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
  publicMode?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}) {
  const barColor = scoreBarColor(chunk.match_score, publicMode);
  const isInteractive = barColor !== null;

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

  // Controlled mode — used by AnalysisView split panel
  if (onSelect) {
    const isSelected = selectedId === chunk.id;
    return (
      <div
        className={cn(
          'relative mb-1.5 cursor-pointer select-none rounded px-1 -mx-1 transition-colors duration-150',
          isSelected ? 'bg-surface-sunken' : 'hover:bg-surface-sunken/50',
        )}
        onClick={() => onSelect(isSelected ? null : chunk.id)}
      >
        <div className={cn(
          'absolute top-0 bottom-0 -left-3 w-1 rounded-sm',
          barColor,
        )} />
        {body}
      </div>
    );
  }

  // Uncontrolled mode — inline accordion (Posting tab default)
  const isExpanded = expandedId === chunk.id;
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
            {chunk.advocacy_blurb && !!(chunk.experience_sources?.length || chunk.experience_source) && chunk.match_score !== 0 && (
              <hr className="my-1.5 border-border-strong" />
            )}
            {!!(chunk.experience_sources?.length || chunk.experience_source) && chunk.match_score !== 0 && (
              <p className="text-xs text-text-tertiary">
                Source:{' '}
                <span className="font-medium text-text-secondary">
                  {chunk.experience_sources?.length
                    ? chunk.experience_sources.map(s => SOURCE_LABELS[s] ?? s).join(', ')
                    : (chunk.source_label ?? chunk.experience_source)}
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
  selectedId,
  onSelect,
}: {
  section: string;
  chunks: JobChunk[];
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
  publicMode?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
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
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

export function JobPosting({ data, error, title, company, jobUrl, authorName, publicMode, hideHeader, generationReady, selectedId, onSelect }: JobPostingProps) {
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
      {!hideHeader && (
        <TailoringHeader
          company={company}
          title={title}
          jobUrl={jobUrl}
          authorName={authorName}
          className="mb-8"
        />
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
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ))
      )}
    </div>
  );
}
