'use client';

import { useMemo, useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, Loader2, MousePointerClick, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChunksResponse, ExperienceChunk, GapAnalysis, JobChunk } from '@/types';
import { InlineMarkdown } from '@/components/dashboard/InlineMarkdown';
import { JobPosting } from '@/components/dashboard/JobPosting';

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface AnalysisViewProps {
  data: ChunksResponse | null;
  error: string | null;
  title?: string | null;
  company?: string | null;
  jobUrl?: string | null;
  authorName?: string | null;
  tailoringId?: string;
  gapAnalysis?: GapAnalysis | null;
  gapResponses?: ExperienceChunk[] | null;
  generationReady?: boolean;
  readOnly?: boolean;
}

interface GapAnswerFormProps {
  jobChunkId: string;
  tailoringId: string;
  question: string;
  context?: string;
  prompt?: string;
  initialValue?: string;
  buttonLabel?: string;
  readOnly?: boolean;
  onSuccess: (updatedScore: number | null, updatedRationale: string | null, blurb: string | null, submittedText: string) => void;
}

interface ChunkContextPanelProps {
  chunk: JobChunk;
  tailoringId?: string;
  gapQuestion?: { question: string; context: string } | null;
  answeredChunk?: ExperienceChunk | null;
  onScoreChange: (chunkId: string, score: number | null, rationale: string | null, blurb?: string | null) => void;
  readOnly?: boolean;
}

/* ─── Constants ──────────────────────────────────────────────────────────── */

const SOURCE_LABELS: Record<string, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct Input',
  gap_response: 'Direct Input',
};

const SCORE_CONFIG = {
  strong: {
    label: 'Strong',
    bar: 'bg-score-strong',
    dot: 'bg-score-strong',
    text: 'text-score-strong',
    badge: 'bg-score-strong/10 text-score-strong border-score-strong/20',
  },
  partial: {
    label: 'Partial',
    bar: 'bg-score-partial',
    dot: 'bg-score-partial',
    text: 'text-score-partial',
    badge: 'bg-score-partial/10 text-score-partial border-score-partial/20',
  },
  gap: {
    label: 'Gap',
    bar: 'bg-score-gap',
    dot: 'bg-score-gap',
    text: 'text-score-gap',
    badge: 'bg-score-gap/10 text-score-gap border-score-gap/20',
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

  const scored = data.chunks.filter(
    c => c.match_score !== null && c.match_score !== undefined && c.match_score !== -1 && c.should_render !== false,
  );

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

/* ─── Gap answer form ────────────────────────────────────────────────────── */

function GapAnswerForm({ jobChunkId, tailoringId, question, context, prompt, initialValue, buttonLabel = 'Save answer', readOnly = false, onSuccess }: GapAnswerFormProps) {
  const [answer, setAnswer] = useState(initialValue ?? '');
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  async function handleSubmit() {
    const trimmed = answer.trim();
    if (!trimmed) return;
    setSaving(true);
    setErrorMsg('');
    try {
      const res = await fetch('/api/experience/gap-response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_chunk_id: jobChunkId,
          tailoring_id: tailoringId,
          question,
          answer: trimmed,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setErrorMsg(data?.detail ?? 'Could not save. Please try again.');
        return;
      }
      const data = await res.json().catch(() => ({}));
      onSuccess(data?.updated_score ?? null, data?.updated_rationale ?? null, data?.advocacy_blurb ?? null, trimmed);
    } catch {
      setErrorMsg('Could not reach the server.');
    } finally {
      setSaving(false);
    }
  }

  const displayText = prompt ?? question;

  return (
    <div className="mt-3 space-y-2">

      {context && (
        <p className="text-sm text-text-tertiary leading-relaxed italic">{context}</p>
      )}
      {displayText && (
        <p className="text-sm text-text-secondary leading-relaxed">{displayText}</p>
      )}
      <textarea
        rows={3}
        placeholder="Share your experience here…"
        value={answer}
        onChange={e => setAnswer(e.target.value)}
        disabled={readOnly}
        className={cn(
          'w-full resize-none rounded-lg border border-border-default bg-surface-elevated',
          'px-3 py-2 text-sm text-text-primary placeholder:text-text-disabled',
          'focus:outline-none focus:ring-border-focus focus:border-border-focus',
          'transition-colors',
          'focus:border-text-primary',
          readOnly && 'opacity-50 cursor-not-allowed',
        )}
      />
      {errorMsg && <p className="text-sm text-error">{errorMsg}</p>}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={readOnly || saving || !answer.trim()}
          className={cn(
            'inline-flex items-center gap-1.5 h-7 px-3 rounded-[8px]',
            'bg-brand-primary text-white text-sm font-normal tracking-[-0.1px]',
            'hover:opacity-90 transition-opacity',
            'disabled:opacity-40 disabled:cursor-not-allowed',
          )}
        >
          {saving && <Loader2 className="h-3 w-3 animate-spin" />}
          {buttonLabel}
        </button>
      </div>
    </div>
  );
}

/* ─── Score summary strip ────────────────────────────────────────────────── */

function ScoreSummaryStrip({ strong, partial, gap }: { strong: number; partial: number; gap: number }) {
  return (
    <div className="sticky top-0 z-10 flex items-center justify-center gap-6 px-4 py-2.5 bg-surface-elevated border-b border-border-subtle text-xs text-text-tertiary">
      {strong > 0 && (
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-score-strong" />
          {strong} Strong
        </span>
      )}
      {partial > 0 && (
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-score-partial" />
          {partial} Partial
        </span>
      )}
      {gap > 0 && (
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-score-gap" />
          {gap} Gap
        </span>
      )}
      {strong === 0 && partial === 0 && gap === 0 && (
        <span className="text-text-disabled">No scored requirements yet</span>
      )}
    </div>
  );
}

/* ─── Default hint ───────────────────────────────────────────────────────── */

function DefaultHint() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <MousePointerClick className="h-8 w-8 text-text-disabled" />
      <p className="text-sm text-text-tertiary leading-relaxed max-w-[18rem]">
        Select a requirement from the posting to see analysis details.
      </p>
    </div>
  );
}

