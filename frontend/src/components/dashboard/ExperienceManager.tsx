'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload, FileText, Loader2, CheckCircle, AlertCircle, Pencil, X,
} from 'lucide-react';
import { LuGithub } from 'react-icons/lu';
import { toast } from 'sonner';
import { cn, toastError, formatElapsed } from '@/lib/utils';
import { ParsedProfile } from '@/components/dashboard/ParsedProfile';
import { EditableResumeProfile } from '@/components/dashboard/EditableResumeProfile';
import type { ExperienceRecord, ExtractedProfile, GitHubRepo } from '@/types';
import { IconCheck } from '@/components/ui/icons';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';

/* ─── Types ─────────────────────────────────────────────────────────────── */

type UploadPhase =
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'processing'; filename: string; experienceId: string }
  | { phase: 'ready'; record: ExperienceRecord }
  | { phase: 'error'; message: string };

type GithubState = 'idle' | 'fetching' | 'saving' | 'saved' | 'removing' | 'error';
type SaveState = 'idle' | 'saving' | 'saved';

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
} as const;

type ConfirmAction = keyof typeof CONFIRM_CONFIGS;

const PROCESS_STAGE_LABELS: Record<string, string> = {
  extracting: 'Extracting text',
  analyzing: 'Analyzing profile',
};
const PROCESS_STAGES = ['extracting', 'analyzing'] as const;

/* ─── Shared styles (mirrors SettingsPanel) ─────────────────────────────── */

const inputCls =
  'w-full h-10 rounded-xl border border-border-default bg-surface-elevated px-3 text-sm text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
  'hover:border-border-strong hover:bg-surface-base ' +
  'focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)] disabled:opacity-50 disabled:cursor-not-allowed';

const textareaCls =
  'w-full rounded-xl border border-border-default bg-surface-elevated px-3 py-2.5 text-sm text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 resize-none ' +
  'hover:border-border-strong hover:bg-surface-base ' +
  'focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)]';

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

/* ─── Section row layout (matches SettingsPanel) ─────────────────────────── */

function SettingRow({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="py-8 grid grid-cols-1 lg:grid-cols-8 gap-x-12 gap-y-4">
      <div className="lg:col-span-3 flex flex-col gap-1">
        <h2 className="text-sm font-medium text-text-primary">{title}</h2>
        {description && <p className="text-sm text-text-secondary">{description}</p>}
      </div>
      <div className="lg:col-span-5">{children}</div>
    </div>
  );
}

/* ─── Card box ──────────────────────────────────────────────────────────── */

function CardBox({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-3 rounded-2xl bg-surface-base p-4 text-sm', className)}>
      {children}
    </div>
  );
}

/* ─── Icon box ──────────────────────────────────────────────────────────── */

function IconBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="shrink-0 rounded-xl p-2 bg-surface-elevated border border-border-subtle shadow-[0px_1px_2px_0px_rgba(20,21,26,0.05)]">
      {children}
    </div>
  );
}

/* ─── Connected badge ───────────────────────────────────────────────────── */

function StatusBadge({ label, variant }: { label: string; variant: 'green' | 'amber' }) {
  return (
    <span className={cn(
      'inline-flex items-center gap-[3px] py-0.5 px-1.5 text-xs font-medium rounded-md',
      variant === 'green'
        ? 'bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400'
        : 'bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400'
    )}>
      {variant === 'green' ? (
        <IconCheck size={11} />
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 18 18" fill="currentColor" stroke="none" aria-hidden="true">
          <circle cx="9" cy="9" r="3.5" />
        </svg>
      )}
      {label}
    </span>
  );
}

/* ─── Source row (ready state) ──────────────────────────────────────────── */

function SourceRow({
  icon,
  name,
  badge,
  description,
  action,
}: {
  icon: React.ReactNode;
  name: string;
  badge?: React.ReactNode;
  description?: React.ReactNode;
  action: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3">
      <IconBox>{icon}</IconBox>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary flex items-center gap-2 flex-wrap">
          {name}{badge}
        </p>
        {description && (
          <div className="text-sm text-text-secondary mt-0.5">{description}</div>
        )}
      </div>
      <div className="shrink-0 flex items-center gap-2">{action}</div>
    </div>
  );
}

/* ─── Component ─────────────────────────────────────────────────────────── */

