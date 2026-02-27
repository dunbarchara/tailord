'use client';

import { useState } from 'react';
import { Link2, Sparkles, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';

type ProcessingState = 'idle' | 'processing' | 'success' | 'error';

export function NewTailoringForm() {
  const [url, setUrl] = useState('');
  const [state, setState] = useState<ProcessingState>('idle');
  const [tailoringId, setTailoringId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setState('processing');
    // TODO: POST to /api/parse then /api/generate
    setTimeout(() => {
      setTailoringId(Math.random().toString(36).substring(7));
      setState('success');
    }, 3000);
  };

  const resetForm = () => {
    setUrl('');
    setState('idle');
    setTailoringId(null);
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
              Analyzing job posting…
            </div>
          )}

          {state === 'success' && tailoringId && (
            <Card className="border-success/30 bg-success-bg animate-fade-in">
              <CardContent className="pt-4 pb-4">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-success flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-text-primary">Tailoring created</p>
                    <div className="flex gap-3 mt-3">
                      <Button asChild size="sm">
                        <a href={`/dashboard/tailorings/${tailoringId}`}>View Tailoring</a>
                      </Button>
                      <Button variant="outline" size="sm" onClick={resetForm}>
                        Create Another
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {state === 'error' && (
            <Card className="border-error/30 bg-error-bg animate-fade-in">
              <CardContent className="pt-4 pb-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-error flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-text-primary">Unable to process URL</p>
                    <p className="text-sm text-text-secondary mt-1">Check the URL and try again.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {state !== 'success' && (
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
          )}
        </form>
      </div>
    </div>
  );
}
