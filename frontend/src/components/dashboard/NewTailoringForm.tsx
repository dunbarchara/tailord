'use client';

import { useState } from 'react';
import { Link2, Sparkles, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

type ProcessingState = 'idle' | 'processing' | 'success' | 'error';

export function NewTailoringForm() {
  const [url, setUrl] = useState('');
  const [state, setState] = useState<ProcessingState>('idle');
  const [tailoringId, setTailoringId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!url.trim()) return;

    setState('processing');

    // Simulate API call
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
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold text-text-primary mb-2">
            Create New Tailoring
          </h1>
          <p className="text-text-secondary">
            Paste a job posting URL and we'll analyze it to create a perfectly tailored application
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-3">
            <label htmlFor="job-url" className="block text-sm font-medium text-text-primary">
              Job Posting URL
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Link2 className="h-5 w-5 text-text-tertiary" />
              </div>
              <input
                id="job-url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://company.com/careers/job-posting"
                disabled={state === 'processing'}
                className="w-full pl-12 pr-4 py-3 rounded-lg border border-border-default bg-surface-elevated text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                required
              />
            </div>
            <p className="text-xs text-text-tertiary">
              We support LinkedIn, Indeed, Greenhouse, Lever, and most job boards
            </p>
          </div>

          {/* Processing states */}
          {state === 'processing' && (
            <div className="p-4 rounded-lg bg-surface-overlay border border-border-subtle animate-fade-in">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 text-brand-primary animate-spin" />
                <div className="flex-1">
                  <p className="font-medium text-text-primary">Processing job posting...</p>
                  <p className="text-sm text-text-secondary mt-0.5">
                    Analyzing requirements and extracting key information
                  </p>
                </div>
              </div>
            </div>
          )}

          {state === 'success' && tailoringId && (
            <div className="p-4 rounded-lg bg-success-bg border border-success-border animate-fade-in">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-success flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-text-primary">Job posting analyzed successfully!</p>
                  <p className="text-sm text-text-secondary mt-1">
                    Your tailoring is ready. We've analyzed the requirements and prepared a customized application.
                  </p>
                  <div className="flex gap-3 mt-4">
                    <a
                      href={`/tailorings/${tailoringId}`}
                      className="px-4 py-2 rounded-lg bg-brand-primary text-text-inverse text-sm font-medium hover:bg-brand-primary-hover transition-colors"
                    >
                      View Tailoring
                    </a>
                    <button
                      type="button"
                      onClick={resetForm}
                      className="px-4 py-2 rounded-lg bg-surface-elevated border border-border-default text-text-primary text-sm font-medium hover:bg-surface-overlay transition-colors"
                    >
                      Create Another
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {state === 'error' && (
            <div className="p-4 rounded-lg bg-error-bg border border-error-border animate-fade-in">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-error flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-text-primary">Unable to process URL</p>
                  <p className="text-sm text-text-secondary mt-1">
                    Please check the URL and try again. Make sure it's a valid job posting.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Submit button */}
          {state !== 'success' && (
            <button
              type="submit"
              disabled={!url.trim() || state === 'processing'}
              className="w-full sm:w-auto px-6 py-3 rounded-lg bg-brand-primary text-text-inverse font-medium hover:bg-brand-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
            >
              {state === 'processing' ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  Analyze Job Posting
                </>
              )}
            </button>
          )}
        </form>

        {/* Info section */}
        <div className="space-y-4 pt-4">
          <h3 className="font-semibold text-text-primary">
            What happens next?
          </h3>
          
          <div className="space-y-3">
            <div className="flex gap-4">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-primary/10 text-brand-primary flex items-center justify-center text-sm font-semibold">
                1
              </div>
              <div className="flex-1 pt-0.5">
                <p className="text-sm text-text-primary font-medium">
                  We extract key requirements
                </p>
                <p className="text-sm text-text-secondary mt-1">
                  Skills, experience level, responsibilities, and company culture
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-primary/10 text-brand-primary flex items-center justify-center text-sm font-semibold">
                2
              </div>
              <div className="flex-1 pt-0.5">
                <p className="text-sm text-text-primary font-medium">
                  AI analyzes your fit
                </p>
                <p className="text-sm text-text-secondary mt-1">
                  Matches your experience with job requirements
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-brand-primary/10 text-brand-primary flex items-center justify-center text-sm font-semibold">
                3
              </div>
              <div className="flex-1 pt-0.5">
                <p className="text-sm text-text-primary font-medium">
                  Generate tailored content
                </p>
                <p className="text-sm text-text-secondary mt-1">
                  Cover letter, resume highlights, and application strategy
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
