'use client';

import { Loader2, AlertCircle, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChunksResponse, JobChunk } from '@/types';
import { InlineMarkdown } from '@/components/dashboard/InlineMarkdown';
import { TailoringErrorState } from '@/components/dashboard/TailoringErrorState';

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface FitAnalysisProps {
  data: ChunksResponse | null;
  error: string | null;
  title?: string | null;
  company?: string | null;
  jobUrl?: string | null;
}

/* ─── Constants ──────────────────────────────────────────────────────────── */

const SOURCE_LABELS: Record<string, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct Input',
};

const SCORE_CONFIG = {
  strong: {
    label: 'Strong',
    bar: 'bg-score-strong',
    dot: 'bg-score-strong',
    text: 'text-score-strong',
    sourceCls: 'bg-green-50 dark:bg-green-950/30 text-score-strong border-green-200 dark:border-green-800/40',
  },
  partial: {
    label: 'Partial',
    bar: 'bg-score-partial',
    dot: 'bg-score-partial',
    text: 'text-score-partial',
    sourceCls: 'bg-amber-50 dark:bg-amber-950/30 text-score-partial border-amber-200 dark:border-amber-800/40',
  },
  gap: {
    label: 'Gap',
    bar: 'bg-score-gap',
    dot: 'bg-score-gap',
    text: 'text-score-gap',
    sourceCls: 'bg-surface-overlay text-text-disabled border-border-subtle',
  },
} as const;

type Variant = keyof typeof SCORE_CONFIG;

function scoreToVariant(score: number | null | undefined): Variant {
  if (score === 2) return 'strong';
  if (score === 1) return 'partial';
  return 'gap';
}

/* ─── Plain-text export (used by copy button in TailoringDetail) ─────────── */

export function fitAnalysisToText(
  data: ChunksResponse,
  title?: string | null,
  company?: string | null,
): string {
  const header = [
    `Fit Analysis${title ? `: ${title}` : ''}${company ? ` @ ${company}` : ''}`,
    '─'.repeat(48),
    '',
  ].join('\n');

  const scored = data.chunks.filter(c => c.match_score !== null && c.match_score !== undefined && c.match_score !== -1);

  const lines: string[] = [];
  for (const c of scored) {
    const variant = scoreToVariant(c.match_score);
    const label = SCORE_CONFIG[variant].label.toUpperCase();
    lines.push(`[${label}] ${c.content}`);
    if (c.advocacy_blurb && variant !== 'gap') lines.push(`  → ${c.advocacy_blurb}`);
    if (c.match_rationale && (variant === 'partial' || variant === 'gap')) lines.push(`  ~ ${c.match_rationale}`);
    lines.push('');
  }

  return (header + lines.join('\n')).trim();
}

/* ─── Match card ─────────────────────────────────────────────────────────── */