export function ExperienceManager() {
  const [uploadState, setUploadState] = useState<UploadPhase>({ phase: 'idle' });
  const [githubUrl, setGithubUrl] = useState('');
  const [githubState, setGithubState] = useState<GithubState>('idle');
  const [githubError, setGithubError] = useState<string | null>(null);
  const [githubEditing, setGithubEditing] = useState(false);
  const [previewRepos, setPreviewRepos] = useState<GitHubRepo[] | null>(null);
  const [selectedRepoNames, setSelectedRepoNames] = useState<Set<string>>(new Set());
  const [directText, setDirectText] = useState('');
  const [directState, setDirectState] = useState<SaveState>('idle');

  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const [stageStartedAt, setStageStartedAt] = useState<Record<string, number>>({});
  const [, setTick] = useState(0);

  const [editingProfile, setEditingProfile] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmAction | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (uploadState.phase !== 'processing') return;
    const interval = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(interval);
  }, [uploadState.phase]);

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
        } else if (record.status === 'error') {
          stopPolling();
          setUploadState({ phase: 'error', message: record.error_message ?? 'Processing failed' });
        }
      } catch { /* ignore */ }
    }, 3000);
  }, [stopPolling]);

  useEffect(() => {
    async function loadInitialState() {
      try {
        const res = await fetch('/api/experience');
        if (!res.ok) return;
        const record: ExperienceRecord | null = await res.json();
        if (!record) return;

        if (record.status === 'ready') {
          setUploadState({ phase: 'ready', record });
          if (record.github_username) setGithubUrl(record.github_username);
          if (record.user_input_text) setDirectText(record.user_input_text);
        } else if (record.status === 'processing' || record.status === 'pending') {
          setUploadState({ phase: 'processing', filename: record.filename ?? '', experienceId: record.id });
          startPolling();
        } else if (record.status === 'error') {
          setUploadState({ phase: 'error', message: record.error_message ?? 'Processing failed' });
        }
      } catch { /* ignore */ }
    }

    loadInitialState();
    return () => stopPolling();
  }, [startPolling, stopPolling]);

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
              setProcessingStage(null);
              if (record.github_username) setGithubUrl(record.github_username);
              if (record.user_input_text) setDirectText(record.user_input_text);
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
    setEditingProfile(false);
    setProfileSaved(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleConfirmAction = async () => {
    const action = confirmDialog;
    setConfirmDialog(null);
    if (action === 'resume-remove') await handleRemove();
    else if (action === 'resume-replace') fileInputRef.current?.click();
    else if (action === 'github-remove') await handleGithubRemove();
    else if (action === 'github-change') await doGithubSave(parseGithubUsername(githubUrl), [...selectedRepoNames]);
  };

  function parseGithubUsername(input: string): string {
    const match = input.match(/github\.com\/([^/]+)/);
    return match ? match[1] : input.trim();
  }

  const resetGithubPreview = () => {
    setPreviewRepos(null);
    setSelectedRepoNames(new Set());
  };

  const doGithubSave = async (username: string, repoNames: string[]) => {
    setGithubState('saving');
    setGithubError(null);
    const res = await fetch('/api/experience/github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ github_username: username, selected_repo_names: repoNames }),
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
    const updated = await fetch('/api/experience').then((r) => r.json());
    if (updated) setUploadState({ phase: 'ready', record: updated });
  };

  const handleGithubFetch = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const username = parseGithubUsername(githubUrl);
    if (!username) return;
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
    setSelectedRepoNames(new Set(repos.map((r) => r.name)));
    setGithubState('idle');
  };

  const handleGithubConnect = async () => {
    const username = parseGithubUsername(githubUrl);
    if (!username || selectedRepoNames.size === 0) return;
    if (githubEditing) {
      setConfirmDialog('github-change');
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
    resetGithubPreview();
    toast.success('GitHub profile removed');
    const updated = await fetch('/api/experience').then((r) => r.json());
    if (updated) setUploadState({ phase: 'ready', record: updated });
  };

  const handleDirectSave = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!directText.trim()) return;
    setDirectState('saving');
    const res = await fetch('/api/experience/user-input', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: directText }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? `Failed to save (${res.status})`);
      setDirectState('idle');
      return;
    }
    setDirectState('saved');
    toast.success('Additional context saved');
    const updated = await fetch('/api/experience').then((r) => r.json());
    if (updated) setUploadState({ phase: 'ready', record: updated });
  };

  const handleSaveProfile = async (profile: ExtractedProfile) => {
    const res = await fetch('/api/experience', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? 'Failed to save profile');
      throw new Error('save failed');
    }
    const updated: ExperienceRecord = await res.json();
    setUploadState({ phase: 'ready', record: updated });
    setEditingProfile(false);
    setProfileSaved(true);
    toast.success('Profile updated');
  };

  /* ─── Resume right-col content ─────────────────────────────────────────── */

  const renderResumeContent = () => {
    switch (uploadState.phase) {
      case 'idle':
        return (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full py-10 rounded-2xl border-2 border-dashed border-border-default bg-surface-base hover:border-border-strong hover:bg-surface-overlay transition-colors text-center"
          >
            <Upload className="h-5 w-5 text-text-tertiary mx-auto mb-2.5" />
            <p className="text-sm text-text-secondary">Click to upload</p>
            <p className="text-xs text-text-disabled mt-1">PDF, DOCX, or TXT</p>
          </button>
        );

      case 'uploading':
        return (
          <CardBox>
            <SourceRow
              icon={<FileText className="h-4 w-4 text-text-tertiary" />}
              name={uploadState.filename}
              description={
                <span className="flex items-center gap-1.5">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-text-disabled" />
                  Uploading…
                </span>
              }
              action={null}
            />
          </CardBox>
        );

      case 'processing': {
        const stagesWithStatus = PROCESS_STAGES.map((stage) => {
          const stageIndex = PROCESS_STAGES.indexOf(stage);
          const activeIndex = processingStage
            ? PROCESS_STAGES.indexOf(processingStage as typeof PROCESS_STAGES[number])
            : -1;
          const isActive = processingStage === stage;
          const isDone = activeIndex > stageIndex;
          return { stage, isActive, isDone };
        }).filter(({ isActive, isDone }) => isActive || isDone);

        return (
          <CardBox>
            <SourceRow
              icon={<Loader2 className="h-4 w-4 text-text-tertiary animate-spin" />}
              name={uploadState.filename}
              description="Processing…"
              action={
                <button
                  type="button"
                  onClick={handleRemove}
                  className="text-xs text-text-tertiary hover:text-error transition-colors"
                >
                  Cancel
                </button>
              }
            />
            {stagesWithStatus.length > 0 && (
              <div className="space-y-1.5 pl-[52px]">
                {stagesWithStatus.map(({ stage, isActive, isDone }) => {
                  const stageIndex = PROCESS_STAGES.indexOf(stage as typeof PROCESS_STAGES[number]);
                  const nextStage = PROCESS_STAGES[stageIndex + 1];
                  const endTime = isDone && nextStage && stageStartedAt[nextStage]
                    ? stageStartedAt[nextStage] : Date.now();
                  const elapsed = stageStartedAt[stage]
                    ? Math.floor((endTime - stageStartedAt[stage]) / 1000) : 0;
                  return (
                    <div key={stage} className="flex items-center gap-2">
                      {isDone
                        ? <CheckCircle className="h-3 w-3 text-success shrink-0" />
                        : <div className="h-3 w-3 flex items-center justify-center shrink-0">
                            <div className="h-1.5 w-1.5 rounded-full bg-brand-primary animate-pulse" />
                          </div>}
                      <span className="text-xs text-text-secondary flex-1">
                        {PROCESS_STAGE_LABELS[stage]}{isActive ? '…' : ''}
                      </span>
                      {stageStartedAt[stage] && (
                        <span className="text-xs text-text-disabled">{formatElapsed(elapsed)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardBox>
        );
      }

      case 'ready':
        if (!uploadState.record.filename) {
          return (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-10 rounded-2xl border-2 border-dashed border-border-default bg-surface-base hover:border-border-strong hover:bg-surface-overlay transition-colors text-center"
            >
              <Upload className="h-5 w-5 text-text-tertiary mx-auto mb-2.5" />
              <p className="text-sm text-text-secondary">Click to upload</p>
              <p className="text-xs text-text-disabled mt-1">PDF, DOCX, or TXT</p>
            </button>
          );
        }
        return (
          <CardBox>
            <SourceRow
              icon={<FileText className="h-4 w-4 text-text-tertiary" />}
              name={uploadState.record.filename}
              badge={<StatusBadge label="Extracted" variant="green" />}
              description="Profile extracted from resume"
              action={
                <>
                  <button
                    type="button"
                    onClick={() => setConfirmDialog('resume-replace')}
                    className={outlineBtnCls}
                  >
                    Replace
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDialog('resume-remove')}
                    className="h-8 w-8 inline-flex items-center justify-center rounded-[10px] text-text-tertiary hover:text-error hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors"
                    title="Remove"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </>
              }
            />
          </CardBox>
        );

      case 'error':
        return (
          <CardBox className="border border-error/30 bg-red-50/40 dark:bg-red-950/10 gap-0">
            <SourceRow
              icon={<AlertCircle className="h-4 w-4 text-error" />}
              name="Processing failed"
              description={uploadState.message}
              action={
                <button
                  type="button"
                  onClick={handleRemove}
                  className={outlineBtnCls}
                >
                  Clear
                </button>
              }
            />
            <div className="pl-[52px] pt-1">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-xs text-text-link hover:underline"
              >
                Try again with a different file
              </button>
            </div>
          </CardBox>
        );
    }
  };

  /* ─── GitHub right-col content ─────────────────────────────────────────── */

  const githubConnected =
    uploadState.phase === 'ready' && !!uploadState.record.github_username;

  const renderGithubContent = () => {
    // ── Connected state ──────────────────────────────────────────────────────
    if (githubConnected && !githubEditing && uploadState.phase === 'ready') {
      return (
        <CardBox>
          <SourceRow
            icon={<LuGithub className="h-4 w-4 text-text-secondary" />}
            name={uploadState.record.github_username!}
            badge={<StatusBadge label="Connected" variant="green" />}
            description={`${uploadState.record.github_repos?.length ?? 0} repos selected`}
            action={
              <>
                <button
                  type="button"
                  onClick={() => { setGithubEditing(true); setGithubState('idle'); setGithubError(null); resetGithubPreview(); }}
                  className={outlineBtnCls}
                >
                  Change
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDialog('github-remove')}
                  disabled={githubState === 'removing'}
                  className="h-8 w-8 inline-flex items-center justify-center rounded-[10px] text-text-tertiary hover:text-error hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-50"
                  title="Remove"
                >
                  {githubState === 'removing'
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <X className="h-4 w-4" />}
                </button>
              </>
            }
          />
        </CardBox>
      );
    }

    // ── Step 2: repo selection ───────────────────────────────────────────────
    if (previewRepos !== null || githubState === 'fetching') {
      return (
        <CardBox>
          <div className="space-y-3">
            {/* Username header */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-text-secondary font-mono">
                @{parseGithubUsername(githubUrl)}
              </span>
              <button
                type="button"
                onClick={() => { resetGithubPreview(); setGithubState('idle'); setGithubError(null); }}
                className="text-xs text-text-tertiary hover:text-text-secondary"
              >
                Change username
              </button>
            </div>

            {githubState === 'fetching' ? (
              <div className="flex items-center gap-2 py-4 justify-center text-xs text-text-tertiary">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Fetching repos…
              </div>
            ) : previewRepos!.length === 0 ? (
              <p className="text-xs text-text-disabled italic py-2">No public repos found.</p>
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {previewRepos!.map((repo) => (
                  <label
                    key={repo.name}
                    className="flex items-start gap-2.5 px-2 py-1.5 rounded-lg hover:bg-surface-sunken cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedRepoNames.has(repo.name)}
                      onChange={() => toggleRepo(repo.name)}
                      className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 accent-brand-primary"
                    />
                    <div className="min-w-0">
                      <span className="text-xs font-medium text-text-primary font-mono">{repo.name}</span>
                      {repo.language && (
                        <span className="text-xs text-text-tertiary ml-2">{repo.language}</span>
                      )}
                      {repo.description && (
                        <p className="text-xs text-text-tertiary truncate mt-0.5">{repo.description}</p>
                      )}
                    </div>
                    {repo.pushed_at && (
                      <span className="text-xs text-text-disabled ml-auto flex-shrink-0">
                        {new Date(repo.pushed_at).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}
                      </span>
                    )}
                  </label>
                ))}
              </div>
            )}

            {githubState === 'error' && githubError && (
              <p className="text-xs text-error">{githubError}</p>
            )}

            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={handleGithubConnect}
                disabled={selectedRepoNames.size === 0 || githubState === 'saving' || githubState === 'fetching'}
                className={saveBtnCls}
              >
                {githubState === 'saving'
                  ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Connecting…</>
                  : `Connect (${selectedRepoNames.size} repo${selectedRepoNames.size !== 1 ? 's' : ''})`
                }
              </button>
              <button
                type="button"
                onClick={() => {
                  resetGithubPreview();
                  setGithubState('idle');
                  setGithubError(null);
                  if (githubEditing) setGithubEditing(false);
                }}
                className={outlineBtnCls}
              >
                Cancel
              </button>
            </div>
          </div>
        </CardBox>
      );
    }

    // ── Step 1: username input ───────────────────────────────────────────────
    return (
      <CardBox>
        <form onSubmit={handleGithubFetch} className="space-y-3">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LuGithub className="h-4 w-4 text-text-tertiary" />
            </div>
            <input
              type="text"
              value={githubUrl}
              onChange={(e) => { setGithubUrl(e.target.value); setGithubState('idle'); setGithubError(null); }}
              placeholder="github.com/username or username"
              className={cn(inputCls, 'pl-9')}
            />
          </div>
          {githubState === 'error' && githubError && (
            <p className="text-xs text-error">{githubError}</p>
          )}
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={!githubUrl.trim()}
              className={saveBtnCls}
            >
              Fetch Repos
            </button>
            {githubEditing && (
              <button
                type="button"
                onClick={() => { setGithubEditing(false); setGithubState('idle'); setGithubError(null); resetGithubPreview(); }}
                className={outlineBtnCls}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </CardBox>
    );
  };

  /* ─── Render ─────────────────────────────────────────────────────────────── */

  const hasProfile = uploadState.phase === 'ready' && !!uploadState.record.extracted_profile;

  return (
    <div className="h-full flex flex-col bg-surface-elevated">

      {/* Topbar */}
      <div className="shrink-0 flex items-center h-12 px-6 bg-surface-elevated">
        <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">My Experience</span>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-6xl mx-auto px-6 lg:px-16 pt-12 pb-24">

          {/* Three input sections */}
          <div className="divide-y divide-zinc-950/5 dark:divide-white/5 [&>*:first-child]:pt-0">

            {/* Resume */}
            <SettingRow
              title="Resume"
              description="Upload a PDF, DOCX, or TXT file. We'll extract your experience automatically."
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                className="hidden"
                onChange={handleFileChange}
              />
              {renderResumeContent()}
            </SettingRow>

            {/* GitHub */}
            <SettingRow
              title="GitHub"
              description="Import your public repos to enrich your profile with real project context."
            >
              {renderGithubContent()}
            </SettingRow>

            {/* Additional Context */}
            <SettingRow
              title="Additional Context"
              description="Skills, projects, or achievements not captured in your resume."
            >
              <form onSubmit={handleDirectSave} className="space-y-3">
                <textarea
                  value={directText}
                  onChange={(e) => { setDirectText(e.target.value); setDirectState('idle'); }}
                  placeholder="Describe your skills, projects, or achievements not captured in your resume…"
                  rows={6}
                  className={textareaCls}
                />
                <div className="flex items-center justify-between">
                  {directState === 'saved' && (
                    <span className="text-sm text-success">Saved</span>
                  )}
                  <button
                    type="submit"
                    disabled={!directText.trim() || directState === 'saving'}
                    className={cn(saveBtnCls, 'ml-auto')}
                  >
                    {directState === 'saving' ? (
                      <><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving…</>
                    ) : 'Save'}
                  </button>
                </div>
              </form>
            </SettingRow>

          </div>

          {/* Parsed profile — full-width section below the input rows */}
          {hasProfile && uploadState.phase === 'ready' && (
            <div className="mt-8 pt-8 border-t border-zinc-950/5 dark:border-white/5">

              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-sm font-medium text-text-primary">Parsed Profile</h2>
                  <p className="text-sm text-text-secondary mt-0.5">
                    Extracted from your sources — used to generate every tailoring.
                  </p>
                </div>
                {!editingProfile && uploadState.record.extracted_profile?.resume && (
                  <button
                    type="button"
                    onClick={() => { setEditingProfile(true); setProfileSaved(false); }}
                    className={outlineBtnCls}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit
                  </button>
                )}
              </div>

              {profileSaved && (
                <div className="flex items-center justify-between px-4 py-3 mb-6 rounded-xl bg-surface-base border border-border-subtle text-xs">
                  <span className="text-text-secondary">
                    Profile updated — you may want to regenerate tailorings for active applications.
                  </span>
                  <a
                    href="/dashboard"
                    className="text-text-link hover:underline shrink-0 ml-3 whitespace-nowrap"
                  >
                    View tailorings →
                  </a>
                </div>
              )}

              {editingProfile && uploadState.record.extracted_profile?.resume ? (
                <EditableResumeProfile
                  profile={uploadState.record.extracted_profile.resume}
                  onSave={handleSaveProfile}
                  onCancel={() => setEditingProfile(false)}
                />
              ) : (
                <ParsedProfile
                  profile={uploadState.record.extracted_profile!}
                  rawResumeText={uploadState.record.raw_resume_text}
                  repoDetails={uploadState.record.github_repo_details}
                />
              )}
            </div>
          )}

        </div>
      </div>

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
