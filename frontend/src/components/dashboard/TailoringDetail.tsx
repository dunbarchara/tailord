'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import { Copy, CheckCircle2, Loader2, AlertCircle, RotateCcw, Lock, Globe, Link, Info } from 'lucide-react';
import { SiNotion } from 'react-icons/si';
import { toast } from 'sonner';
import { cn, toastError, formatElapsed } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { MatchAnalysis, chunksToMarkdown } from '@/components/dashboard/MatchAnalysis';
import { JobPosting } from '@/components/dashboard/JobPosting';
import type { Tailoring, ChunksResponse } from '@/types';

const POLL_INTERVAL = 3000;


function NotionViewRow({
  label,
  pageUrl,
  exporting,
  disabled,
  disabledReason,
  onExport,
}: {
  label: string
  pageUrl: string | null
  exporting: boolean
  disabled?: boolean
  disabledReason?: string
  onExport: () => void
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-text-secondary">{label}</span>
        {pageUrl && (
          <a
            href={pageUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-text-link hover:underline"
          >
            Open
          </a>
        )}
      </div>
      <Button
        size="sm"
        variant={pageUrl ? 'outline' : 'default'}
        className="w-full text-xs h-8 gap-2"
        onClick={onExport}
        disabled={exporting || disabled}
        title={disabled ? disabledReason : undefined}
      >
        {exporting
          ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
          : pageUrl
            ? <RotateCcw className="h-3.5 w-3.5" />
            : <SiNotion className="h-3.5 w-3.5" />}
        {pageUrl ? 'Refresh' : disabled ? disabledReason! : 'Export'}
      </Button>
    </div>
  );
}

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
  const [regenSsePhase, setRegenSsePhase] = useState<string | null>(null);
  // Tick counter to force re-render of elapsed time display every second
  const [, setElapsedTick] = useState(0);
  const [shareOpen, setShareOpen] = useState(false);
  const [showRegenConfirm, setShowRegenConfirm] = useState(false);
  const [showMakePrivateConfirm, setShowMakePrivateConfirm] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [activeTab, setActiveTab] = useState<'letter' | 'posting' | 'analysis'>('letter');
  const [chunksData, setChunksData] = useState<ChunksResponse | null>(null);
  const [chunksError, setChunksError] = useState<string | null>(null);
  const [notionConnected, setNotionConnected] = useState(false);
  const [exportingNotionLetter, setExportingNotionLetter] = useState(false);
  const [exportingNotionPosting, setExportingNotionPosting] = useState(false);
  const [notionOpen, setNotionOpen] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [tailoringRes, userRes] = await Promise.all([
          fetch(`/api/tailorings/${tailoringId}`),
          fetch('/api/users'),
        ]);
        if (!tailoringRes.ok) {
          const data = await tailoringRes.json().catch(() => ({}));
          setError(data?.detail ?? data?.error ?? 'Failed to load tailoring.');
          return;
        }
        const [tailoringData, userData] = await Promise.all([
          tailoringRes.json(),
          userRes.ok ? userRes.json() : null,
        ]);
        setTailoring(tailoringData);
        setNotionConnected(!!userData?.notion_workspace_name);
      } catch {
        setError('Could not reach the server.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [tailoringId]);

  // Poll generation status every 2s when the tailoring is still being generated
  useEffect(() => {
    if (!tailoring || tailoring.generation_status !== 'generating') return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/tailorings/${tailoringId}`);
        if (!res.ok) return;
        const data = await res.json();
        const titleJustResolved = !tailoring?.title && data.title;
        setTailoring(data);
        if (titleJustResolved || data.generation_status !== 'generating') {
          router.refresh(); // keep sidebar label + icon in sync
        }
        if (data.generation_status !== 'generating') {
          clearInterval(interval);
          if (data.generation_status === 'ready') {
            setRegenerating(false);
            setRegenSsePhase(null);
            setChunksData(null); // reset so chunk polling restarts
          }
        }
      } catch { /* ignore */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [tailoringId, tailoring?.generation_status]);

  // Tick every second to update elapsed time display when generating
  useEffect(() => {
    if (!tailoring || tailoring.generation_status !== 'generating') return;
    const interval = setInterval(() => setElapsedTick(t => t + 1), 1000);
    return () => clearInterval(interval);
  }, [tailoring?.generation_status]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    async function fetchChunks() {
      try {
        const res = await fetch(`/api/tailorings/${tailoringId}/chunks`);
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setChunksError(body?.detail ?? 'Failed to load match data.');
          if (interval) clearInterval(interval);
          return;
        }
        const json: ChunksResponse = await res.json();
        setChunksData(json);
        if (json.enrichment_status === 'complete' || json.enrichment_status === 'error') {
          if (interval) clearInterval(interval);
        }
      } catch {
        setChunksError('Could not reach the server.');
        if (interval) clearInterval(interval);
      }
    }

    fetchChunks();
    interval = setInterval(fetchChunks, POLL_INTERVAL);
    return () => { if (interval) clearInterval(interval); };
  }, [tailoringId]);

  const REGEN_SSE_LABELS: Record<string, string> = {
    scraping: 'Fetching job posting...',
  };

  async function handleRegenerate() {
    setShowRegenConfirm(false);
    setRegenerating(true);
    setRegenSsePhase(null);

    try {
      const res = await fetch(`/api/tailorings/${tailoringId}`, { method: 'POST' });
      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}));
        toastError(data?.detail ?? 'Regeneration failed.');
        setRegenerating(false);
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
            setRegenSsePhase(data);
          } else if (event === 'ready') {
            // Scraping done; extraction + matching + generation running in background.
            // Switch to polling (the generation_status poll effect takes over).
            setRegenSsePhase(null);
            setTailoring(prev => prev ? {
              ...prev,
              generated_output: null,
              generation_status: 'generating',
              generation_stage: 'extracting',
              generation_error: null,
            } : null);
            router.refresh(); // update sidebar to show generating indicator
            return;
          } else if (event === 'error') {
            const payload = JSON.parse(data);
            toastError(payload.detail ?? 'Regeneration failed.');
            setRegenerating(false);
            setRegenSsePhase(null);
            return;
          }
        }
      }
    } catch {
      toastError('Could not reach the server.');
      setRegenerating(false);
      setRegenSsePhase(null);
    }
  }

  async function handleToggleShare(view: 'letter' | 'posting', value: boolean) {
    if (!tailoring) return;
    setSharing(true);
    try {
      const newLetter = view === 'letter' ? value : tailoring.letter_public;
      const newPosting = view === 'posting' ? value : tailoring.posting_public;
      const res = await fetch(`/api/tailorings/${tailoringId}/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ letter: newLetter, posting: newPosting }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toastError(data?.detail ?? 'Could not update sharing.');
        return;
      }
      const shareData = await res.json();
      setTailoring(prev => prev ? {
        ...prev,
        letter_public: shareData.letter_public,
        posting_public: shareData.posting_public,
        is_public: shareData.letter_public || shareData.posting_public,
        public_slug: shareData.public_slug ?? prev.public_slug,
      } : null);
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
      setTailoring(prev => prev ? { ...prev, is_public: false, letter_public: false, posting_public: false } : null);
      setShareOpen(false);
      toast.success('Tailoring is now private.');
    } catch {
      toastError('Could not reach the server.');
    } finally {
      setSharing(false);
    }
  }

  async function handleExportToNotion(view: 'letter' | 'posting') {
    const setExporting = view === 'letter' ? setExportingNotionLetter : setExportingNotionPosting;
    setExporting(true);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/export/notion?view=${view}`, { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 403 && data?.detail === 'notion_disconnected') {
          setNotionConnected(false);
          toastError('Notion access was revoked. Reconnect in Settings.');
        } else {
          toastError(data?.detail ?? 'Export failed.');
        }
        return;
      }
      if (view === 'letter') {
        setTailoring(prev => prev ? { ...prev, notion_page_url: data.page_url } : null);
        toast.success(tailoring?.notion_page_url ? 'Notion letter page refreshed.' : 'Letter exported to Notion.');
      } else {
        setTailoring(prev => prev ? { ...prev, notion_posting_page_url: data.page_url } : null);
        toast.success(tailoring?.notion_posting_page_url ? 'Notion posting page refreshed.' : 'Posting exported to Notion.');
      }
    } catch {
      toastError('Could not reach the server.');
    } finally {
      setExporting(false);
    }
  }

  const handleCopy = () => {
    if (!tailoring) return;
    if (activeTab === 'analysis' && chunksData) {
      navigator.clipboard.writeText(chunksToMarkdown(chunksData, tailoring.title, tailoring.company));
    } else if (tailoring.generated_output) {
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

  const letterOn = tailoring.letter_public;
  const postingOn = tailoring.posting_public;
  const anyPublic = letterOn || postingOn;

  function ShareButtonLabel() {
    if (letterOn && postingOn) return <><Globe className="h-3.5 w-3.5" />Public</>;
    if (letterOn) return <><Globe className="h-3.5 w-3.5" />Public · Letter</>;
    if (postingOn) return <><Globe className="h-3.5 w-3.5" />Public · Posting</>;
    return <><Lock className="h-3.5 w-3.5" />Share</>;
  }

  return (
    <div className="h-full flex flex-col">

      {/* Toolbar */}
      <header className="relative flex items-center h-11 px-4 border-b border-border-subtle bg-surface-base flex-shrink-0">
        {/* Left: breadcrumb + date */}
        <div className="flex items-center gap-1.5 min-w-0 text-sm" style={{ maxWidth: '50%' }}>
          <span className="font-medium text-text-primary truncate max-w-[180px]">
            {tailoring.title ?? 'Tailoring'}
          </span>
          {tailoring.company && (
            <>
              <span className="text-text-tertiary flex-shrink-0">/</span>
              <span className="text-text-secondary truncate max-w-[140px]">{tailoring.company}</span>
            </>
          )}
          <span className="text-text-tertiary flex-shrink-0">·</span>
          <span className="text-text-tertiary text-xs flex-shrink-0">{createdDate}</span>
        </div>

        {/* Centre: tabs — absolutely centred in the toolbar */}
        <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-0">
          {(['letter', 'posting', 'analysis'] as const).map(tab => (
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
              {tab === 'letter' ? 'Letter' : tab === 'posting' ? 'Posting' : 'Analysis'}
            </button>
          ))}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1 flex-shrink-0 ml-auto">
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
                <ShareButtonLabel />
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-80 p-0">
              <div className="px-4 pt-4 pb-3">
                {anyPublic && shareUrl ? (
                  <>
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
                  </>
                ) : (
                  <>
                    <p className="text-sm font-medium text-text-primary mb-1">Share this tailoring</p>
                    <p className="text-xs text-text-tertiary mb-3">
                      Publish read-only views — no sign-in required.
                    </p>
                  </>
                )}
              </div>

              {/* Toggles */}
              <div className="px-4 pb-3 space-y-3 border-t border-border-subtle pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-primary">Advocacy Letter</span>
                  <Switch
                    checked={letterOn}
                    onCheckedChange={v => handleToggleShare('letter', v)}
                    disabled={sharing}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-primary">Job Posting</span>
                  <Switch
                    checked={postingOn}
                    onCheckedChange={v => handleToggleShare('posting', v)}
                    disabled={sharing}
                  />
                </div>
              </div>

              {/* Note */}
              <div className="px-4 pb-3 pt-1">
                <p className="flex items-start gap-1.5 text-xs text-text-tertiary leading-relaxed">
                  <Info className="h-3 w-3 mt-0.5 flex-shrink-0" />
                  In the public job posting view, gap matches are hidden and partial matches appear as green.
                </p>
              </div>

              {/* Make private */}
              {anyPublic && (
                <div className="px-4 pb-4 border-t border-border-subtle pt-3">
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
              )}
            </PopoverContent>
          </Popover>

          <Popover open={notionOpen} onOpenChange={setNotionOpen}>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0" title="Notion">
                  <SiNotion className="h-4 w-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-72 p-0">
                <div className="px-4 pt-4 pb-3">
                  <p className="text-sm font-medium text-text-primary mb-3">Export to Notion</p>
                  {!notionConnected ? (
                    <p className="text-xs text-text-tertiary">
                      Connect your Notion workspace in{' '}
                      <a href="/dashboard/settings" className="text-text-link hover:underline">Settings</a>{' '}
                      to export.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {/* Letter row */}
                      <NotionViewRow
                        label="Letter"
                        pageUrl={tailoring.notion_page_url}
                        exporting={exportingNotionLetter}
                        disabled={exportingNotionPosting}
                        onExport={() => handleExportToNotion('letter')}
                      />
                      {/* Posting row */}
                      <NotionViewRow
                        label="Posting"
                        pageUrl={tailoring.notion_posting_page_url}
                        exporting={exportingNotionPosting}
                        disabled={exportingNotionLetter || chunksData?.enrichment_status !== 'complete'}
                        disabledReason={chunksData?.enrichment_status !== 'complete' ? 'Enrichment not complete' : undefined}
                        onExport={() => handleExportToNotion('posting')}
                      />
                    </div>
                  )}
                </div>
              </PopoverContent>
            </Popover>

          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={handleCopy}
            disabled={activeTab === 'posting' || !tailoring.generated_output}
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
        {activeTab === 'letter' && (
          <div className="max-w-3xl mx-auto px-6 py-10">
            <header className="mb-8 pb-5 border-b border-border-subtle">
              <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary mb-1">
                {tailoring.company ?? 'Tailoring'}
              </p>
              <h1 className="text-xl font-semibold text-text-primary">
                {tailoring.title ?? ''}
              </h1>
              {tailoring.job_url && (
                <a
                  href={tailoring.job_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block mt-2 text-sm text-text-link hover:underline"
                >
                  View job posting →
                </a>
              )}
            </header>

            {/* SSE phase banner: scraping/extracting during regen */}
            {regenSsePhase && (
              <div className="flex items-center gap-2 mb-6 text-sm text-text-secondary animate-fade-in">
                <Loader2 className="h-4 w-4 text-brand-primary animate-spin flex-shrink-0" />
                {REGEN_SSE_LABELS[regenSsePhase] ?? 'Updating…'}
              </div>
            )}

            {/* Generation phase list: matching/generating (initial load or regen background task) */}
            {tailoring.generation_status === 'generating' && !regenSsePhase && (() => {
              const stage = tailoring.generation_stage;
              const startedAt = tailoring.generation_started_at
                ? new Date(tailoring.generation_started_at).getTime()
                : null;
              const totalElapsed = startedAt
                ? Math.floor((Date.now() - startedAt) / 1000)
                : 0;
              const matchingDone = stage === 'generating';
              const extractingDone = stage === 'matching' || stage === 'generating';
              const phases = [
                { key: 'extracting', label: 'Extracting requirements', done: extractingDone, running: stage === 'extracting' },
                { key: 'matching',   label: 'Matching to your profile', done: matchingDone, running: stage === 'matching' },
                { key: 'generating', label: 'Writing your tailoring',   done: false,        running: stage === 'generating' },
              ];
              return (
                <div className="space-y-2 mb-8 animate-fade-in">
                  {phases.filter(({ done, running }) => done || running).map(({ key, label, done, running }) => (
                    <div key={key} className="flex items-center gap-2.5 text-sm">
                      {done
                        ? <CheckCircle2 className="h-4 w-4 text-success flex-shrink-0" />
                        : <Loader2 className="h-4 w-4 text-brand-primary animate-spin flex-shrink-0" />}
                      <span className="text-text-secondary">
                        {label}{running ? '...' : ''}
                        {running && startedAt && (
                          <span className="text-text-tertiary"> · {formatElapsed(totalElapsed)}</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              );
            })()}

            {/* Error state */}
            {tailoring.generation_status === 'error' && (
              <div className="mb-8 flex items-start gap-3 text-sm">
                <AlertCircle className="h-4 w-4 text-error flex-shrink-0 mt-0.5" />
                <span className="text-text-secondary">
                  {tailoring.generation_error ?? 'Generation failed. Try regenerating.'}
                </span>
              </div>
            )}

            {tailoring.generated_output && (
              <div className={cn(
                "prose prose-sm max-w-none text-text-primary",
                "prose-headings:text-text-primary prose-headings:font-semibold",
                "prose-p:text-text-secondary prose-p:leading-relaxed",
                "prose-hr:my-6",
                "prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs",
                "prose-strong:text-text-primary",
                "prose-hr:border-border-subtle",
                "prose-a:text-text-link prose-a:underline prose-a:underline-offset-2",
                tailoring.generation_status === 'generating' && "opacity-40",
              )}>
                <ReactMarkdown>{tailoring.generated_output}</ReactMarkdown>
              </div>
            )}
          </div>
        )}
        {activeTab === 'posting' && (
          <JobPosting
            data={chunksData}
            error={chunksError}
            title={tailoring.title}
            company={tailoring.company}
            jobUrl={tailoring.job_url}
            generationReady={tailoring.generation_status === 'ready'}
          />
        )}
        {activeTab === 'analysis' && (
          <MatchAnalysis data={chunksData} error={chunksError} />
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
