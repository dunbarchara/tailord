'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Copy, CheckCircle2, Loader2, AlertCircle, RotateCcw,
  Lock, Globe, Link as LinkIcon, ChevronDown, Info,
} from 'lucide-react';
import { SiNotion } from 'react-icons/si';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
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
import { AnalysisView, fitAnalysisToText } from '@/components/dashboard/AnalysisView';
import { JobPosting } from '@/components/dashboard/JobPosting';
import { DebugPanel } from '@/components/dashboard/DebugPanel';
import { AdvocacyLetter } from '@/components/dashboard/AdvocacyLetter';
import { GenerationView } from '@/components/dashboard/GenerationView';
import { TailoringErrorState } from '@/components/dashboard/TailoringErrorState';
import type { Tailoring, ChunksResponse, ExperienceChunk } from '@/types';

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
  tailoringId?: string;
  readOnly?: boolean;
  initialTailoring?: Tailoring;
  initialChunks?: ChunksResponse;
}

export function TailoringDetail({ tailoringId: tailoringIdProp, readOnly, initialTailoring, initialChunks }: TailoringDetailProps) {
  const tailoringId = tailoringIdProp ?? initialTailoring?.id ?? '';
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
  const [gapResponses, setGapResponses] = useState<ExperienceChunk[] | null>(null);
  const [notionConnected, setNotionConnected] = useState(false);
  const [userName, setUserName] = useState<string | null>(null);
  const [exportingNotionLetter, setExportingNotionLetter] = useState(false);
  const [exportingNotionPosting, setExportingNotionPosting] = useState(false);
  const [notionOpen, setNotionOpen] = useState(false);
  // Track enrichment status transitions so we can call router.refresh() exactly once
  // when enrichment settles, keeping the sidebar spinner alive through the enrichment phase.
  const prevEnrichmentStatusRef = useRef<string | null | undefined>(undefined);
  const [gapAnalysisSettled, setGapAnalysisSettled] = useState(false);

  useEffect(() => {
    // When initialTailoring is provided (demo/readOnly mode), skip the API fetch.
    if (initialTailoring) {
      setTailoring(initialTailoring);
      if (initialTailoring.gap_analysis_status === 'complete') setGapAnalysisSettled(true);
      setLoading(false);
      return;
    }
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
        if (tailoringData.gap_analysis_status === 'complete') {
          setGapAnalysisSettled(true);
        }
        if (tailoringData.generation_status === 'error') {
          router.refresh();
        }
        setNotionConnected(!!userData?.notion_workspace_name);
        const preferredName = [userData?.preferred_first_name, userData?.preferred_last_name]
          .filter(Boolean).join(' ').trim() || userData?.name || null;
        setUserName(preferredName);
      } catch {
        setError('Could not reach the server.');
      } finally {
        setLoading(false);
      }
    }
    load();
    // router is stable across renders in Next.js — safe to omit from deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tailoringId, initialTailoring]);

  useEffect(() => {
    if (!tailoring || tailoring.generation_status !== 'generating') return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/tailorings/${tailoringId}`);
        if (!res.ok) return;
        const data = await res.json();
        const titleJustResolved = !tailoring?.title && data.title;
        setTailoring(data);
        // Refresh on title resolution (sidebar shows the title) and on error (shows Failed badge).
        // Do NOT refresh when status → 'ready': the sidebar spinner should stay until enrichment
        // completes. The chunks polling effect will call router.refresh() when enrichment settles.
        if (titleJustResolved || data.generation_status === 'error') {
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
    // Intentional: depend only on generation_status, not the full tailoring object, so the
    // interval isn't reset on every field update — only on generation state transitions.
    // router is stable across renders in Next.js.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tailoringId, tailoring?.generation_status]);

  useEffect(() => {
    const enrichmentDone = chunksData?.enrichment_status === 'complete' || chunksData?.enrichment_status === 'error';
    if (!tailoring || (tailoring.generation_status !== 'generating' && enrichmentDone)) return;
    const interval = setInterval(() => setElapsedTick(t => t + 1), 1000);
    return () => clearInterval(interval);
    // Intentional: depend on specific sub-fields to avoid spurious interval restarts on unrelated updates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tailoring?.generation_status, chunksData?.enrichment_status]);

  useEffect(() => {
    // When initialChunks is provided (demo/readOnly mode), use them directly — no polling.
    if (initialChunks) {
      setChunksData(initialChunks);
      prevEnrichmentStatusRef.current = initialChunks.enrichment_status;
      return;
    }
    // Don't poll if generation already failed — enrichment will never complete
    if (tailoring?.generation_status === 'error') return;

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
        const prevStatus = prevEnrichmentStatusRef.current;
        prevEnrichmentStatusRef.current = json.enrichment_status;
        const enrichmentJustSettled =
          (json.enrichment_status === 'complete' || json.enrichment_status === 'error') &&
          prevStatus !== undefined &&  // skip on first fetch (no transition observed yet)
          prevStatus !== 'complete' && prevStatus !== 'error';
        if (json.enrichment_status === 'complete' || json.enrichment_status === 'error') {
          if (interval) clearInterval(interval);
        }
        if (enrichmentJustSettled) {
          router.refresh();
        }
      } catch {
        setChunksError('Could not reach the server.');
        if (interval) clearInterval(interval);
      }
    }
    fetchChunks();
    interval = setInterval(fetchChunks, POLL_INTERVAL);
    return () => { if (interval) clearInterval(interval); };
    // Intentional: restart chunks polling only on generation_status transitions.
    // router is stable across renders in Next.js.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tailoringId, tailoring?.generation_status, initialChunks]);

  // Fetch gap responses from experience chunks once tailoring is ready.
  useEffect(() => {
    if (readOnly) return;
    if (tailoring?.generation_status !== 'ready') return;
    fetch('/api/experience/chunks')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.gap_response) setGapResponses(d.gap_response); })
      .catch(() => {});
  }, [tailoring?.generation_status, readOnly]);

  // Poll for gap_analysis_status after enrichment completes.
  // Gap analysis runs after chunk enrichment — we must not reveal the full UI until it finishes.
  useEffect(() => {
    if (readOnly) return;
    if (gapAnalysisSettled) return;
    const enrichmentComplete = chunksData?.enrichment_status === 'complete' || chunksData?.enrichment_status === 'error';
    if (!enrichmentComplete) return;

    let interval: ReturnType<typeof setInterval> | null = null;
    async function pollGapStatus() {
      try {
        const res = await fetch(`/api/tailorings/${tailoringId}`);
        if (!res.ok) {
          setGapAnalysisSettled(true); // don't block forever on error
          if (interval) clearInterval(interval);
          return;
        }
        const data = await res.json();
        setTailoring(data);
        if (data.gap_analysis_status === 'complete') {
          setGapAnalysisSettled(true);
          if (interval) clearInterval(interval);
        }
      } catch {
        setGapAnalysisSettled(true); // don't block forever on network error
        if (interval) clearInterval(interval);
      }
    }
    pollGapStatus();
    interval = setInterval(pollGapStatus, POLL_INTERVAL);
    return () => { if (interval) clearInterval(interval); };
    // Intentional: restart only when enrichment or gap settlement status changes.
  }, [tailoringId, chunksData?.enrichment_status, gapAnalysisSettled, readOnly]);

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
            setGapAnalysisSettled(false);
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

  const generationFailed = tailoring.generation_status === 'error';
  const enrichmentComplete = chunksData?.enrichment_status === 'complete';
  // Enrichment is settled once it's complete, errored, or the chunks API itself failed
  const enrichmentSettled = enrichmentComplete || chunksData?.enrichment_status === 'error' || !!chunksError;
  // Show the generation view (hiding tabs) while generation, enrichment, or gap analysis is running
  const showGenerationView = !generationFailed && (
    tailoring.generation_status === 'generating' ||
    (tailoring.generation_status === 'ready' && (!enrichmentSettled || !gapAnalysisSettled))
  );
  const effectiveChunksError = chunksError ?? (
    generationFailed && !enrichmentComplete
      ? (tailoring.generation_error ?? 'Generation failed — try regenerating this tailoring.')
      : null
  );

  const startedAt = tailoring.generation_started_at
    ? new Date(tailoring.generation_started_at).getTime()
    : null;
  const elapsed = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0;

  const createdDate = new Date(tailoring.created_at).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  });

  const shareUrl = tailoring.public_slug && tailoring.author_username_slug
    ? `${window.location.origin}/u/${tailoring.author_username_slug}/${tailoring.public_slug}`
    : null;

  const letterOn = tailoring.letter_public;
  const postingOn = tailoring.posting_public;
  const anyPublic = letterOn || postingOn;

  const canCopy = activeTab === 'letter' && !!tailoring.generated_output;

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

        {/* Center: segment tabs — hidden during generation/error */}
        <div className="flex items-center gap-1.5">
          {showGenerationView && (
            <span className="text-sm text-text-disabled animate-pulse tracking-[-0.1px] select-none">
              Generating…
            </span>
          )}
          {!showGenerationView && !generationFailed && (
            <>
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
            </>
          )}
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-1 justify-end">

          {/* Copy */}
          <button
            type="button"
            onClick={handleCopy}
            disabled={showGenerationView || !canCopy}
            title={copied ? 'Copied!' : 'Copy content'}
            className={cn(iconBtnCls, copied && 'text-success hover:text-success')}
          >
            {copied
              ? <CheckCircle2 className="h-4 w-4" />
              : <Copy className="h-4 w-4" />}
          </button>

          {/* Notion */}
          <Popover open={notionOpen} onOpenChange={readOnly ? undefined : setNotionOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                title={readOnly ? 'Sign in to export to Notion' : 'Export to Notion'}
                disabled={readOnly || showGenerationView || generationFailed}
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
            onClick={() => !readOnly && setShowRegenConfirm(true)}
            disabled={readOnly || regenerating || showGenerationView}
            title={readOnly ? 'Sign in to regenerate' : regenerating ? 'Regenerating…' : 'Regenerate'}
            className={iconBtnCls}
          >
            {regenerating
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <RotateCcw className="h-4 w-4" />}
          </button>

          <ToolDivider />

          {/* Share — Publish style */}
          <Popover open={shareOpen} onOpenChange={readOnly ? undefined : setShareOpen}>
            <PopoverTrigger asChild>
              <button type="button" disabled={readOnly || showGenerationView || generationFailed} className={textBtnCls}>
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
                    onCheckedChange={v => !readOnly && handleToggleShare('posting', v)}
                    disabled={readOnly || sharing}
                  />
                </div>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-text-primary">Advocacy Letter</p>
                    <p className="text-xs text-text-tertiary mt-0.5">Share the generated letter</p>
                  </div>
                  <Switch
                    checked={letterOn}
                    onCheckedChange={v => !readOnly && handleToggleShare('letter', v)}
                    disabled={readOnly || sharing}
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

      {/* ── Preview banner (letter / posting tabs only) ───────────────────── */}
      {!showGenerationView && !generationFailed && (activeTab === 'letter' || activeTab === 'posting') && (
        <div className="shrink-0 flex items-center gap-2 px-4 py-2 border-b border-border-subtle bg-surface-base text-xs text-text-tertiary">
          <Info className="h-3.5 w-3.5 shrink-0" />
          Preview — this is how your tailoring appears when shared. Gap requirements are hidden, partial matches appear green, and each matched item includes an advocacy statement and the experience source that supports it.
        </div>
      )}

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div ref={scrollRef} className={cn('flex-1 custom-scrollbar', activeTab === 'analysis' ? 'overflow-hidden' : 'overflow-y-scroll')}>

        {/* Generation in progress */}
        {showGenerationView && (
          <GenerationView
            tailoring={tailoring}
            regenSsePhase={regenSsePhase}
            enrichmentSettled={enrichmentSettled}
            gapAnalysisSettled={gapAnalysisSettled}
            elapsed={elapsed}
          />
        )}

        {/* Generation failed */}
        {generationFailed && (
          <TailoringErrorState
            message={tailoring.generation_error ?? 'Generation failed — try regenerating this tailoring.'}
            jobUrl={tailoring.job_url}
          />
        )}

        {/* Tabs — revealed once generation and enrichment are both complete */}
        {!showGenerationView && !generationFailed && (
          <>
            {activeTab === 'letter' && (
              <AdvocacyLetter
                tailoring={tailoring}
                authorName={userName}
              />
            )}
            {activeTab === 'posting' && (
              <JobPosting
                data={chunksData}
                error={effectiveChunksError}
                title={tailoring.title}
                company={tailoring.company}
                jobUrl={tailoring.job_url}
                authorName={userName}
                generationReady={tailoring.generation_status === 'ready'}
                publicMode={true}
              />
            )}
            {activeTab === 'analysis' && (
              <AnalysisView
                data={chunksData}
                error={effectiveChunksError}
                title={tailoring.title}
                company={tailoring.company}
                jobUrl={tailoring.job_url}
                authorName={userName}
                tailoringId={readOnly ? undefined : tailoring.id}
                gapAnalysis={tailoring.gap_analysis}
                gapResponses={gapResponses}
                generationReady={tailoring.generation_status === 'ready'}
                readOnly={readOnly}
              />
            )}
            {activeTab === 'debug' && (
              <DebugPanel
                tailoringId={tailoring.id}
                chunksData={chunksData}
                chunksError={effectiveChunksError}
                title={tailoring.title}
                company={tailoring.company}
                jobUrl={tailoring.job_url}
              />
            )}
          </>
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
