'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Copy, CheckCircle2, ExternalLink, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Tailoring } from '@/types';

interface TailoringDetailProps {
  tailoringId: string;
}

export function TailoringDetail({ tailoringId }: TailoringDetailProps) {
  const [tailoring, setTailoring] = useState<Tailoring | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/tailorings/${tailoringId}`);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(data?.detail ?? data?.error ?? 'Failed to load tailoring.');
          return;
        }
        setTailoring(await res.json());
      } catch {
        setError('Could not reach the server.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [tailoringId]);

  const handleCopy = () => {
    if (!tailoring) return;
    navigator.clipboard.writeText(tailoring.generated_output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand-primary" />
      </div>
    );
  }

  if (error || !tailoring) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex items-center gap-2 text-text-secondary">
          <AlertCircle className="h-5 w-5 text-error" />
          <span className="text-sm">{error ?? 'Tailoring not found.'}</span>
        </div>
      </div>
    );
  }

  const createdDate = new Date(tailoring.created_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-3xl mx-auto p-6 lg:p-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-semibold text-text-primary truncate">
              {tailoring.title ?? 'Tailoring'}
            </h1>
            <p className="text-text-secondary mt-1">
              {[tailoring.company, createdDate].filter(Boolean).join(' · ')}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {tailoring.job_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={tailoring.job_url} target="_blank" rel="noopener noreferrer" className="gap-2">
                  <ExternalLink className="h-4 w-4" />
                  View Posting
                </a>
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2">
              {copied ? (
                <><CheckCircle2 className="h-4 w-4 text-success" />Copied</>
              ) : (
                <><Copy className="h-4 w-4" />Copy</>
              )}
            </Button>
          </div>
        </div>

        {/* Generated document */}
        <div className="prose prose-sm max-w-none text-text-primary
          prose-headings:text-text-primary prose-headings:font-semibold
          prose-p:text-text-secondary prose-p:leading-relaxed
          prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs
          prose-strong:text-text-primary
          prose-hr:border-border-subtle">
          <ReactMarkdown>{tailoring.generated_output}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
