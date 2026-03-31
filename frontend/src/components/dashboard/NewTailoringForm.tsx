'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Link2, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { formatElapsed } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import type { TailoringListItem } from '@/types';

type FormState = 'idle' | 'processing' | 'error';
type Phase = 'scraping';

interface PhaseState {
  status: 'pending' | 'running' | 'done';
  elapsed: number;
}

const PHASE_LABELS: Record<Phase, string> = {
  scraping: 'Fetching job posting',
};
const PHASE_ORDER: Phase[] = ['scraping'];

function normalizeUrl(raw: string): string {
  try {
    const u = new URL(raw.trim());
    return (u.origin + u.pathname).replace(/\/$/, '') + (u.search || '');
  } catch {
    return raw.trim().toLowerCase();
  }
}

/* ─── Shared styles ──────────────────────────────────────────────────────── */

const inputCls =
  'w-full h-10 rounded-xl border border-border-default bg-surface-elevated px-3 pl-9 text-sm text-text-primary placeholder:text-text-disabled outline-none transition-colors duration-100 hover:border-border-strong hover:bg-surface-base focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)] disabled:opacity-50 disabled:cursor-not-allowed';

const submitBtnCls =
  'inline-flex items-center justify-center gap-2 h-9 px-4 rounded-[10px] text-sm font-normal tracking-[-0.1px] bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 transition-opacity disabled:bg-surface-base dark:disabled:bg-surface-overlay disabled:text-text-disabled disabled:cursor-not-allowed disabled:hover:opacity-100';

/* ─── Component ──────────────────────────────────────────────────────────── */

