'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Copy, CheckCircle2, ExternalLink, Loader2, AlertCircle, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { Tailoring } from '@/types';

interface TailoringDetailProps {
  tailoringId: string;
}

export function TailoringDetail({ tailoringId }: TailoringDetailProps) {
  const [tailoring, setTailoring] = useState<Tailoring | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [showRegenConfirm, setShowRegenConfirm] = useState(false);

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

  async function handleRegenerate() {
    setShowRegenConfirm(false);
    setRegenerating(true);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(data?.detail ?? 'Regeneration failed.');
        return;
      }
      const updated = await fetch(`/api/tailorings/${tailoringId}`).then(r => r.json());
      setTailoring(updated);
      toast.success('Tailoring regenerated.');
    } catch {
      toast.error('Could not reach the server.');
    } finally {
      setRegenerating(false);
    }
  }

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
            <Button variant="outline" size="sm" onClick={() => setShowRegenConfirm(true)} disabled={regenerating} className="gap-2">
              {regenerating
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <RotateCcw className="h-4 w-4" />}
              {regenerating ? 'Regenerating…' : 'Regenerate'}
            </Button>
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
        <div className={cn(
          "prose prose-sm max-w-none text-text-primary",
          "prose-headings:text-text-primary prose-headings:font-semibold",
          "prose-p:text-text-secondary prose-p:leading-relaxed",
          "prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs",
          "prose-strong:text-text-primary",
          "prose-hr:border-border-subtle",
          regenerating && "opacity-40 pointer-events-none"
        )}>
          <ReactMarkdown>{tailoring.generated_output}</ReactMarkdown>
        </div>
      </div>

      <Dialog open={showRegenConfirm} onOpenChange={setShowRegenConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Regenerate tailoring?</DialogTitle>
            <DialogDescription>
              This will overwrite the current document with a freshly generated version. You can&apos;t undo this.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRegenConfirm(false)}>Cancel</Button>
            <Button onClick={handleRegenerate}>Regenerate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