/* ─── Expandable text ────────────────────────────────────────────────────── */

function ExpandableText({ text, textClassName }: { text: string; textClassName?: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div>
      <p className={cn(
        'text-sm text-text-primary leading-relaxed',
        !expanded && 'line-clamp-2 overflow-hidden',
        textClassName,
      )}>
        <InlineMarkdown text={text} />
      </p>
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        className="text-[11px] font-medium text-text-disabled hover:text-text-tertiary flex items-center gap-0.5 mt-1"
      >
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        {expanded ? 'Less' : 'More'}
      </button>
    </div>
  );
}

/* ─── Chunk context panel ────────────────────────────────────────────────── */

function ChunkContextPanel({ chunk, tailoringId, gapQuestion, answeredChunk, onScoreChange, readOnly }: ChunkContextPanelProps) {
  const [rescoring, setRescoring] = useState(false);
  const [rescoreMsg, setRescoreMsg] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [localAnswer, setLocalAnswer] = useState<string | null>(null);
  const [justAnswered, setJustAnswered] = useState(false);
  const [submissionCount, setSubmissionCount] = useState(0);

  const variant = scoreToVariant(chunk.match_score);
  const config = SCORE_CONFIG[variant];
  const source = chunk.experience_source
    ? (SOURCE_LABELS[chunk.experience_source] ?? chunk.source_label ?? chunk.experience_source)
    : null;

  const hasAdvocacy = !!chunk.advocacy_blurb && variant !== 'gap';
  const hasRationale = !!chunk.match_rationale && (variant === 'partial' || variant === 'gap');

  async function handleRescore() {
    if (!tailoringId) return;
    setRescoring(true);
    setRescoreMsg(null);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/chunks/${chunk.id}/rescore`, {
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setRescoreMsg(data?.detail ?? 'Re-score failed.');
        return;
      }
      const data = await res.json();
      onScoreChange(chunk.id, data.match_score, data.match_rationale, data.advocacy_blurb);
      setRescoreMsg('Re-scored.');
      setTimeout(() => setRescoreMsg(null), 2000);
    } catch {
      setRescoreMsg('Could not reach the server.');
    } finally {
      setRescoring(false);
    }
  }

  const hasSourceRow = !!(source && variant !== 'gap');

  return (
    <div className="flex flex-col gap-0 px-4 py-8">

      <p className="text-xs text-text-tertiary uppercase tracking-wider mb-2">
            Match Card
          </p>

      {/* Structured match card */}
      <div className="rounded-md border border-border-subtle overflow-hidden">

        {/* Row 1 — Score + Requirement */}
        <div className={cn(
          'flex items-center gap-2.5 px-3 py-2.5',
          (hasAdvocacy || hasRationale || hasSourceRow) && 'border-b border-border-subtle',
        )}>
          <span className={cn(
            'inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border shrink-0',
            config.badge,
          )}>
            <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', config.dot)} />
            {config.label}
          </span>
          <p className="text-sm text-text-primary truncate overflow-hidden leading-snug flex-1 min-w-0">
            <InlineMarkdown text={chunk.content} />
          </p>
        </div>

        {/* Row 2 — Advocacy */}
        {hasAdvocacy && (
          <div className={cn(
            'px-3 py-2.5',
            (hasRationale || hasSourceRow) && 'border-b border-border-subtle',
          )}>
            <p className="text-[11px] font-medium text-text-disabled uppercase tracking-wider mb-1.5">
              Advocacy
            </p>
            <ExpandableText text={chunk.advocacy_blurb!} />
          </div>
        )}

        {/* Row 3 — Rationale */}
        {hasRationale && (
          <div className={cn(
            'px-3 py-2.5',
            hasSourceRow && 'border-b border-border-subtle',
          )}>
            <p className="text-[11px] font-medium text-text-disabled uppercase tracking-wider mb-1.5">
              Rationale
            </p>
            <ExpandableText text={chunk.match_rationale!} textClassName="italic" />
          </div>
        )}

        {/* Row 4 — Sources */}
        {hasSourceRow && (
          <div className="px-3 py-2.5">
            <p className="text-[11px] font-medium text-text-disabled uppercase tracking-wider mb-1.5">
              Sources
            </p>
            <p className="text-sm text-text-secondary">{source}</p>
          </div>
        )}

      </div>

      {/* Gap Enrichment section */}
      {variant === 'gap' && (
        <div className="mt-4">

          <p className="text-xs text-text-tertiary uppercase tracking-wider mb-2">
            Gap Enrichment
          </p>

          {readOnly && gapQuestion ? (
            <GapAnswerForm
              jobChunkId={chunk.id}
              tailoringId=""
              question={gapQuestion.question}
              context={gapQuestion.context}
              readOnly
              onSuccess={() => {}}
            />
          ) : gapQuestion && tailoringId ? (
            // Gap question mode: "You answered this" card → edit flow
            (answeredChunk || justAnswered) && !isEditing ? (
              <div className="rounded-lg border border-border-subtle bg-surface-base px-3 py-2.5 space-y-1.5">
                <p className="text-xs font-medium text-success flex items-center gap-1.5">
                  <CheckCircle2 className="h-3 w-3 shrink-0" />
                  You answered this
                </p>
                {(answeredChunk?.chunk_metadata?.question ?? gapQuestion.question) && (
                  <p className="text-sm text-text-tertiary leading-relaxed italic">
                    {answeredChunk?.chunk_metadata?.question ?? gapQuestion.question}
                  </p>
                )}
                <p className="text-sm text-text-secondary leading-relaxed">
                  {localAnswer ?? answeredChunk?.content ?? ''}
                </p>
                <button
                  type="button"
                  onClick={() => setIsEditing(true)}
                  className="text-xs text-text-link hover:underline"
                >
                  Edit answer
                </button>
              </div>
            ) : (
              <GapAnswerForm
                jobChunkId={chunk.id}
                tailoringId={tailoringId}
                question={gapQuestion.question}
                context={gapQuestion.context}
                initialValue={isEditing ? (localAnswer ?? answeredChunk?.content ?? '') : undefined}
                onSuccess={(score, rationale, blurb, text) => {
                  onScoreChange(chunk.id, score, rationale, blurb);
                  setLocalAnswer(text);
                  setJustAnswered(true);
                  setIsEditing(false);
                }}
              />
            )
          ) : tailoringId ? (
            // Additional experience mode: always show form, pre-populate, Update button
            <>
            <p className="text-sm text-text-disabled">No question available for this gap.</p>
            <GapAnswerForm
              key={submissionCount}
              jobChunkId={chunk.id}
              tailoringId={tailoringId}
              question=""
              prompt="Feel free to add any experience you think is relevant to this requirement."
              initialValue={localAnswer ?? answeredChunk?.content ?? ''}
              buttonLabel={localAnswer || answeredChunk ? 'Update' : 'Save answer'}
              onSuccess={(score, rationale, blurb, text) => {
                onScoreChange(chunk.id, score, rationale, blurb);
                setLocalAnswer(text);
                setSubmissionCount(c => c + 1);
              }}
            />
            </>
          ) : (
            <p className="text-sm text-text-disabled">No question available for this gap.</p>
          )}
        </div>
      )}

      {/* Re-score section */}
      {tailoringId && (
        <div className="mt-4">
          <p className="text-[11px] font-medium text-text-disabled uppercase tracking-wider mb-2">
            Re-score
          </p>
          <button
            type="button"
            onClick={handleRescore}
            disabled={rescoring}
            className={cn(
              'inline-flex items-center gap-1.5 h-7 px-3 rounded-[8px] text-sm',
              'border border-border-default bg-surface-elevated text-text-secondary',
              'hover:bg-surface-overlay hover:border-border-strong hover:text-text-primary',
              'transition-colors disabled:opacity-40 disabled:cursor-not-allowed',
            )}
          >
            {rescoring
              ? <Loader2 className="h-3 w-3 animate-spin" />
              : <RefreshCw className="h-3 w-3" />}
            Re-score this requirement
          </button>
          {rescoreMsg && (
            <p className={cn(
              'mt-1.5 text-xs transition-opacity',
              rescoreMsg === 'Re-scored.' ? 'text-success' : 'text-error',
            )}>
              {rescoreMsg}
            </p>
          )}
        </div>
      )}

    </div>
  );
}

/* ─── AnalysisView ───────────────────────────────────────────────────────── */

export function AnalysisView({
  data,
  error,
  title,
  company,
  jobUrl,
  authorName,
  tailoringId,
  gapAnalysis,
  gapResponses,
  generationReady,
  readOnly,
}: AnalysisViewProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scoreOverrides, setScoreOverrides] = useState<
    Map<string, { match_score: number | null; match_rationale: string | null; advocacy_blurb?: string | null }>
  >(new Map());

  const localChunks = useMemo(() => {
    const chunks = data?.chunks ?? [];
    if (scoreOverrides.size === 0) return chunks;
    return chunks.map(c => {
      const override = scoreOverrides.get(c.id);
      return override ? { ...c, ...override } : c;
    });
  }, [data, scoreOverrides]);

  const localData = useMemo(
    () => (data ? { ...data, chunks: localChunks } : null),
    [data, localChunks],
  );

  const scored = localChunks.filter(
    c => c.match_score !== null && c.match_score !== undefined && c.match_score !== -1 && c.should_render !== false,
  );
  const strongCount = scored.filter(c => c.match_score === 2).length;
  const partialCount = scored.filter(c => c.match_score === 1).length;
  const gapCount = scored.filter(c => c.match_score === 0).length;

  const selectedChunk = localChunks.find(c => c.id === selectedId) ?? null;

  const gapByChunkId = useMemo(
    () =>
      new Map(
        (gapAnalysis?.gaps ?? [])
          .filter(g => g.chunk_id)
          .map(g => [g.chunk_id!, { question: g.question_for_candidate, context: g.context }]),
      ),
    [gapAnalysis],
  );

  const answeredByChunkId = useMemo(
    () =>
      new Map(
        (gapResponses ?? [])
          .filter(c => c.chunk_metadata?.job_chunk_id)
          .map(c => [c.chunk_metadata!.job_chunk_id, c]),
      ),
    [gapResponses],
  );

  function handleScoreChange(
    chunkId: string,
    score: number | null,
    rationale: string | null,
    blurb?: string | null,
  ) {
    setScoreOverrides(prev =>
      new Map(prev).set(chunkId, { match_score: score, match_rationale: rationale, advocacy_blurb: blurb }),
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">

      <ScoreSummaryStrip strong={strongCount} partial={partialCount} gap={gapCount} />

      <div className="flex-1 flex overflow-hidden">

        {/* Left panel — 3/5 */}
        <div className="w-3/5 overflow-y-auto px-8">
          <JobPosting
            data={localData}
            error={error}
            title={title ?? null}
            company={company ?? null}
            jobUrl={jobUrl ?? null}
            authorName={authorName}
            generationReady={generationReady}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>

        {/* Right panel — 2/5 */}
        <div className="w-2/5 flex flex-col overflow-y-auto">
          {selectedChunk ? (
            <ChunkContextPanel
              chunk={selectedChunk}
              tailoringId={tailoringId}
              gapQuestion={gapByChunkId.get(selectedChunk.id) ?? null}
              answeredChunk={answeredByChunkId.get(selectedChunk.id) ?? null}
              onScoreChange={handleScoreChange}
              readOnly={readOnly}
            />
          ) : (
            <DefaultHint />
          )}
        </div>

      </div>

    </div>
  );
}
