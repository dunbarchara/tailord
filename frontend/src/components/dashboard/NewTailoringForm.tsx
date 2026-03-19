'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Link2, Sparkles, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { formatElapsed } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { TailoringListItem } from '@/types';

type FormState = 'idle' | 'processing' | 'error';

type Phase = 'scraping';

interface PhaseState {
  status: 'pending' | 'running' | 'done';
  elapsed: number; // seconds
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

export function NewTailoringForm() {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [formState, setFormState] = useState<FormState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [tailorings, setTailorings] = useState<TailoringListItem[]>([]);
  const [duplicate, setDuplicate] = useState<TailoringListItem | null>(null);
  const [phases, setPhases] = useState<Record<Phase, PhaseState>>({
    scraping: { status: 'pending', elapsed: 0 },
  });

  // Per-phase timers
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activePhaseRef = useRef<Phase | null>(null);

  useEffect(() => {
    fetch('/api/tailorings')
      .then((r) => r.json())
      .then((data) => Array.isArray(data) ? setTailorings(data) : [])
      .catch(() => { });
  }, []);

  // Tick the active phase's elapsed counter every second
  useEffect(() => {
    timerRef.current = setInterval(() => {
      const phase = activePhaseRef.current;
      if (!phase) return;
      setPhases(prev => ({
        ...prev,
        [phase]: { ...prev[phase], elapsed: prev[phase].elapsed + 1 },
      }));
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  function startPhase(phase: Phase) {
    activePhaseRef.current = phase;
    setPhases(prev => ({ ...prev, [phase]: { status: 'running', elapsed: 0 } }));
  }

  function completePhase(phase: Phase) {
    setPhases(prev => ({
      ...prev,
      [phase]: { ...prev[phase], status: 'done' },
    }));
  }

  const submitTailoring = async () => {
    setFormState('processing');
    setErrorMessage('');
    setDuplicate(null);
    setPhases({
      scraping: { status: 'pending', elapsed: 0 },
    });

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
            // Mark previous phase done
            const prev = PHASE_ORDER[PHASE_ORDER.indexOf(stage) - 1];
            if (prev) completePhase(prev);
            startPhase(stage);
          } else if (event === 'ready') {
            // Mark all phases done
            activePhaseRef.current = null;
            setPhases(prev => {
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
    const existing = tailorings.find(
      (t) => t.job_url && normalizeUrl(t.job_url) === normalized,
    );
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

      <div className="h-full overflow-y-auto custom-scrollbar">
        <div className="max-w-2xl mx-auto p-6 lg:p-8 space-y-6">
          <div>
            <h1 className="text-2xl font-semibold text-text-primary">New Tailoring</h1>
            <p className="mt-1 text-text-secondary">
              Paste a job posting URL to generate a tailored application.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="job-url" className="text-sm font-medium text-text-primary">
                Job Posting URL
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Link2 className="h-4 w-4 text-text-tertiary" />
                </div>
                <Input
                  id="job-url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://company.com/careers/job-posting"
                  disabled={isProcessing}
                  className="pl-9"
                  required
                />
              </div>
            </div>

            {/* Phase list — visible during processing, pending steps hidden */}
            {isProcessing && (
              <div className="space-y-2 animate-fade-in">
                {PHASE_ORDER.filter(phase => phases[phase].status !== 'pending').map((phase) => {
                  const { status, elapsed } = phases[phase];
                  return (
                    <div key={phase} className="flex items-center gap-2.5 text-sm">
                      {status === 'done'
                        ? <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0" />
                        : <Loader2 className="h-4 w-4 text-brand-primary animate-spin flex-shrink-0" />}
                      <span className="text-text-secondary">
                        {PHASE_LABELS[phase]}{status === 'running' ? '...' : ''}
                        <span className="text-text-tertiary"> · {formatElapsed(elapsed)}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {formState === 'error' && (
              <Card className="border-error/30 bg-error-bg animate-fade-in">
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-error flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-text-primary">Unable to create tailoring</p>
                      <p className="text-sm text-text-secondary mt-1">{errorMessage}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <Button
              type="submit"
              disabled={!url.trim() || isProcessing}
              className="gap-2"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Processing…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Create Tailoring
                </>
              )}
            </Button>
          </form>
        </div>
      </div>
    </>
  );
}
