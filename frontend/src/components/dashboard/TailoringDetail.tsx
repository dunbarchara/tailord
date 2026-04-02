'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import {
  Copy, CheckCircle2, Loader2, AlertCircle, RotateCcw,
  Lock, Globe, Link as LinkIcon, ChevronDown,
} from 'lucide-react';
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
import { FitAnalysis, fitAnalysisToText } from '@/components/dashboard/FitAnalysis';
import { JobPosting } from '@/components/dashboard/JobPosting';
import { DebugPanel } from '@/components/dashboard/DebugPanel';
import type { Tailoring, ChunksResponse } from '@/types';

const POLL_INTERVAL = 3000;

/* ─── Shared button styles ─────────────────────────────────────────────── */

// Icon-only button (Open Live Preview style)
const iconBtnCls =
  'inline-flex items-center justify-center h-8 w-8 rounded-[10px] ' +
  'bg-surface-elevated border border-border-default text-text-secondary ' +
  'hover:bg-surface-overlay hover:border-border-strong hover:text-text-primary ' +
  'transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-surface-elevated disabled:hover:border-border-default disabled:hover:text-text-secondary';

// Text button (Publish style)
const textBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-2.5 rounded-[10px] ' +
  'bg-surface-elevated border border-border-default text-text-secondary ' +
  'text-sm font-normal tracking-[-0.1px] ' +
  'hover:bg-surface-overlay hover:border-border-strong hover:text-text-primary ' +
  'transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

// Vertical divider between button groups
function ToolDivider() {
  return <div className="h-4 w-px bg-border-default mx-0.5 shrink-0" />;
}

/* ─── Notion export row ────────────────────────────────────────────────── */

