'use client';

import { Upload, FileText, Trash2, Loader2, AlertCircle, X, RefreshCw } from 'lucide-react';
import { formatElapsed, formatRelativeDate } from '@/lib/utils';
import { MintButton } from '@/components/ui/MintButton';
import type { ExperienceRecord } from '@/types';

/* ─── Types (exported so ExperienceManager can import them) ─────────────── */

export type UploadPhase =
  | { phase: 'loading' }
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'processing'; filename: string; experienceId: string }
  | { phase: 'ready'; record: ExperienceRecord }
  | { phase: 'error'; message: string };

const PROCESS_STAGE_LABELS: Record<string, string> = {
  extracting: 'Extracting text',
  analyzing: 'Analyzing profile',
};

/* ─── LiveBadge ──────────────────────────────────────────────────────────── */

function LiveBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center w-fit font-medium bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400 gap-[3px] text-xs leading-none rounded-full py-1 px-2">
      <span className="flex items-center justify-center size-3">
        <span className="size-1.5 bg-current rounded-full" />
      </span>
      {label}
    </span>
  );
}

/* ─── Props ─────────────────────────────────────────────────────────────── */

interface ResumeUploadSectionProps {
  uploadState: UploadPhase;
  processingStage: string | null;
  stageStartedAt: Record<string, number>;
  readOnly?: boolean;
  onUploadClick: () => void;
  onCancelProcessing: () => void;
  onReplace: () => void;
  onRemove: () => void;
}

/* ─── Component ─────────────────────────────────────────────────────────── */

export function ResumeUploadSection({
  uploadState,
  processingStage,
  stageStartedAt,
  readOnly,
  onUploadClick,
  onCancelProcessing,
  onReplace,
  onRemove,
}: ResumeUploadSectionProps) {
  const hasFile = uploadState.phase === 'ready' && !!uploadState.record.filename;

  const subtext = (() => {
    switch (uploadState.phase) {
      case 'loading':
      case 'error': return null;
      case 'uploading':
      case 'processing':
      case 'idle': return 'Upload a PDF, DOCX, or TXT file to get started';
      case 'ready':
        if (!uploadState.record.filename) return 'Upload a PDF, DOCX, or TXT file to get started';
        return `Last updated ${formatRelativeDate(uploadState.record.processed_at) ?? ''}`;
    }
  })();

  const card = (() => {
    switch (uploadState.phase) {
      case 'loading':
      case 'idle': return null;
      case 'uploading':
        return (
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
            <Loader2 className="h-4 w-4 text-text-tertiary animate-spin flex-shrink-0" />
            <div>
              <p className="text-sm text-text-secondary truncate">{uploadState.filename}</p>
              <p className="text-xs text-text-disabled">Uploading…</p>
            </div>
          </div>
        );
      case 'processing': {
        const firstStage = Object.keys(stageStartedAt)[0];
        const overallStart = firstStage ? stageStartedAt[firstStage] : undefined;
        // eslint-disable-next-line react-hooks/purity -- parent re-renders via tick interval; Date.now() stays fresh
        const elapsed = overallStart ? Math.floor((Date.now() - overallStart) / 1000) : 0;
        const label = processingStage
          ? (PROCESS_STAGE_LABELS[processingStage] ?? processingStage)
          : 'Processing';
        return (
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
            <Loader2 className="h-4 w-4 text-text-tertiary animate-spin flex-shrink-0" />
            <div>
              <p className="text-sm text-text-secondary truncate">{uploadState.filename}</p>
              <p className="text-xs text-text-disabled">
                {label}…{overallStart ? ` ${formatElapsed(elapsed)}` : ''}
              </p>
            </div>
          </div>
        );
      }
      case 'ready':
        if (!uploadState.record.filename) return null;
        return (
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
            <FileText className="h-4 w-4 text-text-tertiary flex-shrink-0" />
            <div>
              <p className="text-sm text-text-secondary truncate">{uploadState.record.filename}</p>
              <p className="text-xs text-text-disabled">Processed</p>
            </div>
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-red-50/60 dark:bg-red-950/10 border border-error/20 w-fit min-w-xs">
            <AlertCircle className="h-4 w-4 text-error flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm text-error">Processing failed</p>
              <p className="text-xs text-text-tertiary truncate">{uploadState.message}</p>
            </div>
          </div>
        );
    }
  })();

  const uploadBtn = (
    <button
      type="button"
      onClick={() => !readOnly && onUploadClick()}
      disabled={readOnly}
      className={`flex items-center gap-3 px-3 py-3 rounded-xl border border-dashed border-border-default text-left w-fit min-w-xs transition-colors ${
        readOnly ? 'opacity-50 cursor-not-allowed' : 'hover:border-border-strong hover:bg-surface-sunken'
      }`}
    >
      <Upload className="h-4 w-4 text-text-tertiary flex-shrink-0" />
      <div>
        <p className="text-sm text-text-secondary">Click to upload</p>
        <p className="text-xs text-text-disabled">PDF, DOCX, or TXT</p>
      </div>
    </button>
  );

  const controls = (() => {
    switch (uploadState.phase) {
      case 'loading':
      case 'uploading': return null;
      case 'idle': return uploadBtn;
      case 'processing':
        return (
          <div className="flex flex-wrap items-center gap-2">
            <MintButton icon={<X />} label="Cancel" onClick={onCancelProcessing} danger disabled={readOnly} />
          </div>
        );
      case 'ready':
        if (!uploadState.record.filename) return uploadBtn;
        return (
          <div className="flex flex-wrap items-center gap-2">
            <MintButton icon={<RefreshCw />} label="Replace" onClick={onReplace} disabled={readOnly} />
            <MintButton icon={<Trash2 />} label="Delete" onClick={onRemove} danger disabled={readOnly} />
          </div>
        );
      case 'error':
        return (
          <div className="flex flex-wrap items-center gap-2">
            <MintButton icon={<Upload />} label="Try again" onClick={onUploadClick} disabled={readOnly} />
            <MintButton icon={<X />} label="Clear" onClick={onRemove} danger disabled={readOnly} />
          </div>
        );
    }
  })();

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2 h-6">
          <h2 className="text-sm font-medium text-text-primary">Resume Upload</h2>
          <span className={hasFile ? 'flex items-center' : 'invisible'}>
            <LiveBadge label="Uploaded" />
          </span>
        </div>
        {subtext && (
          <p className="text-sm text-text-tertiary">{subtext}</p>
        )}
      </div>
      {card}
      {controls}
    </div>
  );
}
