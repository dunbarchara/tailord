'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Link2, Sparkles, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';

type ProcessingState = 'idle' | 'processing' | 'error';

export function NewTailoringForm() {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [state, setState] = useState<ProcessingState>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setState('processing');
    setErrorMessage('');

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
    } catch {
      setErrorMessage('Could not reach the server. Please try again.');
      setState('error');
    }
  };

  return (
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
  );
}