function MatchCard({ chunk }: { chunk: JobChunk }) {
  const variant = scoreToVariant(chunk.match_score);
  const config = SCORE_CONFIG[variant];
  const source = chunk.experience_source
    ? (SOURCE_LABELS[chunk.experience_source] ?? chunk.experience_source)
    : null;

  return (
    <div className="px-5 py-4 flex gap-4 items-start">
      {/* Vertical score bar */}
      <div className={cn('mt-1.5 w-1 self-stretch rounded-full flex-shrink-0 min-h-[2rem]', config.bar)} />

      <div className="flex-1 min-w-0">
        {/* Score label */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className={cn(`text-xs font-medium flex items-center gap-1.5`, config.text)}>
            <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', config.dot)} />
            {config.label}
          </span>
        </div>

        {/* Requirement text */}
        <p className="text-sm text-text-primary leading-snug mb-2">
          <InlineMarkdown text={chunk.content} />
        </p>

        {/* Advocacy blurb — Strong and Partial */}
        {chunk.advocacy_blurb && variant !== 'gap' && (
          <p className="text-xs text-text-secondary leading-relaxed mb-2">
            <InlineMarkdown text={chunk.advocacy_blurb} />
          </p>
        )}

        {/* Rationale — Partial (diagnostic: why it's partial) and Gap (actionable: what's missing) */}
        {chunk.match_rationale && (variant === 'partial' || variant === 'gap') && (
          <p className={cn(
            'text-[11px] leading-relaxed mb-2',
            variant === 'partial' ? 'text-text-tertiary' : 'text-text-secondary',
          )}>
            <InlineMarkdown text={chunk.match_rationale} />
          </p>
        )}

        {/* Source tag — Strong and Partial only */}
        {source && variant !== 'gap' && (
          <span className={cn(
            'inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium border',
            config.sourceCls,
          )}>
            {source}
          </span>
        )}
      </div>
    </div>
  );
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export function FitAnalysis({ data, error, title, company, jobUrl }: FitAnalysisProps) {

  if (error) return <TailoringErrorState message={error} jobUrl={jobUrl} />;

  if (!data) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading…
      </div>
    );
  }

  const isPending = data.enrichment_status === 'pending' || data.enrichment_status === 'processing';
  const isError = data.enrichment_status === 'error';

  const scored = data.chunks.filter(c => c.match_score !== null && c.match_score !== undefined && c.match_score !== -1);
  const strong = scored.filter(c => c.match_score === 2);
  const partial = scored.filter(c => c.match_score === 1);
  const gap = scored.filter(c => c.match_score === 0);
  const hasAny = scored.length > 0;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">

      {/* Pending */}
      {isPending && (
        <div className="flex items-center gap-2 mb-6 text-sm text-text-secondary">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Analyzing your fit…
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="flex items-center gap-2 mb-6 text-sm text-error">
          <AlertCircle className="h-3.5 w-3.5" />
          Analysis failed — try regenerating this tailoring.
        </div>
      )}

      {/* No data */}
      {!hasAny && !isPending && !isError && (
        <p className="text-sm text-text-tertiary">No match data available.</p>
      )}

      {hasAny && (
        <div className="rounded-3xl border border-border-subtle bg-surface-elevated shadow-md overflow-hidden">

          {/* Header bar */}
          <div
            className="px-5 py-4 border-b border-border-subtle flex items-center justify-between gap-4"
            style={{ backgroundColor: 'var(--color-brand-accent-subtle)' }}
          >
            <div className="min-w-0">
              {company && (
                <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary mb-0.5 truncate">
                  {company}
                </p>
              )}
              {title && (
                <p className="text-sm font-semibold text-text-primary truncate">
                  {title}
                </p>
              )}
              {!company && !title && (
                <p className="text-sm font-semibold text-text-primary">Fit Analysis</p>
              )}
            </div>
            <div className="flex items-center gap-3 text-xs text-text-tertiary flex-shrink-0">
              {strong.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-score-strong" />
                  {strong.length} Strong
                </span>
              )}
              {partial.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-score-partial" />
                  {partial.length} Partial
                </span>
              )}
              {gap.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-score-gap" />
                  {gap.length} Gap
                </span>
              )}
            </div>
          </div>

          {/* Context blurb */}
          <div className="px-5 py-3 border-b border-border-subtle bg-surface-base flex items-start gap-2">
            <Info className="h-3.5 w-3.5 text-text-disabled mt-0.5 flex-shrink-0" />
            <p className="text-xs text-text-tertiary leading-relaxed">
              Requirements extracted from the job posting, scored against your saved experience.
              Strong and Partial matches include supporting evidence from your profile.
              Gaps are requirements without a direct match — add context to your experience to address them.
            </p>
          </div>

          {/* Requirement cards — in original posting order */}
          <div className="divide-y divide-border-subtle">
            {scored.map(c => (
              <MatchCard key={c.id} chunk={c} />
            ))}
          </div>

        </div>
      )}

    </div>
  );
}
