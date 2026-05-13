'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload, Pencil, FileText, Trash2, Loader2, AlertCircle, X, RefreshCw, GitBranch, ArrowUpRight, ChevronDown, ChevronUp,
} from 'lucide-react';
import { LuGithub } from 'react-icons/lu';
import { toast } from 'sonner';
import { cn, toastError, formatElapsed } from '@/lib/utils';
import { ChunkedProfile } from '@/components/dashboard/ChunkedProfile';
import type { ExperienceRecord, ExperienceChunksResponse, GitHubRepo, ProfileCorrections } from '@/types';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function formatRelativeDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minutes ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return '1 day ago';
  if (diffDays < 30) return `${diffDays} days ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

/* ─── Types ─────────────────────────────────────────────────────────────── */

type UploadPhase =
  | { phase: 'loading' }
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'processing'; filename: string; experienceId: string }
  | { phase: 'ready'; record: ExperienceRecord }
  | { phase: 'error'; message: string };

type GithubState = 'idle' | 'fetching' | 'saving' | 'saved' | 'removing' | 'error';

const CONFIRM_CONFIGS = {
  'resume-remove': {
    title: 'Remove resume',
    description: 'Your resume and extracted profile data will be permanently deleted. This cannot be undone.',
    confirm: 'Remove',
  },
  'resume-replace': {
    title: 'Replace resume',
    description: 'Your current resume and extracted profile data will be replaced. The previous data will be permanently deleted. This cannot be undone.',
    confirm: 'Replace',
  },
  'github-remove': {
    title: 'Remove GitHub',
    description: 'Your GitHub profile and imported repository data will be permanently deleted. This cannot be undone.',
    confirm: 'Remove',
  },
  'github-change': {
    title: 'Change GitHub profile',
    description: 'Your existing GitHub profile and imported repository data will be replaced with the new username. The previous data will be permanently deleted. This cannot be undone.',
    confirm: 'Change',
  },
  'github-repos-remove': {
    title: 'Remove repositories',
    description: 'Removing repositories will permanently delete the signals extracted from them. This cannot be undone.',
    confirm: 'Remove',
  },
} as const;

type ConfirmAction = keyof typeof CONFIRM_CONFIGS;

const PROCESS_STAGE_LABELS: Record<string, string> = {
  extracting: 'Extracting text',
  analyzing: 'Analyzing profile',
};
const PROCESS_STAGES = ['extracting', 'analyzing'] as const;

/* ─── Shared styles ─────────────────────────────────────────────────────── */

const inputCls =
  'w-full h-10 rounded-xl border border-border-default bg-surface-elevated px-3 text-sm text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
  'hover:border-border-strong hover:bg-surface-base ' +
  'focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)] disabled:opacity-50 disabled:cursor-not-allowed';

const saveBtnCls =
  'inline-flex items-center gap-1.5 justify-center h-9 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] ' +
  'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 ' +
  'hover:opacity-90 transition-opacity ' +
  'disabled:bg-surface-base dark:disabled:bg-surface-overlay disabled:text-text-disabled ' +
  'disabled:cursor-not-allowed disabled:hover:opacity-100';

const outlineBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] ' +
  'border border-border-default bg-surface-elevated text-text-secondary ' +
  'hover:bg-surface-base hover:border-border-strong hover:text-text-primary ' +
  'transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

/* ─── Live badge (Mintlify pill style) ───────────────────────────────────── */

function LiveBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center w-fit font-medium bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400 gap-[3px] text-xs leading-none rounded-full py-1 px-2">
      <span className="flex items-center justify-center size-3">
        <span className="size-1.5 bg-current rounded-full" />
      </span>
      {label}
    </span>
  );
}

/* ─── Mintlify-style button ──────────────────────────────────────────────── */

function MintBtn({
  icon,
  label,
  onClick,
  danger,
  disabled,
}: {
  icon: React.ReactNode;
  label?: string;
  onClick?: () => void;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-[10px] border transition-colors',
        'outline-none focus-visible:ring-2 [&_svg:not([class*="size-"])]:size-3.5',
        label
          ? 'gap-1.5 h-8 px-2.5 text-sm font-normal tracking-[-0.1px]'
          : 'size-8',
        danger
          ? 'text-text-secondary bg-surface-elevated border-border-subtle text-red-600 border-red-300 dark:border-red-800 hover:border-red-300 hover:bg-red-50 hover:text-error dark:hover:border-red-800 dark:hover:bg-red-950/20'
          : 'text-text-secondary bg-surface-elevated border-border-subtle hover:border-border-default hover:bg-surface-sunken hover:text-text-primary',
        disabled && 'opacity-40 cursor-not-allowed pointer-events-none',
      )}
    >
      {icon}
      {label}
    </button>
  );
}

/* ─── Toggle switch ──────────────────────────────────────────────────────── */

function Toggle({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={cn(
        'relative inline-flex h-4 w-7 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent',
        'transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2',
        checked ? 'bg-zinc-900 dark:bg-white' : 'bg-border-default',
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block h-3 w-3 rounded-full bg-white dark:bg-zinc-900',
          'shadow transform transition duration-200 ease-in-out',
          checked ? 'translate-x-3' : 'translate-x-0',
        )}
      />
    </button>
  );
}

/* ─── Component ─────────────────────────────────────────────────────────── */

export function ExperienceManager({
  readOnly,
  initialRecord,
  initialChunks,
}: {
  readOnly?: boolean;
  initialRecord?: ExperienceRecord;
  initialChunks?: ExperienceChunksResponse;
} = {}) {
  const [uploadState, setUploadState] = useState<UploadPhase>({ phase: 'loading' });
  const [githubUrl, setGithubUrl] = useState('');
  const [githubState, setGithubState] = useState<GithubState>('idle');
  const [githubError, setGithubError] = useState<string | null>(null);
  const [githubEditing, setGithubEditing] = useState(false);
  const [previewRepos, setPreviewRepos] = useState<GitHubRepo[] | null>(null);
  const [selectedRepoNames, setSelectedRepoNames] = useState<Set<string>>(new Set());
  const [acknowledged, setAcknowledged] = useState(false);

  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const [stageStartedAt, setStageStartedAt] = useState<Record<string, number>>({});
  const [, setTick] = useState(0);

  const [connectedGithub, setConnectedGithub] = useState<{ username: string; repos: GitHubRepo[] } | null>(null);

  const [chunksRefreshKey, setChunksRefreshKey] = useState(0);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmAction | null>(null);
  const [previouslyConnectedRepos, setPreviouslyConnectedRepos] = useState<Set<string>>(new Set());
  const [rescanConfirm, setRescanConfirm] = useState<string | null>(null);

  const [scanningRepos, setScanningRepos] = useState<Record<string, number>>({});
  const scanningReposRef = useRef<Record<string, number>>({});
  const scanPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [profileFields, setProfileFields] = useState({ yoe_override: '', headline: '', title: '', location: '', summary: '' });
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileExpanded, setProfileExpanded] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);


  useEffect(() => {
    if (uploadState.phase !== 'processing') return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [uploadState.phase]);

  const scanIsActive = Object.keys(scanningRepos).length > 0;
  useEffect(() => {
    if (!scanIsActive) return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [scanIsActive]);

  const syncProfileFromRecord = useCallback((record: ExperienceRecord) => {
    const corrections: ProfileCorrections = record.extracted_profile?.corrections ?? {};
    const resume = record.extracted_profile?.resume;
    setProfileFields({
      yoe_override: corrections.yoe_override != null ? String(corrections.yoe_override) : '',
      headline: corrections.headline ?? resume?.headline ?? '',
      title: corrections.title ?? resume?.title ?? '',
      location: corrections.location ?? resume?.location ?? '',
      summary: corrections.summary ?? resume?.summary ?? '',
    });
  }, []);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();
    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/experience');
        if (!res.ok) return;
        const record: ExperienceRecord | null = await res.json();
        if (!record) return;
        if (record.status === 'ready') {
          stopPolling();
          setUploadState({ phase: 'ready', record });
          setChunksRefreshKey((k) => k + 1);
        } else if (record.status === 'error') {
          stopPolling();
          setUploadState({ phase: 'error', message: record.error_message ?? 'Processing failed' });
        }
      } catch { /* ignore */ }
    }, 3000);
  }, [stopPolling]);

  const updateScanningRepos = useCallback((fn: (prev: Record<string, number>) => Record<string, number>) => {
    scanningReposRef.current = fn(scanningReposRef.current);
    setScanningRepos({ ...scanningReposRef.current });
  }, []);

  const stopScanPolling = useCallback(() => {
    if (scanPollRef.current) { clearInterval(scanPollRef.current); scanPollRef.current = null; }
  }, []);

  const startScanPolling = useCallback(() => {
    stopScanPolling();
    scanPollRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/experience');
        if (!res.ok) return;
        const record: ExperienceRecord | null = await res.json();
        if (!record?.github_repos) return;

        let anyCompleted = false;
        updateScanningRepos((prev) => {
          const next = { ...prev };
          for (const [name, startTs] of Object.entries(prev)) {
            const repo = record.github_repos!.find((r) => r.name === name);
            if (repo?.scanned_at && new Date(repo.scanned_at).getTime() >= startTs) {
              delete next[name];
              anyCompleted = true;
            }
          }
          return next;
        });

        if (anyCompleted) {
          setConnectedGithub({ username: record.github_username!, repos: record.github_repos ?? [] });
          setChunksRefreshKey((k) => k + 1);
          if (Object.keys(scanningReposRef.current).length === 0) stopScanPolling();
        }
      } catch { /* ignore */ }
    }, 3000);
  }, [stopScanPolling, updateScanningRepos]);

  useEffect(() => {
    async function loadInitialState() {
      // When initialRecord is provided (e.g. demo mode), skip the fetch.
      const record: ExperienceRecord | null = initialRecord ?? await (async () => {
        try {
          const res = await fetch('/api/experience');
          if (!res.ok) { setUploadState({ phase: 'idle' }); return null; }
          return await res.json() as ExperienceRecord | null;
        } catch {
          setUploadState({ phase: 'idle' });
          return null;
        }
      })();

      if (!record) {
        if (!initialRecord) setUploadState({ phase: 'idle' });
        return;
      }

      try {
        // Always restore GitHub state regardless of resume processing status
        if (record.github_username) {
          setGithubUrl(record.github_username);
          setConnectedGithub({ username: record.github_username, repos: record.github_repos ?? [] });

          // Restore in-flight scans from scanning_started_at
          const scanning: Record<string, number> = {};
          for (const repo of record.github_repos ?? []) {
            if (repo.scanning_started_at) {
              const startTs = new Date(repo.scanning_started_at).getTime();
              const doneTs = repo.scanned_at ? new Date(repo.scanned_at).getTime() : 0;
              if (doneTs < startTs) scanning[repo.name] = startTs;
            }
          }
          if (Object.keys(scanning).length > 0) {
            updateScanningRepos(() => scanning);
            startScanPolling();
          }
        }

        if (record.status === 'ready') {
          setUploadState({ phase: 'ready', record });
          syncProfileFromRecord(record);
        } else if (record.status === 'processing' || record.status === 'pending') {
          if (record.last_process_requested_at) {
            const startTs = new Date(record.last_process_requested_at).getTime();
            setStageStartedAt({ [PROCESS_STAGES[0]]: startTs });
            setProcessingStage(PROCESS_STAGES[0]);
          }
          setUploadState({ phase: 'processing', filename: record.filename ?? '', experienceId: record.id });
          startPolling();
        } else if (record.status === 'error') {
          setUploadState({ phase: 'error', message: record.error_message ?? 'Processing failed' });
        }
      } catch {
        setUploadState({ phase: 'idle' });
      }
    }

    loadInitialState();
    return () => { stopPolling(); stopScanPolling(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startPolling, stopPolling, stopScanPolling, startScanPolling, updateScanningRepos, syncProfileFromRecord]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    setUploadState({ phase: 'uploading', filename: file.name });

    try {
      const urlRes = await fetch('/api/experience/upload-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name }),
      });
      if (!urlRes.ok) {
        const err = await urlRes.json().catch(() => ({}));
        throw new Error(err.detail ?? `Failed to get upload URL (${urlRes.status})`);
      }
      const { upload_url, storage_key, experience_id } = await urlRes.json();

      const uploadRes = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream', 'x-ms-blob-type': 'BlockBlob' },
      });
      if (!uploadRes.ok) throw new Error(`Failed to upload file to storage (${uploadRes.status})`);

      setUploadState({ phase: 'processing', filename: file.name, experienceId: experience_id });
      setProcessingStage(null);
      setStageStartedAt({});

      const processRes = await fetch('/api/experience/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ storage_key, experience_id }),
      });
      if (!processRes.ok || !processRes.body) {
        const err = await processRes.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Failed to start processing');
      }

      const reader = processRes.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let currentEvent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (currentEvent === 'stage') {
              setProcessingStage(data);
              setStageStartedAt((prev) => ({ ...prev, [data]: Date.now() }));
            } else if (currentEvent === 'ready') {
              const record = JSON.parse(data) as ExperienceRecord;
              setUploadState({ phase: 'ready', record });
              syncProfileFromRecord(record);
              setProcessingStage(null);
              setChunksRefreshKey((k) => k + 1);
              if (record.github_username) {
                setGithubUrl(record.github_username);
                setConnectedGithub({ username: record.github_username, repos: record.github_repos ?? [] });
              }
            } else if (currentEvent === 'error') {
              const { message } = JSON.parse(data);
              setUploadState({ phase: 'error', message });
              setProcessingStage(null);
            }
            currentEvent = '';
          }
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setUploadState({ phase: 'error', message });
      setProcessingStage(null);
    }
  };

  const handleRemove = async () => {
    stopPolling();
    const res = await fetch('/api/experience', { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? `Failed to remove (${res.status})`);
      return;
    }
    setUploadState({ phase: 'idle' });
    setProcessingStage(null);
    setStageStartedAt({});
    setChunksRefreshKey((k) => k + 1);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleConfirmAction = async () => {
    const action = confirmDialog;
    setConfirmDialog(null);
    if (action === 'resume-remove') await handleRemove();
    else if (action === 'resume-replace') fileInputRef.current?.click();
    else if (action === 'github-remove') await handleGithubRemove();
    else if (action === 'github-change') await doGithubSave(parseGithubUsername(githubUrl), [...selectedRepoNames]);
    else if (action === 'github-repos-remove') {
      const added = [...selectedRepoNames].filter((n) => !previouslyConnectedRepos.has(n));
      await doGithubSave(parseGithubUsername(githubUrl), [...selectedRepoNames], added);
    }
  };

  function parseGithubUsername(input: string): string {
    const match = input.match(/github\.com\/([^/]+)/);
    return match ? match[1] : input.trim();
  }

  const resetGithubPreview = () => {
    setPreviewRepos(null);
    setSelectedRepoNames(new Set());
    setAcknowledged(false);
  };

  const doGithubSave = async (username: string, repoNames: string[], enrichOnly?: string[]) => {
    setGithubState('saving');
    setGithubError(null);
    const payload: Record<string, unknown> = { github_username: username, selected_repo_names: repoNames };
    if (enrichOnly !== undefined) payload.enrich_only_repo_names = enrichOnly;
    const res = await fetch('/api/experience/github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      setGithubError(err.detail ?? 'Could not connect GitHub. Please try again.');
      setGithubState('error');
      return;
    }
    setGithubState('saved');
    setGithubEditing(false);
    resetGithubPreview();
    toast.success('GitHub profile connected');
    const updated: ExperienceRecord | null = await fetch('/api/experience').then((r) => r.json());
    if (updated) {
      setUploadState({ phase: 'ready', record: updated });
      setChunksRefreshKey((k) => k + 1);
      if (updated.github_username) {
        setConnectedGithub({ username: updated.github_username, repos: updated.github_repos ?? [] });
      }
      const toScan = enrichOnly ?? repoNames;
      const now = Date.now();
      const scanning: Record<string, number> = {};
      for (const name of toScan) {
        const repo = updated.github_repos?.find((r) => r.name === name);
        if (!repo?.scanned_at || new Date(repo.scanned_at).getTime() < now) {
          scanning[name] = now;
        }
      }
      if (Object.keys(scanning).length > 0) {
        updateScanningRepos((prev) => ({ ...prev, ...scanning }));
        startScanPolling();
      }
    }
  };

  const fetchReposForUsername = async (username: string, preselect?: Set<string>) => {
    setGithubState('fetching');
    setGithubError(null);
    const res = await fetch(`/api/experience/github/${encodeURIComponent(username)}/repos`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      setGithubError(err.detail ?? 'Could not fetch repos. Check the username and try again.');
      setGithubState('error');
      return;
    }
    const data = await res.json();
    const repos: GitHubRepo[] = data.repos ?? [];
    setPreviewRepos(repos);
    // Default OFF for initial connect; pre-select for Modify
    setSelectedRepoNames(preselect ? new Set(preselect) : new Set());
    setGithubState('idle');
  };

  const handleGithubFetch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const username = parseGithubUsername(githubUrl);
    if (!username) return;
    setPreviewRepos(null);
    setAcknowledged(false);
    await fetchReposForUsername(username);
  };

  const handleGithubModify = async () => {
    if (!connectedGithub) return;
    const username = connectedGithub.username;
    const currentRepos = new Set(connectedGithub.repos.map((r) => r.name));
    setPreviouslyConnectedRepos(currentRepos);
    setGithubUrl(username);
    setGithubEditing(true);
    setGithubError(null);
    setPreviewRepos(null);
    setAcknowledged(true); // pre-acknowledge for Modify since user already agreed once
    await fetchReposForUsername(username, currentRepos);
  };

  const handleGithubConnect = async () => {
    const username = parseGithubUsername(githubUrl);
    if (!username || selectedRepoNames.size === 0 || !acknowledged) return;

    if (githubEditing) {
      const added = [...selectedRepoNames].filter((n) => !previouslyConnectedRepos.has(n));
      const removed = [...previouslyConnectedRepos].filter((n) => !selectedRepoNames.has(n));
      if (removed.length > 0) {
        setConfirmDialog('github-repos-remove');
        return;
      }
      // Additions only — enrich only the new repos
      await doGithubSave(username, [...selectedRepoNames], added.length > 0 ? added : undefined);
      return;
    }

    await doGithubSave(username, [...selectedRepoNames]);
  };

  const toggleRepo = (name: string) => {
    setSelectedRepoNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handleRepoRescan = async (repoName: string) => {
    if (uploadState.phase !== 'ready') return;
    const username = uploadState.record.github_username;
    if (!username) return;
    const res = await fetch('/api/experience/github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ github_username: username, rescan_repo_names: [repoName] }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? 'Rescan failed');
      return;
    }
    toast.success(`Re-scan queued for ${repoName}`);
    const now = Date.now();
    updateScanningRepos((prev) => ({ ...prev, [repoName]: now }));
    startScanPolling();
  };

  const handleGithubRemove = async () => {
    setGithubState('removing');
    const res = await fetch('/api/experience/github', { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? `Failed to remove (${res.status})`);
      setGithubState('idle');
      return;
    }
    setGithubUrl('');
    setGithubState('idle');
    setGithubEditing(false);
    setConnectedGithub(null);
    resetGithubPreview();
    toast.success('GitHub profile removed');
    const updated = await fetch('/api/experience').then((r) => r.json());
    if (updated) {
      setUploadState({ phase: 'ready', record: updated });
      setChunksRefreshKey((k) => k + 1);
    }
  };

  /* ─── Profile signals ────────────────────────────────────────────────────── */

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      const yoe = parseFloat(profileFields.yoe_override);
      if (profileFields.yoe_override !== '' && !isNaN(yoe)) payload.yoe_override = yoe;
      if (profileFields.headline) payload.headline = profileFields.headline;
      if (profileFields.title) payload.title = profileFields.title;
      if (profileFields.location) payload.location = profileFields.location;
      if (profileFields.summary) payload.summary = profileFields.summary;

      const res = await fetch('/api/experience', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toastError(err.detail ?? 'Failed to save profile signals');
        return;
      }
      const updated = await res.json() as ExperienceRecord;
      setUploadState({ phase: 'ready', record: updated });
      // Don't re-sync fields — user just saved them, keep display stable
      toast.success('Profile signals saved');
    } catch {
      toastError('Failed to save profile signals');
    } finally {
      setProfileSaving(false);
    }
  };

  /* ─── Resume section: per-section helpers ───────────────────────────────── */

  const resumeHasFile =
    uploadState.phase === 'ready' && !!uploadState.record.filename;

  const resumeSubtext = (() => {
    switch (uploadState.phase) {
      case 'loading':
      case 'error': return null;
      case 'uploading':
      case 'processing':
      case 'idle': return 'Upload a PDF, DOCX, or TXT file to get started';
      case 'ready':
        if (!uploadState.record.filename) return 'Upload a PDF, DOCX, or TXT file to get started';
        return `Last updated ${formatRelativeDate(uploadState.record.processed_at) ?? ''}`;
    }
  })();

  const resumeCard = (() => {
    switch (uploadState.phase) {
      case 'loading':
      case 'idle': return null;
      case 'uploading':
        return (
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
            <Loader2 className="h-4 w-4 text-text-tertiary animate-spin flex-shrink-0" />
            <div>
              <p className="text-sm text-text-secondary truncate">{uploadState.filename}</p>
              <p className="text-xs text-text-disabled">Uploading…</p>
            </div>
          </div>
        );
      case 'processing': {
        const overallStart = stageStartedAt[PROCESS_STAGES[0]];
        const elapsed = overallStart ? Math.floor((Date.now() - overallStart) / 1000) : 0;
        const label = processingStage ? (PROCESS_STAGE_LABELS[processingStage] ?? processingStage) : 'Processing';
        return (
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
            <Loader2 className="h-4 w-4 text-text-tertiary animate-spin flex-shrink-0" />
            <div>
              <p className="text-sm text-text-secondary truncate">{uploadState.filename}</p>
              <p className="text-xs text-text-disabled">
                {label}…{overallStart ? ` ${formatElapsed(elapsed)}` : ''}
              </p>
            </div>
          </div>
        );
      }
      case 'ready':
        if (!uploadState.record.filename) return null;
        return (
          <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
            <FileText className="h-4 w-4 text-text-tertiary flex-shrink-0" />
            <div>
              <p className="text-sm text-text-secondary truncate">{uploadState.record.filename}</p>
              <p className="text-xs text-text-disabled">Processed</p>
            </div>
          </div>
        );
      case 'error':
        return (
          <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-red-50/60 dark:bg-red-950/10 border border-error/20 w-fit min-w-xs">
            <AlertCircle className="h-4 w-4 text-error flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-sm text-error">Processing failed</p>
              <p className="text-xs text-text-tertiary truncate">{uploadState.message}</p>
            </div>
          </div>
        );
    }
  })();

  const resumeControls = (() => {
    const uploadBtn = (
      <button
        type="button"
        onClick={() => !readOnly && fileInputRef.current?.click()}
        disabled={readOnly}
        className={cn(
          'flex items-center gap-3 px-3 py-3 rounded-xl border border-dashed border-border-default text-left w-fit min-w-xs transition-colors',
          readOnly ? 'opacity-50 cursor-not-allowed' : 'hover:border-border-strong hover:bg-surface-sunken',
        )}
      >
        <Upload className="h-4 w-4 text-text-tertiary flex-shrink-0" />
        <div>
          <p className="text-sm text-text-secondary">Click to upload</p>
          <p className="text-xs text-text-disabled">PDF, DOCX, or TXT</p>
        </div>
      </button>
    );
    switch (uploadState.phase) {
      case 'loading':
      case 'uploading': return null;
      case 'idle': return uploadBtn;
      case 'processing':
        return (
          <div className="flex flex-wrap items-center gap-2">
            <MintBtn icon={<X />} label="Cancel" onClick={handleRemove} danger disabled={readOnly} />
          </div>
        );
      case 'ready':
        if (!uploadState.record.filename) return uploadBtn;
        return (
          <div className="flex flex-wrap items-center gap-2">
            <MintBtn icon={<RefreshCw />} label="Replace" onClick={() => setConfirmDialog('resume-replace')} disabled={readOnly} />
            <MintBtn icon={<Trash2 />} label="Delete" onClick={() => setConfirmDialog('resume-remove')} danger disabled={readOnly} />
          </div>
        );
      case 'error':
        return (
          <div className="flex flex-wrap items-center gap-2">
            <MintBtn icon={<Upload />} label="Try again" onClick={() => fileInputRef.current?.click()} disabled={readOnly} />
            <MintBtn icon={<X />} label="Clear" onClick={handleRemove} danger disabled={readOnly} />
          </div>
        );
    }
  })();

  /* ─── GitHub card content ────────────────────────────────────────────────── */

  const githubConnected = !!connectedGithub;
  const isInitialLoad = uploadState.phase === 'loading';

  const renderGithubControls = () => {
    // ── Connected ────────────────────────────────────────────────────────────
    if (githubConnected && !githubEditing && connectedGithub) {
      const repos = connectedGithub.repos;
      const username = connectedGithub.username;
      return (
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <a
              href={`https://github.com/${username}`}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-2 w-fit"
            >
              <LuGithub className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
              <span className="text-sm font-medium text-text-primary group-hover:opacity-80">{username}</span>
              <ArrowUpRight className="size-3 text-text-tertiary" />
            </a>
            <div className="flex flex-col gap-2 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
              <span className="text-sm text-text-tertiary">
                {repos.length} repo{repos.length !== 1 ? 's' : ''} linked
              </span>
              {repos.map((r) => {
                const scanStart = scanningRepos[r.name];
                const isScanning = !!scanStart;
                const elapsed = scanStart ? Math.floor((Date.now() - scanStart) / 1000) : 0;
                return (
                  <div key={r.name} className="group flex items-center gap-2">
                    <GitBranch className="size-3.5 text-text-tertiary flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <a
                        href={`https://github.com/${username}/${r.name}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-text-primary hover:opacity-80"
                      >
                        {r.name}
                      </a>
                      {isScanning ? (
                        <span className="inline-flex items-center gap-1 text-xs text-text-disabled ml-1.5">
                          <Loader2 className="h-2.5 w-2.5 animate-spin" />
                          Scanning… {formatElapsed(elapsed)}
                        </span>
                      ) : r.scanned_at ? (
                        <span className="text-xs text-text-disabled ml-1.5">
                          · scanned {formatRelativeDate(r.scanned_at)}
                        </span>
                      ) : null}
                    </div>
                    {!isScanning && !readOnly && (
                      <button
                        type="button"
                        title="Re-scan this repository"
                        onClick={() => setRescanConfirm(r.name)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-lg hover:bg-surface-sunken text-text-tertiary hover:text-text-secondary"
                      >
                        <RefreshCw className="size-3" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <MintBtn
              icon={<Pencil />}
              label="Modify"
              onClick={handleGithubModify}
              disabled={readOnly}
            />
            <MintBtn
              icon={githubState === 'removing' ? <Loader2 className="animate-spin" /> : <X />}
              label="Disconnect"
              onClick={() => setConfirmDialog('github-remove')}
              danger
              disabled={readOnly || githubState === 'removing'}
            />
          </div>
        </div>
      );
    }

    // ── Step 2: repo selection ───────────────────────────────────────────────
    if (previewRepos !== null || githubState === 'fetching') {
      const previewUsername = parseGithubUsername(githubUrl);
      return (
        <div className="flex flex-col gap-3">
          <a
            href={`https://github.com/${encodeURIComponent(previewUsername)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-2 w-fit"
          >
            <LuGithub className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
            <span className="text-sm font-medium text-text-primary group-hover:opacity-80">{previewUsername}</span>
            <ArrowUpRight className="size-3 text-text-tertiary" />
          </a>

          <div className="flex flex-col gap-0 px-3 py-3 rounded-xl bg-surface-elevated border w-fit min-w-xs">
            {githubState === 'fetching' ? (
              <div className="flex items-center gap-2 py-3 justify-center text-xs text-text-tertiary">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />Fetching repos…
              </div>
            ) : previewRepos!.length === 0 ? (
              <p className="text-xs text-text-disabled py-2">No public repos found</p>
            ) : (
              <>
                <span className="text-sm text-text-tertiary mb-2">
                  {previewRepos!.length} repo{previewRepos!.length !== 1 ? 's' : ''} found
                </span>
                {previewRepos!.map((r) => (
                  <div key={r.name} className="flex items-center gap-3 py-1.5">
                    <Toggle checked={selectedRepoNames.has(r.name)} onChange={() => toggleRepo(r.name)} />
                    <GitBranch className="size-3.5 text-text-tertiary flex-shrink-0" />
                    <div className="flex items-center gap-1 flex-1 min-w-0">
                      <a
                        href={`https://github.com/${encodeURIComponent(previewUsername)}/${encodeURIComponent(r.name)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-text-primary hover:opacity-80 truncate"
                      >
                        {r.name}
                      </a>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
          {githubState === 'error' && githubError && (
            <p className="text-xs text-error">{githubError}</p>
          )}
          {previewRepos !== null && previewRepos.length > 0 && (
            <label className="flex gap-2.5 cursor-pointer">
              <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} className="h-3.5 w-3.5 my-1 flex-shrink-0 accent-brand-primary cursor-pointer" />
              <span className="text-xs text-text-secondary leading-relaxed">
                I confirm the selected repositories are representative of my engineering work. For repos with multiple contributors, Tailord treats the codebase as indicative of my experience.
              </span>
            </label>
          )}
          {(() => {
            const hasNoChange = githubEditing &&
              selectedRepoNames.size === previouslyConnectedRepos.size &&
              [...selectedRepoNames].every((n) => previouslyConnectedRepos.has(n));
            const connectDisabled = selectedRepoNames.size === 0 || !acknowledged || githubState === 'saving' || githubState === 'fetching' || hasNoChange;
            return (
              <div className="flex items-center gap-2">
                <button type="button" onClick={handleGithubConnect} disabled={readOnly || connectDisabled} className={saveBtnCls}>
                  {githubState === 'saving' ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Connecting…</> : `Connect (${selectedRepoNames.size} repo${selectedRepoNames.size !== 1 ? 's' : ''})`}
                </button>
                <button type="button" onClick={() => { resetGithubPreview(); setGithubState('idle'); setGithubError(null); if (githubEditing) setGithubEditing(false); }} className={outlineBtnCls}>
                  Cancel
                </button>
              </div>
            );
          })()}
        </div>
      );
    }

    // ── Step 1: username input ───────────────────────────────────────────────
    return (
      <form onSubmit={readOnly ? (e) => e.preventDefault() : handleGithubFetch} className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-xs">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LuGithub className="h-4 w-4 text-text-tertiary" />
            </div>
            <input type="text" value={githubUrl} onChange={(e) => { setGithubUrl(e.target.value); setGithubState('idle'); setGithubError(null); }} placeholder="github.com/username or username" disabled={readOnly} className={cn(inputCls, 'pl-9')} />
          </div>
          <button type="submit" disabled={readOnly || !githubUrl.trim()} className={saveBtnCls}>
            Connect
          </button>
        </div>
        {githubState === 'error' && githubError && <p className="text-xs text-error">{githubError}</p>}
        {githubEditing && (
          <button type="button" onClick={() => { setGithubEditing(false); setGithubState('idle'); setGithubError(null); resetGithubPreview(); }} className={cn(outlineBtnCls, 'w-fit')}>Cancel</button>
        )}
      </form>
    );
  };

  /* ─── Render ─────────────────────────────────────────────────────────────── */

  return (
    <div className="h-full flex flex-col bg-surface-elevated">

      {/* Hidden file input */}
      <input ref={fileInputRef} type="file" accept=".pdf,.doc,.docx,.txt" className="hidden" onChange={handleFileChange} />

      {/* Topbar */}
      <div className="shrink-0 flex items-center h-12 px-6 bg-surface-elevated">
        <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">My Experience</span>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="mx-auto px-6 lg:px-16 pt-8 pb-24 max-w-6xl">

          {/* Greeting */}
          <div className="flex flex-col gap-1 pb-4">
            <h2 suppressHydrationWarning className="text-lg font-medium text-text-primary tracking-[-0.2px]">

              Build your profile
            </h2>

            <p className="text-sm text-text-secondary">Add your experience here and review it below</p>
          </div>

          {/* Source sections — two-column grid */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-12 pb-6 border-b border-zinc-950/5 dark:border-white/5">
            {/* Resume */}
            <div className="flex flex-col gap-5">
              {/* 1. Header */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2 h-6">
                  <h2 className="text-sm font-medium text-text-primary">Resume Upload</h2>
                  <span className={resumeHasFile ? 'flex items-center' : 'invisible'}>
                    <LiveBadge label="Uploaded" />
                  </span>
                </div>
                {/* 2. Subtext */}
                {resumeSubtext && (
                  <p className="text-sm text-text-tertiary">{resumeSubtext}</p>
                )}
              </div>
              {/* 3. Card */}
              {resumeCard}
              {/* 4. Controls */}
              {resumeControls}
            </div>

            {/* GitHub */}
            <div className="flex flex-col gap-5">
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2 h-6">
                  <h2 className="text-sm font-medium text-text-primary">GitHub Connection</h2>
                  <span className={githubConnected ? 'flex items-center' : 'invisible'}>
                    <LiveBadge label="Connected" />
                  </span>
                </div>
                {!isInitialLoad && (
                  <p className="text-sm text-text-tertiary">
                    {githubConnected
                      ? 'Signals are derived from your connected repositories'
                      : 'Import your public repositories to enrich your experience'}
                  </p>
                )}
              </div>
              {!isInitialLoad && renderGithubControls()}
            </div>
          </div>

          {/* Inferred Profile Signals */}
          {uploadState.phase === 'ready' && (
            <div className="mt-8 pb-8 border-b border-zinc-950/5 dark:border-white/5">
              <button
                type="button"
                onClick={() => setProfileExpanded((v) => !v)}
                className="flex w-full items-start justify-between gap-3 text-left"
              >
                <div className="flex flex-col gap-1">
                  <h2 className="text-sm font-medium text-text-primary">Inferred Profile</h2>
                  <p className="text-sm text-text-tertiary">
                    {profileExpanded
                      ? 'These signals are used in generation — edit to correct any inaccuracies.'
                      : 'Expand to review inferred signals — years of experience, title, location, and more.'}
                  </p>
                </div>
                <span className="mt-0.5 shrink-0 text-text-tertiary">
                  {profileExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </span>
              </button>
              {profileExpanded && (
                <>
                  <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-medium text-text-secondary">Years of experience</label>
                      <input
                        type="number"
                        min="0"
                        step="0.5"
                        value={profileFields.yoe_override}
                        onChange={(e) => setProfileFields((p) => ({ ...p, yoe_override: e.target.value }))}
                        placeholder="Auto-computed from resume"
                        disabled={readOnly}
                        className={inputCls}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-medium text-text-secondary">Headline</label>
                      <input
                        type="text"
                        value={profileFields.headline}
                        onChange={(e) => setProfileFields((p) => ({ ...p, headline: e.target.value }))}
                        placeholder="e.g. Senior Software Engineer"
                        disabled={readOnly}
                        className={inputCls}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-medium text-text-secondary">Title</label>
                      <input
                        type="text"
                        value={profileFields.title}
                        onChange={(e) => setProfileFields((p) => ({ ...p, title: e.target.value }))}
                        placeholder="e.g. Software Engineer"
                        disabled={readOnly}
                        className={inputCls}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-medium text-text-secondary">Location</label>
                      <input
                        type="text"
                        value={profileFields.location}
                        onChange={(e) => setProfileFields((p) => ({ ...p, location: e.target.value }))}
                        placeholder="e.g. San Francisco, CA"
                        disabled={readOnly}
                        className={inputCls}
                      />
                    </div>
                    <div className="flex flex-col gap-1.5 md:col-span-2">
                      <label className="text-xs font-medium text-text-secondary">Summary</label>
                      <textarea
                        value={profileFields.summary}
                        onChange={(e) => setProfileFields((p) => ({ ...p, summary: e.target.value }))}
                        placeholder="Professional summary"
                        disabled={readOnly}
                        rows={3}
                        className={cn(inputCls, 'h-auto py-2 resize-none')}
                      />
                    </div>
                  </div>
                  {!readOnly && (
                    <div className="mt-4">
                      <button
                        type="button"
                        onClick={handleProfileSave}
                        disabled={profileSaving}
                        className={saveBtnCls}
                      >
                        {profileSaving ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving…</> : 'Save signals'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Parsed experience */}
          <div className="mt-8">
            <ChunkedProfile refreshKey={chunksRefreshKey} initialData={initialChunks} readOnly={readOnly} />
          </div>

        </div>
      </div>

      {/* Rescan confirm dialog */}
      <Dialog open={rescanConfirm !== null} onOpenChange={(o) => !o && setRescanConfirm(null)}>
        <DialogContent className="max-w-sm bg-surface-elevated border-border-subtle rounded-2xl">
          <DialogHeader>
            <DialogTitle className="text-sm font-medium text-text-primary">Re-scan repository</DialogTitle>
            <DialogDescription className="text-sm text-text-secondary">
              Re-fetch and re-analyze <strong className="text-text-primary">{rescanConfirm}</strong>? The signals will be updated in the background.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-row justify-end gap-2 sm:gap-2">
            <button type="button" onClick={() => setRescanConfirm(null)} className={outlineBtnCls}>Cancel</button>
            <button
              type="button"
              onClick={() => { handleRepoRescan(rescanConfirm!); setRescanConfirm(null); }}
              className={saveBtnCls}
            >
              Re-scan
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm dialog */}
      <Dialog open={confirmDialog !== null} onOpenChange={(o) => !o && setConfirmDialog(null)}>
        <DialogContent className="max-w-sm bg-surface-elevated border-border-subtle rounded-2xl">
          <DialogHeader>
            <DialogTitle className="text-sm font-medium text-text-primary">
              {confirmDialog && CONFIRM_CONFIGS[confirmDialog].title}
            </DialogTitle>
            <DialogDescription className="text-sm text-text-secondary">
              {confirmDialog && CONFIRM_CONFIGS[confirmDialog].description}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-row justify-end gap-2 sm:gap-2">
            <button
              type="button"
              onClick={() => setConfirmDialog(null)}
              className={outlineBtnCls}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirmAction}
              className="inline-flex items-center justify-center h-9 px-3 rounded-[10px] text-sm font-normal bg-red-600 text-white hover:bg-red-700 transition-colors"
            >
              {confirmDialog && CONFIRM_CONFIGS[confirmDialog].confirm}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
