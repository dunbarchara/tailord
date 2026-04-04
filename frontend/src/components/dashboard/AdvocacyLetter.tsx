'use client';

import { CheckCircle2, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { cn, formatElapsed } from '@/lib/utils';
import { TailoringErrorState } from '@/components/dashboard/TailoringErrorState';
import { TailoringHeader } from '@/components/dashboard/TailoringHeader';
import type { Tailoring } from '@/types';

const REGEN_SSE_LABELS: Record<string, string> = {
  scraping: 'Fetching job posting...',
};

interface AdvocacyLetterProps {
  tailoring: Tailoring;
  regenSsePhase: string | null;
  generationFailed: boolean;
  authorName?: string | null;
}

export function AdvocacyLetter({ tailoring, regenSsePhase, generationFailed, authorName }: AdvocacyLetterProps) {
  if (generationFailed) {
    return (
      <TailoringErrorState
        message={tailoring.generation_error ?? 'Generation failed — try regenerating this tailoring.'}
        jobUrl={tailoring.job_url}
      />
    );
  }

  const stage = tailoring.generation_stage;
  const startedAt = tailoring.generation_started_at
    ? new Date(tailoring.generation_started_at).getTime()
    : null;
  const totalElapsed = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0;
  const matchingDone = stage === 'generating';
  const extractingDone = stage === 'matching' || stage === 'generating';
  const phases = [
    { key: 'extracting', label: 'Extracting requirements', done: extractingDone, running: stage === 'extracting' },
    { key: 'matching', label: 'Matching to your profile', done: matchingDone, running: stage === 'matching' },
    { key: 'generating', label: 'Writing your tailoring', done: false, running: stage === 'generating' },
  ];

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <TailoringHeader
        company={tailoring.company}
        title={tailoring.title}
        jobUrl={tailoring.job_url}
        authorName={authorName}
        className="mb-8"
      />

      {regenSsePhase && (
        <div className="flex items-center gap-2 mb-6 text-sm text-text-secondary animate-fade-in">
          <Loader2 className="h-4 w-4 text-brand-primary animate-spin flex-shrink-0" />
          {REGEN_SSE_LABELS[regenSsePhase] ?? 'Updating…'}
        </div>
      )}

      {tailoring.generation_status === 'generating' && !regenSsePhase && (
        <div className="space-y-2 mb-8 animate-fade-in">
          {phases.filter(({ done, running }) => done || running).map(({ key, label, done, running }) => (
            <div key={key} className="flex items-center gap-2.5 text-sm">
              {done
                ? <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0" />
                : <Loader2 className="h-4 w-4 text-brand-primary animate-spin flex-shrink-0" />}
              <span className="text-text-secondary">
                {label}{running ? '...' : ''}
                {running && startedAt && (
                  <span className="text-text-tertiary"> · {formatElapsed(totalElapsed)}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {tailoring.generated_output && (
        <div className={cn(
          'prose prose-sm max-w-none text-text-primary',
          'prose-headings:text-text-primary prose-headings:font-semibold',
          'prose-p:text-text-secondary prose-p:leading-relaxed',
          'prose-hr:my-6',
          'prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs',
          'prose-strong:text-text-primary',
          'prose-hr:border-border-subtle',
          'prose-a:text-text-link prose-a:underline prose-a:underline-offset-2',
          tailoring.generation_status === 'generating' && 'opacity-40',
        )}>
          <ReactMarkdown>{tailoring.generated_output}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
