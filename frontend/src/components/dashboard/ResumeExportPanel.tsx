'use client';

import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { Loader2, Download, AlertCircle, FileText, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ResumeCanvas } from '@/components/dashboard/ResumeCanvas';
import type { ResumeDraft } from '@/types';

interface Props {
  open: boolean;
  onClose: () => void;
  tailoringId: string;
  jobTitle?: string | null;
  company?: string | null;
  initialDraft?: ResumeDraft | null;
  tailoringPublicLink?: string | null;
  profilePublicLink?: string | null;
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

export function ResumeExportPanel({ open, onClose, tailoringId, jobTitle, company, initialDraft, tailoringPublicLink, profilePublicLink }: Props) {
  const { data: session } = useSession();
  const [draft, setDraft] = useState<ResumeDraft | null>(initialDraft ?? null);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setDraft(await res.json());
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

  const subtitle = [jobTitle, company].filter(Boolean).join(' · ');
  const userName = session?.user?.name ?? null;
  const contactEmail = session?.user?.email ?? null;

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose(); }}>
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
          </div>
        </DialogHeader>

        {/* Hint banner — only when a draft is loaded */}
        {draft && (
          <div className="shrink-0 flex items-center justify-center px-5 py-2 border-b border-border-subtle bg-surface-elevated">
            <p className="text-xs text-text-tertiary text-center">
              Click any text in the preview to edit it. Hover bullets for AI polish.
            </p>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">

          {draft ? (
            <ResumeCanvas
              draft={draft}
              userName={userName}
              contactEmail={contactEmail}
              tailoringPublicLink={tailoringPublicLink}
              profilePublicLink={profilePublicLink}
              tailoringId={tailoringId}
              onDraftChange={setDraft}
            />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 p-6 text-center">
              {noActiveClaims && (
                <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-surface-elevated border border-border-default max-w-sm">
                  <AlertCircle className="h-4 w-4 text-text-tertiary shrink-0 mt-0.5" />
                  <p className="text-text-secondary text-xs text-left">
                    No experience claims found. Add your experience in{' '}
                    <a href="/dashboard/experience" className="text-text-link hover:underline">My Experience</a>{' '}
                    first, then generate a resume.
                  </p>
                </div>
              )}

              {error && !noActiveClaims && (
                <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-surface-elevated border border-border-default text-xs text-error max-w-sm">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {generating && (
                <div className="flex items-center gap-2 text-sm text-text-secondary">
                  <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                  Selecting your most relevant experience…
                </div>
              )}

              {!error && !generating && (
                <>
                  <div className="flex flex-col items-center gap-2">
                    <FileText className="h-10 w-10 text-text-tertiary opacity-30" />
                    <p className="text-sm text-text-secondary max-w-xs">
                      Generates a resume pre-filled with the experience most relevant to this role.
                      Original content is never modified — edits are kept separately.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={generating}
                    className={cn(primaryBtnCls, 'px-5 h-9')}
                  >
                    Generate Resume
                  </button>
                </>
              )}
            </div>
          )}

        </div>
      </DialogContent>
    </Dialog>
  );
}