export function NewTailoringForm() {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [formState, setFormState] = useState<FormState>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [tailorings, setTailorings] = useState<TailoringListItem[]>([]);
  const [duplicate, setDuplicate] = useState<TailoringListItem | null>(null);
  const [phases, setPhases] = useState<Record<Phase, PhaseState>>({
    scraping: { status: 'pending', elapsed: 0 },
  });

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activePhaseRef = useRef<Phase | null>(null);

  useEffect(() => {
    fetch('/api/tailorings')
      .then((r) => r.json())
      .then((data) => Array.isArray(data) ? setTailorings(data) : [])
      .catch(() => {});
  }, []);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      const phase = activePhaseRef.current;
      if (!phase) return;
      setPhases((prev) => ({
        ...prev,
        [phase]: { ...prev[phase], elapsed: prev[phase].elapsed + 1 },
      }));
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  function startPhase(phase: Phase) {
    activePhaseRef.current = phase;
    setPhases((prev) => ({ ...prev, [phase]: { status: 'running', elapsed: 0 } }));
  }

  function completePhase(phase: Phase) {
    setPhases((prev) => ({
      ...prev,
      [phase]: { ...prev[phase], status: 'done' },
    }));
  }

  const submitTailoring = async () => {
    setFormState('processing');
    setErrorMessage('');
    setDuplicate(null);
    setPhases({ scraping: { status: 'pending', elapsed: 0 } });

    try {
      const res = await fetch('/api/tailorings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_url: url }),
      });

      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data?.detail ?? data?.error ?? 'Something went wrong.');
        setFormState('error');
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const boundary = buffer.lastIndexOf('\n\n');
        if (boundary === -1) continue;
        const complete = buffer.slice(0, boundary + 2);
        buffer = buffer.slice(boundary + 2);

        for (const block of complete.split('\n\n')) {
          if (!block.trim()) continue;
          let event: string | null = null;
          let data = '';
          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) event = line.slice(7).trim();
            else if (line.startsWith('data: ')) data = line.slice(6);
          }
          if (!data) continue;

          if (event === 'stage') {
            const stage = data as Phase;
            const prev = PHASE_ORDER[PHASE_ORDER.indexOf(stage) - 1];
            if (prev) completePhase(prev);
            startPhase(stage);
          } else if (event === 'ready') {
            activePhaseRef.current = null;
            setPhases((prev) => {
              const next = { ...prev };
              for (const p of PHASE_ORDER) next[p] = { ...prev[p], status: 'done' };
              return next;
            });
            const payload = JSON.parse(data);
            router.push(`/dashboard/tailorings/${payload.id}`);
            router.refresh();
            return;
          } else if (event === 'error') {
            activePhaseRef.current = null;
            const payload = JSON.parse(data);
            setErrorMessage(payload.detail ?? 'Something went wrong.');
            setFormState('error');
            return;
          }
        }
      }
    } catch {
      setErrorMessage('Could not reach the server. Please try again.');
      setFormState('error');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    const normalized = normalizeUrl(url);
    const existing = tailorings.find((t) => t.job_url && normalizeUrl(t.job_url) === normalized);
    if (existing) { setDuplicate(existing); return; }
    await submitTailoring();
  };

  const duplicateLabel = duplicate
    ? [duplicate.title, duplicate.company].filter(Boolean).join(' at ') || 'a previous tailoring'
    : '';

  const isProcessing = formState === 'processing';

  return (
    <>
      <Dialog open={!!duplicate} onOpenChange={(open) => !open && setDuplicate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>You&apos;ve used this posting before</DialogTitle>
            <DialogDescription>
              You already generated{' '}
              <span className="font-medium text-text-primary">{duplicateLabel}</span>{' '}
              from this URL. Create another tailoring anyway?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => duplicate && router.push(`/dashboard/tailorings/${duplicate.id}`)}
            >
              View existing
            </Button>
            <Button onClick={submitTailoring}>Create anyway</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Shell — matches Settings layout */}
      <div className="h-full flex flex-col bg-surface-elevated">

        {/* Topbar */}
        <div className="shrink-0 flex items-center h-12 px-6 bg-surface-elevated">
          <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">
            New Tailoring
          </span>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="max-w-6xl mx-auto px-6 lg:px-16 pt-12 pb-24 [&>*:first-child]:pt-0">
            <div className="divide-y divide-zinc-950/5 dark:divide-white/5">

              {/* Section row */}
              <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-8 gap-x-12 gap-y-4">

                {/* Left: section title + description */}
                <div className="col-span-3 flex flex-col gap-1">
                  <h2 className="text-sm text-text-primary">
                    Create New Tailoring
                  </h2>
                  <p className="text-sm text-text-secondary">
                    Paste a job posting URL and Tailord will generate a role-specific document mapped to your experience.
                  </p>
                </div>

                {/* Right: controls */}
                <div className="col-span-5 space-y-3">

                  {/* URL field */}
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="job-url" className="text-sm font-medium text-text-primary">
                      Job posting URL
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Link2 className="h-4 w-4 text-text-tertiary" />
                      </div>
                      <input
                        id="job-url"
                        type="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://company.com/careers/role"
                        disabled={isProcessing}
                        required
                        className={inputCls}
                      />
                    </div>
                  </div>

                  {/* Processing phases */}
                  {isProcessing && (
                    <div className="space-y-2">
                      {PHASE_ORDER.filter((phase) => phases[phase].status !== 'pending').map((phase) => {
                        const { status, elapsed } = phases[phase];
                        return (
                          <div key={phase} className="flex items-center gap-2.5 text-sm">
                            {status === 'done'
                              ? <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
                              : <Loader2 className="h-4 w-4 text-text-tertiary animate-spin shrink-0" />}
                            <span className="text-text-secondary">
                              {PHASE_LABELS[phase]}{status === 'running' ? '…' : ''}
                            </span>
                            <span className="text-text-disabled text-xs">{formatElapsed(elapsed)}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Error state */}
                  {formState === 'error' && (
                    <div className="flex items-start gap-3 rounded-xl border border-error/30 bg-error-bg px-4 py-3">
                      <AlertCircle className="h-4 w-4 text-error shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-text-primary">Unable to create tailoring</p>
                        <p className="text-sm text-text-secondary mt-0.5">{errorMessage}</p>
                      </div>
                    </div>
                  )}

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={!url.trim() || isProcessing}
                    className={submitBtnCls}
                  >
                    {isProcessing ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Processing…
                      </>
                    ) : (
                      <>
                        Create Tailoring
                      </>
                    )}
                  </button>

                </div>
              </form>

            </div>
          </div>
        </div>

      </div>
    </>
  );
}
