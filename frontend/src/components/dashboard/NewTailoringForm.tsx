'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Link2, Sparkles, AlertCircle, Loader2 } from 'lucide-react';
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

type ProcessingState = 'idle' | 'processing' | 'error';

function normalizeUrl(raw: string): string {
  try {
    const u = new URL(raw.trim());
    // Strip trailing slash and fragment, keep path+query for comparison
    return (u.origin + u.pathname).replace(/\/$/, '') + (u.search || '');
  } catch {
    return raw.trim().toLowerCase();
  }
}

export function NewTailoringForm() {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [state, setState] = useState<ProcessingState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [tailorings, setTailorings] = useState<TailoringListItem[]>([]);
  const [duplicate, setDuplicate] = useState<TailoringListItem | null>(null);

  useEffect(() => {
    fetch('/api/tailorings')
      .then((r) => r.json())
      .then((data) => Array.isArray(data) ? setTailorings(data) : [])
      .catch(() => { });
  }, []);

  const submitTailoring = async () => {
    setState('processing');
    setErrorMessage('');
    setDuplicate(null);

    try {
      const res = await fetch('/api/tailorings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_url: url }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = data?.detail ?? data?.error ?? 'Something went wrong.';
        setErrorMessage(detail);
        setState('error');
        return;
      }

      const tailoring = await res.json();
      router.push(`/dashboard/tailorings/${tailoring.id}`);
      router.refresh();
    } catch {
      setErrorMessage('Could not reach the server. Please try again.');
      setState('error');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    const normalized = normalizeUrl(url);
    const existing = tailorings.find(
      (t) => t.job_url && normalizeUrl(t.job_url) === normalized,
    );

    if (existing) {
      setDuplicate(existing);
      return;
    }

    await submitTailoring();
  };

  const duplicateLabel = duplicate
    ? [duplicate.title, duplicate.company].filter(Boolean).join(' at ') || 'a previous tailoring'
    : '';

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
            <Button onClick={submitTailoring}>
              Create anyway
            </Button>
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
                  disabled={state === 'processing'}
                  className="pl-9"
                  required
                />
              </div>
            </div>

            {state === 'processing' && (
              <div className="flex items-center gap-2 text-sm text-text-secondary animate-fade-in">
                <Loader2 className="h-4 w-4 text-brand-primary animate-spin flex-shrink-0" />
                Analyzing job posting… this takes 15–25 seconds
              </div>
            )}

            {state === 'error' && (
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
              disabled={!url.trim() || state === 'processing'}
              className="gap-2"
            >
              {state === 'processing' ? (
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
