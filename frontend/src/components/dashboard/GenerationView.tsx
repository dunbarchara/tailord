'use client';

import { CheckCircle2, Loader2 } from 'lucide-react';
import { formatElapsed } from '@/lib/utils';
import type { Tailoring } from '@/types';

interface GenerationViewProps {
  tailoring: Tailoring;
  regenSsePhase: string | null;
  enrichmentSettled: boolean;
  elapsed: number;
}

export function GenerationView({ tailoring, regenSsePhase, enrichmentSettled, elapsed }: GenerationViewProps) {
  const stage = tailoring.generation_stage;
  const generationComplete = tailoring.generation_status === 'ready';

  const extractingDone = stage === 'matching' || stage === 'generating' || generationComplete;
  const matchingDone = stage === 'generating' || generationComplete;

  const phases = [
    {
      key: 'extracting',
      label: 'Extracting requirements',
      done: extractingDone,
      running: stage === 'extracting',
    },
    {
      key: 'matching',
      label: 'Matching to your profile',
      done: matchingDone,
      running: stage === 'matching',
    },
    {
      key: 'generating',
      label: 'Writing your tailoring',
      done: generationComplete,
      running: stage === 'generating',
    },
    {
      key: 'enriching',
      label: 'Scoring requirements',
      done: enrichmentSettled,
      running: generationComplete && !enrichmentSettled,
    },
  ];

  const visiblePhases = phases.filter(p => p.done || p.running);

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">

      <h2 className="text-base font-medium text-text-primary mb-6">
        Generating your Tailoring — this could take a minute…
      </h2>

      {/* SSE phase — scraping during regeneration */}
      {regenSsePhase && (
        <div className="flex items-center gap-2.5 text-sm text-text-secondary">
          <Loader2 className="h-4 w-4 text-brand-primary animate-spin shrink-0" />
          {regenSsePhase === 'scraping' ? 'Fetching job posting...' : 'Updating...'}
        </div>
      )}

      {/* Backend phases */}
      {!regenSsePhase && visiblePhases.length > 0 && (
        <div className="space-y-2">
          {visiblePhases.map(({ key, label, done, running }) => (
            <div key={key} className="flex items-center gap-2.5 text-sm">
              {done
                ? <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
                : <Loader2 className="h-4 w-4 text-brand-primary animate-spin shrink-0" />}
              <span className="text-text-secondary">
                {label}{running ? '...' : ''}
                {running && elapsed > 0 && (
                  <span className="text-text-tertiary"> · {formatElapsed(elapsed)}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Fallback — before any stage is known */}
      {!regenSsePhase && visiblePhases.length === 0 && (
        <div className="flex items-center gap-2.5 text-sm text-text-secondary">
          <Loader2 className="h-4 w-4 text-brand-primary animate-spin shrink-0" />
          <span>Generating tailoring...</span>
        </div>
      )}

    </div>
  );
}
