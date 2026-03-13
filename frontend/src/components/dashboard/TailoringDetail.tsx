'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import { Copy, CheckCircle2, ExternalLink, Loader2, AlertCircle, RotateCcw, Lock, Globe, Link } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { MatchAnalysis, chunksToMarkdown } from '@/components/dashboard/MatchAnalysis';
import type { Tailoring, ChunksResponse } from '@/types';

interface TailoringDetailProps {
  tailoringId: string;
}

export function TailoringDetail({ tailoringId }: TailoringDetailProps) {
  const router = useRouter();
  const [tailoring, setTailoring] = useState<Tailoring | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [showRegenConfirm, setShowRegenConfirm] = useState(false);
  const [showMakePublicConfirm, setShowMakePublicConfirm] = useState(false);
  const [showMakePrivateConfirm, setShowMakePrivateConfirm] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [activeTab, setActiveTab] = useState<'document' | 'analysis'>('document');
  const [analysisKey, setAnalysisKey] = useState(0);
  const [chunksData, setChunksData] = useState<ChunksResponse | null>(null);

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
        toastError(data?.detail ?? 'Regeneration failed.');
        return;
      }
      const updated = await fetch(`/api/tailorings/${tailoringId}`).then(r => r.json());
      setTailoring(updated);
      setAnalysisKey(k => k + 1);
      router.refresh();
      toast.success('Tailoring regenerated.');
    } catch {
      toastError('Could not reach the server.');
    } finally {
      setRegenerating(false);
    }
  }

  async function handleShare() {
    setShowMakePublicConfirm(false);
    setSharing(true);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/share`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastError(data?.detail ?? 'Could not share tailoring.');
        return;
      }
      const updated = await fetch(`/api/tailorings/${tailoringId}`).then(r => r.json());
      setTailoring(updated);
      setShareOpen(true);
      toast.success('Tailoring is now public.');
    } catch {
      toastError('Could not reach the server.');
    } finally {
      setSharing(false);
    }
  }

  async function handleUnshare() {
    setShowMakePrivateConfirm(false);
    setSharing(true);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/share`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastError(data?.detail ?? 'Could not make tailoring private.');
        return;
      }
      setTailoring(prev => prev ? { ...prev, is_public: false } : null);
      setShareOpen(false);
      toast.success('Tailoring is now private.');
    } catch {
      toastError('Could not reach the server.');
    } finally {
      setSharing(false);
    }
  }

  const handleCopy = () => {
    if (!tailoring) return;
    if (activeTab === 'analysis' && chunksData) {
      navigator.clipboard.writeText(chunksToMarkdown(chunksData, tailoring.title, tailoring.company));
    } else {
      navigator.clipboard.writeText(tailoring.generated_output);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyLink = () => {
    if (!tailoring?.public_slug) return;
    const url = `${window.location.origin}/t/${tailoring.public_slug}`;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
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

  const shareUrl = tailoring.public_slug
    ? `${window.location.origin}/t/${tailoring.public_slug}`
    : null;

  return (
    <div className="h-full flex flex-col">

      {/* Toolbar */}
      <header className="relative flex items-center h-11 px-4 border-b border-border-subtle bg-surface-base flex-shrink-0">
        {/* Left: breadcrumb */}
        <div className="flex items-center gap-1.5 min-w-0 text-sm" style={{ maxWidth: '40%' }}>
          <span className="font-medium text-text-primary truncate max-w-[180px]">
            {tailoring.title ?? 'Tailoring'}
          </span>
          {tailoring.company && (
            <>
              <span className="text-text-tertiary flex-shrink-0">/</span>
              <span className="text-text-secondary truncate max-w-[140px]">{tailoring.company}</span>
            </>
          )}
        </div>

        {/* Centre: tabs — absolutely centred in the toolbar */}
        <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-0">
          {(['document', 'analysis'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-3 h-11 text-xs font-medium border-b-2 transition-colors',
                activeTab === tab
                  ? 'border-brand-primary text-text-primary'
                  : 'border-transparent text-text-tertiary hover:text-text-secondary'
              )}
            >
              {tab === 'document' ? 'Document' : 'Match Analysis'}
            </button>
          ))}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1 flex-shrink-0 ml-auto">
          {tailoring.job_url && (
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" asChild>
              <a href={tailoring.job_url} target="_blank" rel="noopener noreferrer" title="View job posting">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => setShowRegenConfirm(true)}
            disabled={regenerating}
            title="Regenerate"
          >
            {regenerating
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <RotateCcw className="h-4 w-4" />}
          </Button>

          {/* Share popover */}
          <Popover open={shareOpen} onOpenChange={setShareOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 gap-1.5 px-2.5 text-xs font-normal ml-1"
              >
                {tailoring.is_public
                  ? <><Globe className="h-3.5 w-3.5" />Public</>
                  : <><Lock className="h-3.5 w-3.5" />Share</>}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-80 p-0">
              {tailoring.is_public && shareUrl ? (
                <div>
                  <div className="px-4 pt-4 pb-3">
                    <p className="text-sm font-medium text-text-primary mb-3">Shareable link</p>
                    <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-surface-sunken border border-border-subtle">
                      <Link className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
                      <a
                        href={shareUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 text-xs text-text-link hover:underline truncate"
                      >
                        {shareUrl}
                      </a>
                      <button
                        onClick={handleCopyLink}
                        className="flex-shrink-0 text-text-tertiary hover:text-text-primary transition-colors"
                        title="Copy link"
                      >
                        {copiedLink
                          ? <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                          : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>
                  <div className="px-4 pb-4 pt-1 border-t border-border-subtle">
                    <p className="text-xs text-text-tertiary mb-3 pt-3">Anyone with this link can view the tailoring without signing in.</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full text-xs h-8 gap-2"
                      onClick={() => { setShareOpen(false); setShowMakePrivateConfirm(true); }}
                      disabled={sharing}
                    >
                      <Lock className="h-3.5 w-3.5" />
                      Make private
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="px-4 py-4">
                  <p className="text-sm font-medium text-text-primary mb-1">Share this tailoring</p>
                  <p className="text-xs text-text-tertiary mb-4">
                    Publish a read-only link anyone can open — no sign-in required.
                  </p>
                  <Button
                    size="sm"
                    className="w-full text-xs h-8 gap-2"
                    onClick={() => { setShareOpen(false); setShowMakePublicConfirm(true); }}
                    disabled={sharing}
                  >
                    {sharing
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Globe className="h-3.5 w-3.5" />}
                    Make public
                  </Button>
                </div>
              )}
            </PopoverContent>
          </Popover>

          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={handleCopy}
            title={copied ? 'Copied' : 'Copy content'}
          >
            {copied
              ? <CheckCircle2 className="h-4 w-4 text-success" />
              : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {activeTab === 'document' ? (
          <div className="max-w-3xl mx-auto px-8 py-10">
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-text-primary leading-tight">
                {tailoring.title ?? 'Tailoring'}
              </h1>
              <p className="text-text-secondary mt-2 text-sm">
                {[tailoring.company, createdDate].filter(Boolean).join(' · ')}
              </p>
            </div>
            <div className={cn(
              "prose prose-sm max-w-none text-text-primary",
              "prose-headings:text-text-primary prose-headings:font-semibold",
              "prose-p:text-text-secondary prose-p:leading-relaxed",
              "prose-hr:my-6",
              "prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs",
              "prose-strong:text-text-primary",
              "prose-hr:border-border-subtle",
              "prose-a:text-text-link prose-a:underline prose-a:underline-offset-2",
              regenerating && "opacity-40 pointer-events-none"
            )}>
              <ReactMarkdown>{tailoring.generated_output}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <MatchAnalysis key={analysisKey} tailoringId={tailoringId} onDataChange={setChunksData} />
        )}
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

      <Dialog open={showMakePublicConfirm} onOpenChange={setShowMakePublicConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Make this tailoring public?</DialogTitle>
            <DialogDescription>
              Anyone with the link will be able to view this tailoring without signing in. You can make it private again at any time.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMakePublicConfirm(false)}>Cancel</Button>
            <Button onClick={handleShare}>Make public</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showMakePrivateConfirm} onOpenChange={setShowMakePrivateConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Make this tailoring private?</DialogTitle>
            <DialogDescription>
              The shareable link will stop working immediately. If you re-share later, the same link will be restored.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowMakePrivateConfirm(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleUnshare}>Make private</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
