'use client';

import { useEffect, useState } from 'react';
import { Copy, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import { ChunkAnalysis, chunksToMarkdown } from '@/components/dashboard/ChunkAnalysis';
import type { ChunksResponse, GapAnalysis } from '@/types';

/* ─── Types ──────────────────────────────────────────────────────────────── */

interface DebugInfo {
  model: string | null;
  matching_mode: 'vector' | 'llm' | null;
  generation_duration_ms: number | null;
  chunk_batch_count: number | null;
  chunk_error_count: number | null;
  formatted_profile: string;
  profile_snapshot_source: 'snapshot' | 'reconstructed';
  chunk_matching_system_prompt: string;
  sample_chunk_user_message: string;
  tailoring_system_prompt: string | null;
  gap_analysis: GapAnalysis | null;
  gap_analysis_system_prompt: string | null;
}

interface DebugPanelProps {
  tailoringId: string;
  chunksData: ChunksResponse | null;
  chunksError: string | null;
  title?: string | null;
  company?: string | null;
  jobUrl?: string | null;
}

/* ─── Copy button ─────────────────────────────────────────────────────────── */

function CopyButton({ getText }: { getText: () => string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(getText());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? 'Copied!' : 'Copy'}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium border border-border-default bg-surface-elevated text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors"
    >
      {copied
        ? <><CheckCircle2 className="h-3 w-3 text-success" /> Copied</>
        : <><Copy className="h-3 w-3" /> Copy</>}
    </button>
  );
}

/* ─── Section wrapper ────────────────────────────────────────────────────── */

function DebugSection({
  label,
  badge,
  children,
  onCopy,
}: {
  label: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  onCopy: () => string;
}) {
  return (
    <section className="mb-10">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-medium uppercase tracking-widest text-text-tertiary">{label}</h2>
          {badge}
        </div>
        <CopyButton getText={onCopy} />
      </div>
      {children}
    </section>
  );
}

/* ─── Code block ─────────────────────────────────────────────────────────── */

