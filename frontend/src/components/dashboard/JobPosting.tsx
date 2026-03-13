'use client';

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChunksResponse, JobChunk } from '@/types';

interface JobPostingProps {
  data: ChunksResponse | null;
  error: string | null;
  title: string | null;
  company: string | null;
  jobUrl: string | null;
}

const SOURCE_LABELS: Record<string, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct Input',
};

function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '').replace(/\*/g, '').trim();
}

// Renders **bold**, *italic*, and [text](url) inline markers as React nodes.
// Links render as their anchor text only (no href) — the Posting view is for
// reading, not navigation. The "View job posting →" header link covers that.
// Chunk data is left unchanged — styling lives in the render layer.
function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="font-medium text-text-primary">{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('*') && part.endsWith('*')) {
          return <em key={i}>{part.slice(1, -1)}</em>;
        }
        const linkMatch = part.match(/^\[([^\]]+)\]\([^)]+\)$/);
        if (linkMatch) {
          return linkMatch[1].replace(/\*\*/g, '').replace(/\*/g, '');
        }
        return part;
      })}
    </>
  );
}

// Matches bare markdown links like [text](url) or ![alt](url) with no surrounding content
const NOISE_PATTERN = /^(\[.+\]\(.+\)|!\[.*\]\(.+\))$/;
function isPatternNoise(content: string): boolean {
  return NOISE_PATTERN.test(content.trim());
}

function scoreBarColor(score: number | null): string | null {
  if (score === 2) return 'bg-score-strong';
  if (score === 1) return 'bg-score-partial';
  if (score === 0) return 'bg-score-gap';
  return null;
}

function groupBySection(chunks: JobChunk[]): Map<string, JobChunk[]> {
  const groups = new Map<string, JobChunk[]>();
  for (const chunk of chunks) {
    if (chunk.chunk_type === 'header') continue;
    if (chunk.section === null) continue;
    if (isPatternNoise(chunk.content)) continue;
    if (chunk.should_render === false) continue;
    const key = chunk.section;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(chunk);
  }
  return groups;
}

function ChunkItem({
  chunk,
  expandedId,
  setExpandedId,
}: {
  chunk: JobChunk;
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
}) {
  const barColor = scoreBarColor(chunk.match_score);
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
    return (
      <div className="flex gap-2 mb-1.5">
        <div className="w-0.5 flex-shrink-0" />
        <div className="flex-1">{body}</div>
      </div>
    );
  }

  return (
    <div
      className="flex gap-2 mb-1.5 cursor-pointer select-none group"
      onClick={() => setExpandedId(isExpanded ? null : chunk.id)}
    >
      {/* Score bar — expands on hover */}
      <div className={cn('flex-shrink-0 rounded-sm transition-all duration-200', barColor, isExpanded ? 'w-1' : 'w-0.5 group-hover:w-1')} />
      <div className="flex-1">
        {body}
        {/* Expandable rationale — grid trick for smooth height animation */}
        <div className={cn(
          'grid transition-all duration-200',
          isExpanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}>
          <div className="overflow-hidden">
            <div className="mt-1.5 mb-0.5 px-2 py-1.5 rounded bg-surface-sunken">
              {chunk.match_rationale && (
                <p className="text-xs text-text-tertiary leading-relaxed">{chunk.match_rationale}</p>
              )}
              {chunk.match_rationale && chunk.experience_source && (
                <hr className="my-1.5 border-border-strong" />
              )}
              {chunk.experience_source && (
                <p className="text-xs text-text-tertiary">
                  Source:{' '}
                  <span className="font-medium text-text-secondary">
                    {SOURCE_LABELS[chunk.experience_source] ?? chunk.experience_source}
                  </span>
                </p>
              )}
            </div>
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
}: {
  section: string;
  chunks: JobChunk[];
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
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
        />
      ))}
    </div>
  );
}

export function JobPosting({ data, error, title, company, jobUrl }: JobPostingProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-8 py-10 text-sm text-text-secondary">
        Could not load job posting data.
      </div>
    );
  }

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
    <div className="max-w-3xl mx-auto px-8 py-10">
      {/* Header — matches Letter/public page style */}
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

      {/* Sections */}
      {groups.size === 0 ? (
        <p className="text-sm text-text-tertiary italic">No job posting data available.</p>
      ) : (
        Array.from(groups.entries()).map(([section, chunks]) => (
          <SectionBlock
            key={section}
            section={section}
            chunks={chunks}
            expandedId={expandedId}
            setExpandedId={setExpandedId}
          />
        ))
      )}
    </div>
  );
}
