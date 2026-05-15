'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import { ProfileChunkEditor } from '@/components/dashboard/ProfileChunkEditor';
import { ResumeUploadSection } from '@/components/dashboard/ResumeUploadSection';
import type { UploadPhase } from '@/components/dashboard/ResumeUploadSection';
import { GitHubSection } from '@/components/dashboard/GitHubSection';
import type { GithubState } from '@/components/dashboard/GitHubSection';
import type { ExperienceRecord, ExperienceChunksResponse, GitHubRepo, ProfileCorrections } from '@/types';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const _MONTH_ABBR: Record<string, number> = {
  jan:0, feb:1, mar:2, apr:3, may:4, jun:5, jul:6, aug:7, sep:8, oct:9, nov:10, dec:11,
};

function _parseDate(token: string): Date | null {
  const t = token.trim().toLowerCase();
  if (['present', 'current', 'now', 'today'].includes(t)) return new Date();
  let m = t.match(/^(\d{1,2})[/-](\d{4})$/);
  if (m) return new Date(parseInt(m[2]), parseInt(m[1]) - 1, 1);
  m = t.match(/^([a-z]{3})\s+(\d{4})$/);
  if (m && m[1] in _MONTH_ABBR) return new Date(parseInt(m[2]), _MONTH_ABBR[m[1]], 1);
  m = t.match(/^(\d{4})$/);
  if (m) return new Date(parseInt(m[1]), 0, 1);
  return null;
}

// computeYoE: parses duration strings (e.g. "Mar 2020 – Present") from each role,
// builds date intervals, merges overlapping ones (handles concurrent roles correctly),
// then returns the total accumulated years as a float.
function computeYoE(workExperience: Array<{ duration?: string | null }>): number {
  const intervals: Array<[Date, Date]> = [];
  for (const role of workExperience) {
    const dur = role.duration?.trim();
    if (!dur) continue;
    const parts = dur.split(/\s*[-–—]\s*|\s+to\s+/);
    if (parts.length !== 2) continue;
    const start = _parseDate(parts[0]);
    const end = _parseDate(parts[1]);
    if (start && end && end >= start) intervals.push([start, end]);
  }
  if (!intervals.length) return 0;
  const sorted = [...intervals].sort((a, b) => a[0].getTime() - b[0].getTime());
  // Merge overlapping intervals so concurrent roles don't double-count time
  const merged: Array<[Date, Date]> = [sorted[0]];
  for (const [s, e] of sorted.slice(1)) {
    const last = merged[merged.length - 1];
    if (s <= last[1]) { merged[merged.length - 1] = [last[0], e > last[1] ? e : last[1]]; }
    else { merged.push([s, e]); }
  }
  const totalMs = merged.reduce((sum, [s, e]) => sum + (e.getTime() - s.getTime()), 0);
  return Math.round((totalMs / (365.25 * 24 * 60 * 60 * 1000)) * 10) / 10;
}