function NotionViewRow({
  label,
  pageUrl,
  exporting,
  disabled,
  disabledReason,
  onExport,
}: {
  label: string;
  pageUrl: string | null;
  exporting: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onExport: () => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary">{label}</p>
        {pageUrl && (
          <a
            href={pageUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-text-link hover:underline"
          >
            Open in Notion →
          </a>
        )}
      </div>
      <button
        type="button"
        onClick={onExport}
        disabled={exporting || disabled}
        title={disabled ? disabledReason : undefined}
        className={cn(textBtnCls, 'shrink-0')}
      >
        {exporting
          ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
          : pageUrl
            ? <RotateCcw className="h-3.5 w-3.5" />
            : <SiNotion className="h-3.5 w-3.5" />}
        {pageUrl ? 'Refresh' : disabled ? (disabledReason ?? 'Export') : 'Export'}
      </button>
    </div>
  );
}

/* ─── Main component ────────────────────────────────────────────────────── */

interface TailoringDetailProps {
  tailoringId: string;
}

export function TailoringDetail({ tailoringId }: TailoringDetailProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDebug = searchParams?.get('debug') === '1';
  const [tailoring, setTailoring] = useState<Tailoring | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [regenSsePhase, setRegenSsePhase] = useState<string | null>(null);
  const [, setElapsedTick] = useState(0);
  const [shareOpen, setShareOpen] = useState(false);
  const [showRegenConfirm, setShowRegenConfirm] = useState(false);
  const [showMakePrivateConfirm, setShowMakePrivateConfirm] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [activeTab, setActiveTab] = useState<'letter' | 'posting' | 'analysis' | 'debug'>('analysis');
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollRef.current?.scrollTo({ top: 0 }); }, [activeTab]);
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
          router.refresh();
        }
        if (data.generation_status !== 'generating') {
          clearInterval(interval);
          if (data.generation_status === 'ready') {
            setRegenerating(false);
            setRegenSsePhase(null);
            setChunksData(null);
          }
        }
      } catch { /* ignore */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [tailoringId, tailoring?.generation_status]);

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
            setRegenSsePhase(null);
            setTailoring(prev => prev ? {
              ...prev,
              generated_output: null,
              generation_status: 'generating',
              generation_stage: 'extracting',
              generation_error: null,
            } : null);
            router.refresh();
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
      navigator.clipboard.writeText(fitAnalysisToText(chunksData, tailoring.title, tailoring.company));
    } else if (tailoring.generated_output) {
      navigator.clipboard.writeText(tailoring.generated_output);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyLink = () => {
    if (!tailoring?.public_slug || !tailoring?.author_username_slug) return;
    const url = `${window.location.origin}/u/${tailoring.author_username_slug}/${tailoring.public_slug}`;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-surface-elevated">
        <Loader2 className="h-6 w-6 animate-spin text-brand-primary" />
      </div>
    );
  }

  if (error || !tailoring) {
    return (
      <div className="h-full flex items-center justify-center bg-surface-elevated">
        <div className="flex items-center gap-2 text-text-secondary">
          <AlertCircle className="h-5 w-5 text-error" />
          <span className="text-sm">{error ?? 'Tailoring not found.'}</span>
        </div>
      </div>
    );
  }

  const createdDate = new Date(tailoring.created_at).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  });

  const shareUrl = tailoring.public_slug && tailoring.author_username_slug
    ? `${window.location.origin}/u/${tailoring.author_username_slug}/${tailoring.public_slug}`
    : null;

  const letterOn = tailoring.letter_public;
  const postingOn = tailoring.posting_public;
  const anyPublic = letterOn || postingOn;

  const canCopy = activeTab !== 'posting' && activeTab !== 'debug' && (
    activeTab === 'analysis' ? !!chunksData : !!tailoring.generated_output
  );

  return (
    <div className="h-full flex flex-col bg-surface-elevated">

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="shrink-0 grid grid-cols-[1fr_auto_1fr] items-center h-12 px-3 gap-2 bg-surface-elevated border-b border-border-subtle">

        {/* Left: title / company / debug pill */}
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-sm font-medium text-text-primary tracking-[-0.1px] truncate max-w-[200px]">
            {tailoring.title ?? 'Tailoring'}
          </span>
          {tailoring.company && (
            <>
              <span className="text-text-tertiary shrink-0 text-sm">/</span>
              <span className="text-sm font-medium text-text-tertiary tracking-[-0.1px] truncate max-w-[160px]">
                {tailoring.company}
              </span>
            </>
          )}
          <span className="text-text-disabled shrink-0 text-sm">·</span>
          <span className="text-xs text-text-disabled shrink-0">{createdDate}</span>
          {isDebug && (
            <span className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/40">
              debug
            </span>
          )}
        </div>

        {/* Center: segment tabs — grid col 2, naturally centered */}
        <div className="flex items-center gap-1.5">
          {/* Analysis pill */}
          <button
            type="button"
            onClick={() => setActiveTab('analysis')}
            className={cn(
              'px-3 h-7 text-sm font-normal tracking-[-0.1px] rounded-[8px] border transition-colors whitespace-nowrap',
              activeTab === 'analysis'
                ? 'bg-surface-overlay border-border-strong text-text-primary'
                : 'bg-surface-elevated border-border-default text-text-secondary hover:bg-surface-overlay hover:border-border-strong hover:text-text-primary'
            )}
          >
            Analysis
          </button>

          {/* Text divider */}
          <span className="text-border-strong text-sm select-none">|</span>

          {/* Posting + Letter joined pill */}
          <div className="flex rounded-[8px] border border-border-default overflow-hidden">
            <button
              type="button"
              onClick={() => setActiveTab('posting')}
              className={cn(
                'px-3 h-7 text-sm font-normal tracking-[-0.1px] border-r border-border-default transition-colors whitespace-nowrap',
                activeTab === 'posting'
                  ? 'bg-surface-overlay text-text-primary'
                  : 'bg-surface-elevated text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
              )}
            >
              Posting
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('letter')}
              className={cn(
                'px-3 h-7 text-sm font-normal tracking-[-0.1px] transition-colors whitespace-nowrap',
                activeTab === 'letter'
                  ? 'bg-surface-overlay text-text-primary'
                  : 'bg-surface-elevated text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
              )}
            >
              Letter
            </button>
          </div>

          {/* Debug tab — only when ?debug=1 */}
          {isDebug && (
            <>
              <span className="text-border-strong text-sm select-none">|</span>
              <button
                type="button"
                onClick={() => setActiveTab('debug')}
                className={cn(
                  'px-3 h-7 text-sm font-normal tracking-[-0.1px] rounded-[8px] border transition-colors whitespace-nowrap',
                  activeTab === 'debug'
                    ? 'bg-surface-overlay border-border-strong text-text-primary'
                    : 'bg-surface-elevated border-border-default text-text-secondary hover:bg-surface-overlay hover:border-border-strong hover:text-text-primary'
                )}
              >
                Debug
              </button>
            </>
          )}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1 justify-end">

          {/* Copy */}
          <button
            type="button"
            onClick={handleCopy}
            disabled={!canCopy}
            title={copied ? 'Copied!' : 'Copy content'}
            className={cn(iconBtnCls, copied && 'text-success hover:text-success')}
          >
            {copied
              ? <CheckCircle2 className="h-4 w-4" />
              : <Copy className="h-4 w-4" />}
          </button>

          {/* Notion */}
          <Popover open={notionOpen} onOpenChange={setNotionOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                title="Export to Notion"
                className={iconBtnCls}
              >
                <SiNotion className="h-4 w-4" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" sideOffset={6} className="w-72 p-0 rounded-2xl border-border-subtle shadow-lg overflow-hidden">
              <div className="px-4 pt-4 pb-3">
                <p className="text-sm font-semibold text-text-primary tracking-[-0.1px]">Export to Notion</p>
                <p className="text-sm text-text-secondary mt-0.5">Send your tailoring directly to Notion.</p>
              </div>
              <div className="border-t border-border-subtle px-4 py-3">
                {!notionConnected ? (
                  <p className="text-sm text-text-secondary">
                    Connect your Notion workspace in{' '}
                    <a href="/dashboard/settings" className="text-text-link hover:underline">Settings</a>{' '}
                    to export.
                  </p>
                ) : (
                  <div className="space-y-3">
                    <NotionViewRow
                      label="Posting"
                      pageUrl={tailoring.notion_posting_page_url ?? null}
                      exporting={exportingNotionPosting}
                      disabled={exportingNotionLetter || chunksData?.enrichment_status !== 'complete'}
                      disabledReason={chunksData?.enrichment_status !== 'complete' ? 'Enrichment not ready' : undefined}
                      onExport={() => handleExportToNotion('posting')}
                    />
                    <NotionViewRow
                      label="Letter"
                      pageUrl={tailoring.notion_page_url ?? null}
                      exporting={exportingNotionLetter}
                      disabled={exportingNotionPosting}
                      onExport={() => handleExportToNotion('letter')}
                    />
                  </div>
                )}
              </div>
            </PopoverContent>
          </Popover>

          <ToolDivider />

          {/* Regenerate */}
          <button
            type="button"
            onClick={() => setShowRegenConfirm(true)}
            disabled={regenerating}
            title={regenerating ? 'Regenerating…' : 'Regenerate'}
            className={iconBtnCls}
          >
            {regenerating
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <RotateCcw className="h-4 w-4" />}
          </button>

          <ToolDivider />

          {/* Share — Publish style */}
          <Popover open={shareOpen} onOpenChange={setShareOpen}>
            <PopoverTrigger asChild>
              <button type="button" className={textBtnCls}>
                {anyPublic
                  ? <Globe className="h-3.5 w-3.5 text-brand-accent" />
                  : <Lock className="h-3.5 w-3.5" />}
                <span>{anyPublic ? 'Public' : 'Share'}</span>
                <ChevronDown className="h-3.5 w-3.5 text-text-disabled" />
              </button>
            </PopoverTrigger>

            <PopoverContent align="end" sideOffset={6} className="w-80 p-0 rounded-2xl border-border-subtle shadow-lg overflow-hidden">

              {/* Header */}
              <div className="px-4 pt-4 pb-3">
                <p className="text-sm font-semibold text-text-primary tracking-[-0.1px]">
                  {anyPublic ? 'Shared' : 'Share this tailoring'}
                </p>
                <p className="text-sm text-text-secondary mt-0.5">
                  Publish read-only views — no sign-in required.
                </p>
              </div>

              {/* Shareable link (when public) */}
              {anyPublic && shareUrl && (
                <div className="border-t border-border-subtle px-4 py-3">
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-base border border-border-subtle">
                    <LinkIcon className="h-3.5 w-3.5 text-text-tertiary shrink-0" />
                    <a
                      href={shareUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 text-xs text-text-link hover:underline truncate"
                    >
                      {shareUrl}
                    </a>
                    <button
                      type="button"
                      onClick={handleCopyLink}
                      className="shrink-0 text-text-tertiary hover:text-text-primary transition-colors"
                      title="Copy link"
                    >
                      {copiedLink
                        ? <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                        : <Copy className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>
              )}

              {/* Toggles */}
              <div className="border-t border-border-subtle px-4 py-3 space-y-3">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-text-primary">Job Posting</p>
                    <p className="text-xs text-text-tertiary mt-0.5">Gap matches hidden, partials shown as green</p>
                  </div>
                  <Switch
                    checked={postingOn}
                    onCheckedChange={v => handleToggleShare('posting', v)}
                    disabled={sharing}
                  />
                </div>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-text-primary">Advocacy Letter</p>
                    <p className="text-xs text-text-tertiary mt-0.5">Share the generated letter</p>
                  </div>
                  <Switch
                    checked={letterOn}
                    onCheckedChange={v => handleToggleShare('letter', v)}
                    disabled={sharing}
                  />
                </div>
              </div>

              {/* Make private */}
              {anyPublic && (
                <div className="border-t border-border-subtle px-4 py-3">
                  <button
                    type="button"
                    onClick={() => { setShareOpen(false); setShowMakePrivateConfirm(true); }}
                    disabled={sharing}
                    className={cn(
                      textBtnCls,
                      'w-full justify-center text-red-600 border-red-200 dark:border-red-900/40 ',
                      'hover:bg-red-50 dark:hover:bg-red-950/20 hover:text-red-600 hover:border-red-300'
                    )}
                  >
                    <Lock className="h-3.5 w-3.5" />
                    Make private
                  </button>
                </div>
              )}
            </PopoverContent>
          </Popover>

        </div>
      </div>

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto custom-scrollbar">
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

            {regenSsePhase && (
              <div className="flex items-center gap-2 mb-6 text-sm text-text-secondary animate-fade-in">
                <Loader2 className="h-4 w-4 text-brand-primary animate-spin flex-shrink-0" />
                {REGEN_SSE_LABELS[regenSsePhase] ?? 'Updating…'}
              </div>
            )}

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
                { key: 'matching', label: 'Matching to your profile', done: matchingDone, running: stage === 'matching' },
                { key: 'generating', label: 'Writing your tailoring', done: false, running: stage === 'generating' },
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
          <FitAnalysis data={chunksData} error={chunksError} title={tailoring.title} company={tailoring.company} />
        )}
        {activeTab === 'debug' && (
          <DebugPanel
            tailoringId={tailoring.id}
            chunksData={chunksData}
            chunksError={chunksError}
            title={tailoring.title}
            company={tailoring.company}
          />
        )}
      </div>

      {/* ── Dialogs ──────────────────────────────────────────────────────── */}

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
