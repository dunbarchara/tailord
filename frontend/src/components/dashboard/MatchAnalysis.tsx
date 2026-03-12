'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChunksResponse, JobChunk } from '@/types';

interface MatchAnalysisProps {
  tailoringId: string;
}

const POLL_INTERVAL = 3000;

const SOURCE_LABELS: Record<string, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct Input',
};

function ScoreBadge({ score }: { score: number | null }) {
  if (score === 2) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-success flex-shrink-0 w-16">
        <span className="h-1.5 w-1.5 rounded-full bg-success" />
        Strong
      </span>
    );
  }
  if (score === 1) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-warning flex-shrink-0 w-16">
        <span className="h-1.5 w-1.5 rounded-full bg-warning" />
        Partial
      </span>
    );
  }
  if (score === 0) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-text-disabled flex-shrink-0 w-16">
        <span className="h-1.5 w-1.5 rounded-full bg-surface-border" />
        —
      </span>
    );
  }
  // null — not yet enriched
  return <span className="h-1.5 w-1.5 rounded-full bg-surface-border animate-pulse flex-shrink-0" />;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-text-tertiary">{label}:</span>
      <span className="text-text-primary font-mono">{value ?? <span className="text-text-disabled">—</span>}</span>
    </span>
  );
}

function ChunkRow({ chunk }: { chunk: JobChunk }) {
  const source = chunk.experience_source
    ? (SOURCE_LABELS[chunk.experience_source] ?? chunk.experience_source)
    : null;

  return (
    <div className={cn(
      'rounded border border-border-subtle bg-surface-elevated text-xs mb-2',
      chunk.match_score === 0 && 'opacity-50',
    )}>
      {/* Row 1: metadata */}
      <div className="flex items-center gap-4 px-3 py-1.5 border-b border-border-subtle bg-surface-sunken rounded-t flex-wrap">
        <Field label="id" value={<span className="text-text-tertiary">{chunk.id.slice(0, 8)}</span>} />
        <Field label="type" value={chunk.chunk_type} />
        <Field label="pos" value={chunk.position} />
        <Field label="section" value={chunk.section} />
        <Field label="score" value={<ScoreBadge score={chunk.match_score} />} />
        {source && <Field label="source" value={source} />}
      </div>
      {/* Row 2: content */}
      <div className="px-3 py-2 border-b border-border-subtle text-text-secondary leading-relaxed whitespace-pre-wrap">
        {chunk.content}
      </div>
      {/* Row 3: rationale */}
      <div className="px-3 py-1.5 text-text-tertiary italic min-h-[1.75rem]">
        {chunk.match_rationale ?? <span className="not-italic text-text-disabled">no rationale</span>}
      </div>
    </div>
  );
}

function groupBySection(chunks: JobChunk[]): Map<string, JobChunk[]> {
  const groups = new Map<string, JobChunk[]>();
  for (const chunk of chunks) {
    if (chunk.chunk_type === 'header') continue;
    const key = chunk.section ?? '';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(chunk);
  }
  return groups;
}

export function MatchAnalysis({ tailoringId }: MatchAnalysisProps) {
  const [data, setData] = useState<ChunksResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchChunks() {
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/chunks`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail ?? 'Failed to load match data.');
        stopPolling();
        return;
      }
      const json: ChunksResponse = await res.json();
      setData(json);
      if (json.enrichment_status === 'complete' || json.enrichment_status === 'error') {
        stopPolling();
      }
    } catch {
      setError('Could not reach the server.');
      stopPolling();
    }
  }

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => {
    fetchChunks();
    pollRef.current = setInterval(fetchChunks, POLL_INTERVAL);
    return () => stopPolling();
  }, [tailoringId]);

  if (error) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-text-secondary">
        <AlertCircle className="h-4 w-4 text-error flex-shrink-0" />
        {error}
      </div>
    );
  }

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
  const groups = groupBySection(data.chunks);

  return (
    <div className="max-w-3xl mx-auto px-8 py-8">

      {/* Status bar */}
      {isPending && (
        <div className="flex items-center gap-2 mb-6 text-xs text-text-secondary">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Analyzing match data…
        </div>
      )}
      {isError && (
        <div className="flex items-center gap-2 mb-6 text-xs text-error">
          <AlertCircle className="h-3.5 w-3.5" />
          Analysis failed — try regenerating this tailoring.
        </div>
      )}

      {/* No chunks yet */}
      {groups.size === 0 && !isPending && (
        <p className="text-sm text-text-tertiary">No match data available.</p>
      )}

      {/* Sections */}
      {Array.from(groups.entries()).map(([section, chunks]) => (
        <div key={section} className="mb-8">
          {section && (
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3 pb-2 border-b border-border-subtle">
              {section}
            </h3>
          )}
          <div>
            {chunks.map(chunk => (
              <ChunkRow key={chunk.id} chunk={chunk} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