/* ─── Types ─────────────────────────────────────────────────────────────── */

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

  const _emptyProfile = { yoe_override: '', title: '', location: '', headline: '', summary: '', email: '', phone: '', linkedin: '' };
  const [profileFields, setProfileFields] = useState(_emptyProfile);
  const [profileFieldsInitial, setProfileFieldsInitial] = useState(_emptyProfile);
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
    const fields = {
      yoe_override: corrections.yoe_override != null ? String(corrections.yoe_override) : '',
      title: corrections.title ?? resume?.title ?? '',
      location: corrections.location ?? resume?.location ?? '',
      headline: corrections.headline ?? resume?.headline ?? '',
      summary: corrections.summary ?? resume?.summary ?? '',
      email: corrections.email ?? resume?.email ?? '',
      phone: corrections.phone ?? resume?.phone ?? '',
      linkedin: corrections.linkedin ?? resume?.linkedin ?? '',
    };
    setProfileFields(fields);
    setProfileFieldsInitial(fields);
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
      // Always send all fields. Empty string → null which tells the backend to clear
      // the correction (falling back to the extracted value on next read).
      const yoe = parseFloat(profileFields.yoe_override);
      const payload: Record<string, string | number | null> = {
        yoe_override: (profileFields.yoe_override !== '' && !isNaN(yoe)) ? yoe : null,
        title: profileFields.title,
        location: profileFields.location,
        headline: profileFields.headline,
        summary: profileFields.summary,
        email: profileFields.email,
        phone: profileFields.phone,
        linkedin: profileFields.linkedin,
      };

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
      setProfileFieldsInitial(profileFields); // mark current fields as saved baseline
      toast.success('Profile signals saved');
    } catch {
      toastError('Failed to save profile signals');
    } finally {
      setProfileSaving(false);
    }
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
            <ResumeUploadSection
              uploadState={uploadState}
              processingStage={processingStage}
              stageStartedAt={stageStartedAt}
              readOnly={readOnly}
              onUploadClick={() => fileInputRef.current?.click()}
              onCancelProcessing={handleRemove}
              onReplace={() => setConfirmDialog('resume-replace')}
              onRemove={() => setConfirmDialog('resume-remove')}
            />
            <GitHubSection
              isInitialLoad={uploadState.phase === 'loading'}
              connectedGithub={connectedGithub}
              githubEditing={githubEditing}
              githubUrl={githubUrl}
              githubState={githubState}
              githubError={githubError}
              previewRepos={previewRepos}
              selectedRepoNames={selectedRepoNames}
              acknowledged={acknowledged}
              previouslyConnectedRepos={previouslyConnectedRepos}
              scanningRepos={scanningRepos}
              readOnly={readOnly}
              onGithubUrlChange={(url) => { setGithubUrl(url); setGithubState('idle'); setGithubError(null); }}
              onGithubFetch={handleGithubFetch}
              onGithubConnect={handleGithubConnect}
              onGithubModify={handleGithubModify}
              onDisconnectRequest={() => setConfirmDialog('github-remove')}
              onToggleRepo={toggleRepo}
              onAcknowledgeChange={setAcknowledged}
              onCancelEdit={() => { resetGithubPreview(); setGithubState('idle'); setGithubError(null); if (githubEditing) setGithubEditing(false); }}
              onRescanRequest={setRescanConfirm}
              parseUsername={parseGithubUsername}
            />
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
                  <div className="mt-5 space-y-4">

                    {/* Row 1: Contact — Email · Phone · LinkedIn */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-email" className="text-xs font-medium text-text-secondary">Email</label>
                        <input
                          id="profile-email"
                          type="email"
                          value={profileFields.email}
                          onChange={(e) => setProfileFields((p) => ({ ...p, email: e.target.value }))}
                          placeholder="you@example.com"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-phone" className="text-xs font-medium text-text-secondary">Phone</label>
                        <input
                          id="profile-phone"
                          type="tel"
                          value={profileFields.phone}
                          onChange={(e) => setProfileFields((p) => ({ ...p, phone: e.target.value }))}
                          placeholder="+1 555 000 0000"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-linkedin" className="text-xs font-medium text-text-secondary">LinkedIn</label>
                        <input
                          id="profile-linkedin"
                          type="text"
                          value={profileFields.linkedin}
                          onChange={(e) => setProfileFields((p) => ({ ...p, linkedin: e.target.value }))}
                          placeholder="linkedin.com/in/username"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                    </div>
                    {/* Row 2: YoE · Title · Location */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-yoe" className="text-xs font-medium text-text-secondary">Years of experience</label>
                        <input
                          id="profile-yoe"
                          type="number"
                          min="0"
                          step="0.5"
                          value={profileFields.yoe_override}
                          onChange={(e) => setProfileFields((p) => ({ ...p, yoe_override: e.target.value }))}
                          placeholder={(() => {
                            const we = uploadState.phase === 'ready' ? (uploadState.record.extracted_profile?.resume?.work_experience ?? []) : [];
                            const yoe = computeYoE(we);
                            return yoe >= 0 ? `${yoe} (auto-computed)` : 'Auto-computed';
                          })()}
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-title" className="text-xs font-medium text-text-secondary">Title</label>
                        <input
                          id="profile-title"
                          type="text"
                          value={profileFields.title}
                          onChange={(e) => setProfileFields((p) => ({ ...p, title: e.target.value }))}
                          placeholder="e.g. Software Engineer"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-location" className="text-xs font-medium text-text-secondary">Location</label>
                        <input
                          id="profile-location"
                          type="text"
                          value={profileFields.location}
                          onChange={(e) => setProfileFields((p) => ({ ...p, location: e.target.value }))}
                          placeholder="e.g. San Francisco, CA"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                    </div>

                    {/* Row 3: Headline (full width) */}
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="profile-headline" className="text-xs font-medium text-text-secondary">Headline</label>
                      <input
                        id="profile-headline"
                        type="text"
                        value={profileFields.headline}
                        onChange={(e) => setProfileFields((p) => ({ ...p, headline: e.target.value }))}
                        placeholder="e.g. Senior Software Engineer building developer tools"
                        disabled={readOnly}
                        className={inputCls}
                      />
                    </div>

                    {/* Row 4: Summary (full width) */}
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="profile-summary" className="text-xs font-medium text-text-secondary">Summary</label>
                      <textarea
                        id="profile-summary"
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
                        disabled={profileSaving || JSON.stringify(profileFields) === JSON.stringify(profileFieldsInitial)}
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
            <ProfileChunkEditor refreshKey={chunksRefreshKey} initialData={initialChunks} readOnly={readOnly} />
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
