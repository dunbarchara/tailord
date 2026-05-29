'use client';

import { useState } from 'react';
import { Loader2, Download, AlertCircle, FileText, X, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ResumeDraftPreview } from '@/components/dashboard/ResumeDraftPreview';
import type { ResumeDraft } from '@/types';

interface Props {
  open: boolean;
  onClose: () => void;
  tailoringId: string;
  jobTitle?: string | null;
  company?: string | null;
  initialDraft?: ResumeDraft | null;
}

const textBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] ' +
  'bg-surface-elevated border border-border-default text-text-secondary ' +
  'text-sm font-normal tracking-[-0.1px] ' +
  'hover:bg-surface-overlay hover:border-border-strong hover:text-text-primary ' +
  'transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

const primaryBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] ' +
  'bg-brand-primary border border-brand-primary text-white ' +
  'text-sm font-normal tracking-[-0.1px] ' +
  'hover:opacity-90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

export function ResumeExportPanel({ open, onClose, tailoringId, jobTitle, company, initialDraft }: Props) {
  const [draft, setDraft] = useState<ResumeDraft | null>(initialDraft ?? null);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(true);

  const noActiveClaims = error === 'no_active_claims';

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/resume/generate`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail ?? 'Generation failed.');
        return;
      }
      const newDraft = await res.json();
      setDraft(newDraft);
      setPreviewKey(k => k + 1);
      setPreviewLoading(true);
    } catch {
      setError('Could not reach the server.');
    } finally {
      setGenerating(false);
    }
  }

  async function handleExportPdf() {
    if (!draft) return;
    setExporting(true);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/resume/pdf`, { method: 'POST' });
      if (!res.ok) { toast.error('PDF export failed.'); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const disposition = res.headers.get('Content-Disposition') ?? '';
      const match = disposition.match(/filename="([^"]+)"/);
      a.download = match ? match[1] : 'resume.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Resume downloaded.');
    } catch {
      toast.error('Could not download PDF.');
    } finally {
      setExporting(false);
    }
  }

  function handleDraftChange(updated: ResumeDraft) {
    setDraft(updated);
    setPreviewKey(k => k + 1);
    setPreviewLoading(true);
  }

  const subtitle = [jobTitle, company].filter(Boolean).join(' · ');

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-[92vw] w-[1140px] max-h-[90vh] flex flex-col p-0 gap-0 rounded-2xl overflow-hidden">

        {/* Header */}
        <DialogHeader className="shrink-0 flex flex-row items-center justify-between px-5 pt-4 pb-3 border-b border-border-subtle">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="h-4 w-4 text-text-secondary shrink-0" />
            <div className="min-w-0">
              <DialogTitle className="text-sm font-semibold text-text-primary tracking-[-0.1px]">
                Tailored Resume
              </DialogTitle>
              {subtitle && (
                <p className="text-xs text-text-tertiary truncate">{subtitle}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-4">
            {draft && (
              <>
                <button type="button" onClick={handleGenerate} disabled={generating} className={textBtnCls}>
                  {generating
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <RefreshCw className="h-3.5 w-3.5" />}
                  {generating ? 'Rebuilding…' : 'Rebuild'}
                </button>
                <button type="button" onClick={handleExportPdf} disabled={exporting} className={primaryBtnCls}>
                  {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                  {exporting ? 'Exporting…' : 'Export PDF'}
                </button>
              </>
            )}
            <button
              type="button"
              onClick={onClose}
              className="h-7 w-7 rounded-lg flex items-center justify-center text-text-tertiary hover:text-text-primary hover:bg-surface-overlay transition-colors"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </DialogHeader>

        {/* Body */}
        <div className="flex-1 flex overflow-hidden min-h-0">

          {/* Left: controls */}
          <div className="w-[300px] shrink-0 overflow-y-auto border-r border-border-subtle px-4 py-4 space-y-4 custom-scrollbar">

            {/* Error states */}
            {noActiveClaims && (
              <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-xl bg-surface-elevated border border-border-default text-sm">
                <AlertCircle className="h-4 w-4 text-text-tertiary shrink-0 mt-0.5" />
                <p className="text-text-secondary text-xs">
                  No experience claims found. Add your experience in{' '}
                  <a href="/dashboard/experience" className="text-text-link hover:underline">My Experience</a>{' '}
                  first, then generate a resume.
                </p>
              </div>
            )}

            {error && !noActiveClaims && (
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-surface-elevated border border-border-default text-xs text-error">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Pre-generation state */}
            {!draft && !error && !generating && (
              <div className="space-y-3">
                <p className="text-sm text-text-secondary">
                  Generates a one-page resume pre-filled with the experience most relevant to this role.
                  Original claim content is never modified — AI rewrites are kept separately.
                </p>
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={generating}
                  className={cn(primaryBtnCls, 'w-full justify-center h-9')}
                >
                  Generate Resume
                </button>
              </div>
            )}

            {generating && !draft && (
              <div className="flex items-center gap-2 text-sm text-text-secondary py-2">
                <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                Selecting your most relevant experience…
              </div>
            )}

            {/* Draft controls */}
            {draft && !error && (
              <ResumeDraftPreview
                draft={draft}
                tailoringId={tailoringId}
                onDraftChange={handleDraftChange}
              />
            )}
          </div>

          {/* Right: live preview */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden bg-[#e8e8e8] dark:bg-surface-sunken flex justify-center items-start py-8 px-2">
            {draft ? (
              <div className="relative flex-shrink-0 shadow-xl">
                {previewLoading && (
                  <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
                    <Loader2 className="h-5 w-5 animate-spin text-text-tertiary" />
                  </div>
                )}
                <iframe
                  key={previewKey}
                  src={`/api/tailorings/${tailoringId}/resume/html`}
                  title="Resume preview"
                  onLoad={() => setPreviewLoading(false)}
                  style={{
                    width: '8.5in',
                    height: '11in',
                    border: 'none',
                    display: 'block',
                  }}
                />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-text-tertiary gap-3">
                <FileText className="h-10 w-10 opacity-20" />
                <p className="text-sm">Your resume preview will appear here</p>
              </div>
            )}
          </div>

        </div>
      </DialogContent>
    </Dialog>
  );
}