function CodeBlock({ text }: { text: string }) {
  return (
    <pre className="text-xs text-text-secondary leading-relaxed bg-surface-base border border-border-subtle rounded-xl p-4 overflow-x-auto whitespace-pre-wrap break-words font-mono">
      {text}
    </pre>
  );
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export function DebugPanel({ tailoringId, chunksData, chunksError, title, company, jobUrl }: DebugPanelProps) {
  const [debugInfo, setDebugInfo] = useState<DebugInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    fetch(`/api/tailorings/${tailoringId}/debug`)
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(setDebugInfo)
      .catch(() => setError('Failed to load debug info'))
      .finally(() => setLoading(false));
  }, [tailoringId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading debug info…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-text-secondary">
        <AlertCircle className="h-4 w-4 text-error" />
        {error}
      </div>
    );
  }

  const header = [
    `# Debug — ${title ?? 'Tailoring'}${company ? ` @ ${company}` : ''}`,
    debugInfo?.model ? `Model: ${debugInfo.model}` : null,
  ].filter(Boolean).join('\n');

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">

      {/* Meta */}
      {debugInfo && (
        <div className="mb-8 flex flex-wrap items-center gap-x-4 gap-y-2">
          {debugInfo.model && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-tertiary">Model</span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium bg-surface-overlay border border-border-subtle text-text-secondary">
                {debugInfo.model}
              </span>
            </div>
          )}
          {debugInfo.matching_mode && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-tertiary">Matching</span>
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium border ${
                debugInfo.matching_mode === 'vector'
                  ? 'bg-blue-100 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800/40 text-blue-700 dark:text-blue-400'
                  : 'bg-surface-overlay border-border-subtle text-text-secondary'
              }`}>
                {debugInfo.matching_mode}
              </span>
            </div>
          )}
          {debugInfo.generation_duration_ms != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-tertiary">Generation</span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium bg-surface-overlay border border-border-subtle text-text-secondary">
                {debugInfo.generation_duration_ms >= 1000
                  ? `${(debugInfo.generation_duration_ms / 1000).toFixed(1)}s`
                  : `${debugInfo.generation_duration_ms}ms`}
              </span>
            </div>
          )}
          {debugInfo.chunk_batch_count != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-tertiary">Batches</span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium bg-surface-overlay border border-border-subtle text-text-secondary">
                {debugInfo.chunk_batch_count}
              </span>
            </div>
          )}
          {debugInfo.chunk_error_count != null && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-tertiary">Batch errors</span>
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium border ${
                debugInfo.chunk_error_count > 0
                  ? 'bg-error-bg border-error text-error'
                  : 'bg-surface-overlay border-border-subtle text-text-secondary'
              }`}>
                {debugInfo.chunk_error_count}
              </span>
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-text-tertiary">Gap analysis</span>
            {debugInfo.gap_analysis === null ? (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium bg-error-bg border border-error text-error">
                null
              </span>
            ) : (
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium border ${
                debugInfo.gap_analysis.gaps.length > 0
                  ? 'bg-amber-100 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/40 text-amber-700 dark:text-amber-400'
                  : 'bg-surface-overlay border-border-subtle text-text-secondary'
              }`}>
                {debugInfo.gap_analysis.gaps.length} gaps
              </span>
            )}
          </div>
        </div>
      )}

      {/* Chunk Analysis */}
      <DebugSection
        label="Chunk Analysis"
        onCopy={() => chunksData ? chunksToMarkdown(chunksData, title, company) : '(no chunk data)'}
      >
        <ChunkAnalysis data={chunksData} error={chunksError} jobUrl={jobUrl} />
      </DebugSection>

      {/* Profile */}
      {debugInfo && (
        <DebugSection
          label="Formatted Profile"
          badge={
            debugInfo.profile_snapshot_source === 'snapshot'
              ? <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400">Snapshot from generation</span>
              : <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400">Reconstructed — experience may have changed</span>
          }
          onCopy={() => debugInfo.formatted_profile}
        >
          <CodeBlock text={debugInfo.formatted_profile} />
        </DebugSection>
      )}

      {/* Prompts */}
      {debugInfo && (
        <>
          <DebugSection
            label="Chunk Matching — System Prompt"
            onCopy={() => debugInfo.chunk_matching_system_prompt}
          >
            <CodeBlock text={debugInfo.chunk_matching_system_prompt} />
          </DebugSection>

          <DebugSection
            label={
              debugInfo.matching_mode === 'vector'
                ? 'Chunk Matching — Sample User Message (vector mode, 1 call per chunk)'
                : 'Chunk Matching — Sample User Message (llm mode, batched)'
            }
            onCopy={() => debugInfo.sample_chunk_user_message}
          >
            <CodeBlock text={debugInfo.sample_chunk_user_message} />
          </DebugSection>

          {debugInfo.tailoring_system_prompt && (
            <DebugSection
              label="Tailoring Generation — System Prompt"
              onCopy={() => debugInfo.tailoring_system_prompt!}
            >
              <CodeBlock text={debugInfo.tailoring_system_prompt} />
            </DebugSection>
          )}

          {debugInfo.gap_analysis_system_prompt && (
            <DebugSection
              label="Gap Analysis — System Prompt"
              onCopy={() => debugInfo.gap_analysis_system_prompt!}
            >
              <CodeBlock text={debugInfo.gap_analysis_system_prompt} />
            </DebugSection>
          )}

          <DebugSection
            label="Gap Analysis — Result"
            onCopy={() => debugInfo.gap_analysis ? JSON.stringify(debugInfo.gap_analysis, null, 2) : 'null'}
          >
            {debugInfo.gap_analysis === null ? (
              <div className="flex items-center gap-2 p-4 rounded-xl border border-error bg-error-bg text-sm text-error">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>
                  <strong>gap_analysis is null</strong> — gap analysis did not run or failed silently.
                  Restart the backend server, then regenerate this tailoring to trigger a fresh run.
                </span>
              </div>
            ) : debugInfo.gap_analysis.gaps.length === 0 ? (
              <div className="p-4 rounded-xl border border-border-default bg-surface-base text-sm text-text-secondary">
                No gaps found — the LLM considered all requirements sufficiently evidenced.
                sourced: {debugInfo.gap_analysis.sourced_claim_count} / unsourced: {debugInfo.gap_analysis.unsourced_claim_count}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-text-tertiary">
                  {debugInfo.gap_analysis.gaps.length} gap{debugInfo.gap_analysis.gaps.length !== 1 ? 's' : ''} found
                  · sourced: {debugInfo.gap_analysis.sourced_claim_count}
                  · unsourced: {debugInfo.gap_analysis.unsourced_claim_count}
                </p>
                {debugInfo.gap_analysis.gaps.map((gap, i) => (
                  <div key={i} className="rounded-xl border border-border-default bg-surface-base p-3 text-xs space-y-1.5">
                    <p className="font-medium text-text-primary">{gap.job_requirement}</p>
                    <p className="text-text-secondary">{gap.question_for_candidate}</p>
                    <p className="text-text-tertiary">{gap.context}</p>
                    <p className="text-text-disabled">
                      chunk_id: {gap.chunk_id
                        ? <span className="font-mono">{gap.chunk_id}</span>
                        : <span className="text-amber-600 dark:text-amber-400">unresolved</span>}
                      · searched: {gap.source_searched}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </DebugSection>

          <DebugSection
            label="Full Debug Dump"
            onCopy={() => [
              header,
              '',
              '## Formatted Profile',
              debugInfo.formatted_profile,
              '',
              '## Chunk Matching — System Prompt',
              debugInfo.chunk_matching_system_prompt,
              '',
              '## Chunk Matching — Sample User Message',
              debugInfo.sample_chunk_user_message,
              debugInfo.tailoring_system_prompt ? `\n## Tailoring System Prompt\n${debugInfo.tailoring_system_prompt}` : '',
              '',
              '## Chunk Analysis',
              chunksData ? chunksToMarkdown(chunksData, title, company) : '(no chunk data)',
              '',
              '## Gap Analysis',
              debugInfo.gap_analysis ? JSON.stringify(debugInfo.gap_analysis, null, 2) : 'null',
            ].join('\n')}
          >
            <p className="text-xs text-text-tertiary">
              Copies all sections above — formatted profile, all prompts, and full chunk analysis — as a single block for pasting into a review conversation.
            </p>
          </DebugSection>
        </>
      )}

    </div>
  );
}
