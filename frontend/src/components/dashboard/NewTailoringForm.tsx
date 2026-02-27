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

    // Placeholder — real API call goes here
    setTimeout(() => {
      const newId = Math.random().toString(36).substring(7);
      setTailoringId(newId);
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
      <div className="max-w-3xl mx-auto p-6 lg:p-8 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary mb-2">
            Create New Tailoring
          </h1>
          <p className="text-text-secondary">
            Paste a job posting URL and we&apos;ll analyze it to create a perfectly tailored application
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-3">
            <label htmlFor="job-url" className="block text-sm font-medium text-text-primary">
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
            <p className="text-xs text-text-tertiary">
              We support LinkedIn, Indeed, Greenhouse, Lever, and most job boards
            </p>
          </div>

          {state === 'processing' && (
            <Card className="animate-fade-in">
              <CardContent className="pt-4">
                <div className="flex items-center gap-3">
                  <Loader2 className="h-5 w-5 text-brand-primary animate-spin" />
                  <div>
                    <p className="font-medium text-text-primary">Processing job posting...</p>
                    <p className="text-sm text-text-secondary mt-0.5">
                      Analyzing requirements and extracting key information
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {state === 'success' && tailoringId && (
            <Card className="border-success/30 bg-success-bg animate-fade-in">
              <CardContent className="pt-4">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-success flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text-primary">Job posting analyzed successfully!</p>
                    <p className="text-sm text-text-secondary mt-1">
                      Your tailoring is ready.
                    </p>
                    <div className="flex gap-3 mt-4">
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
              <CardContent className="pt-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-error flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-text-primary">Unable to process URL</p>
                    <p className="text-sm text-text-secondary mt-1">
                      Please check the URL and try again.
                    </p>
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
                  Processing...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Analyze Job Posting
                </>
              )}
            </Button>
          )}
        </form>

        <div className="space-y-4 pt-4">
          <h3 className="font-semibold text-text-primary">What happens next?</h3>
          <div className="space-y-3">
            {[
              {
                n: 1,
                title: 'We extract key requirements',
                desc: 'Skills, experience level, responsibilities, and company culture',
              },
              {
                n: 2,
                title: 'AI analyzes your fit',
                desc: 'Matches your experience with job requirements',
              },
              {
                n: 3,
                title: 'Generate tailored content',
                desc: 'Cover letter, resume highlights, and application strategy',
              },
            ].map(({ n, title, desc }) => (
              <div key={n} className="flex gap-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-primary/10 text-brand-primary flex items-center justify-center text-sm font-semibold">
                  {n}
                </div>
                <div className="flex-1 pt-0.5">
                  <p className="text-sm text-text-primary font-medium">{title}</p>
                  <p className="text-sm text-text-secondary mt-1">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
