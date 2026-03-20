'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload,
  Github,
  FileText,
  Loader2,
  CheckCircle,
  AlertCircle,
  Pencil,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { toastError, formatElapsed } from '@/lib/utils';
import { ParsedProfile } from '@/components/dashboard/ParsedProfile';
import { EditableResumeProfile } from '@/components/dashboard/EditableResumeProfile';
import type { ExperienceRecord, ExtractedProfile } from '@/types';

type UploadPhase =
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'processing'; filename: string; experienceId: string }
  | { phase: 'ready'; record: ExperienceRecord }
  | { phase: 'error'; message: string };

type GithubState = 'idle' | 'saving' | 'saved' | 'removing' | 'error';
type SaveState = 'idle' | 'saving' | 'saved';

const PROCESS_STAGE_LABELS: Record<string, string> = {
  extracting: 'Extracting text',
  analyzing: 'Analyzing profile',
};
const PROCESS_STAGES = ['extracting', 'analyzing'] as const;

export function ExperienceManager() {
  const [uploadState, setUploadState] = useState<UploadPhase>({ phase: 'idle' });
  const [githubUrl, setGithubUrl] = useState('');
  const [githubState, setGithubState] = useState<GithubState>('idle');
  const [githubError, setGithubError] = useState<string | null>(null);
  const [directText, setDirectText] = useState('');
  const [directState, setDirectState] = useState<SaveState>('idle');

  // SSE processing state
  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const [stageStartedAt, setStageStartedAt] = useState<Record<string, number>>({});
  const [tick, setTick] = useState(0);

  // Profile editing
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Tick every second while processing (drives elapsed time display)
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

  // Fallback polling — used when page loads mid-processing (no live SSE stream)
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
          setUploadState({
            phase: 'error',
            message: record.error_message ?? 'Processing failed',
          });
        }
      } catch {
        // ignore transient poll errors
      }
    }, 3000);
  }, [stopPolling]);

  // Restore state on mount
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
          setUploadState({
            phase: 'processing',
            filename: record.filename ?? '',
            experienceId: record.id,
          });
          startPolling(); // SSE gone — fall back to polling
        } else if (record.status === 'error') {
          setUploadState({
            phase: 'error',
            message: record.error_message ?? 'Processing failed',
          });
        }
      } catch {
        // ignore
      }
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
      // Step 1: Get upload URL
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

      // Step 2: Upload to blob storage
      const uploadRes = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type || 'application/octet-stream',
          'x-ms-blob-type': 'BlockBlob',
        },
      });
      if (!uploadRes.ok) {
        throw new Error(`Failed to upload file to storage (${uploadRes.status})`);
      }

      // Step 3: Start SSE stream
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

      // Step 4: Read SSE events
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
    await fetch('/api/experience', { method: 'DELETE' }).catch(() => {});
    setUploadState({ phase: 'idle' });
    setProcessingStage(null);
    setStageStartedAt({});
    setEditingProfile(false);
    setProfileSaved(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  function parseGithubUsername(input: string): string {
    const match = input.match(/github\.com\/([^/]+)/);
    return match ? match[1] : input.trim();
  }

  const handleGithubSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const username = parseGithubUsername(githubUrl);
    if (!username) return;

    setGithubState('saving');
    setGithubError(null);

    const res = await fetch('/api/experience/github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ github_username: username }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      setGithubError(err.detail ?? `Error ${res.status}`);
      setGithubState('error');
      return;
    }

    setGithubState('saved');
    toast.success('GitHub profile added');

    const updated = await fetch('/api/experience').then((r) => r.json());
    if (updated) setUploadState({ phase: 'ready', record: updated });
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
    toast.success('GitHub profile removed');

    const updated = await fetch('/api/experience').then((r) => r.json());
    if (updated) setUploadState({ phase: 'ready', record: updated });
  };

  const handleDirectSave = async (e: React.FormEvent) => {
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

  const renderResumeContent = () => {
    switch (uploadState.phase) {
      case 'idle':
        return (
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full px-4 py-8 rounded-lg border border-dashed border-border-default hover:border-brand-primary/50 bg-surface-elevated hover:bg-surface-overlay transition-colors text-center"
          >
            <Upload className="h-5 w-5 text-text-tertiary mx-auto mb-2" />
            <p className="text-sm text-text-secondary">Click to upload resume</p>
            <p className="text-xs text-text-tertiary mt-1">PDF, DOCX, or TXT</p>
          </button>
        );

      case 'uploading':
        return (
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border-subtle bg-surface-elevated">
            <Loader2 className="h-4 w-4 text-text-tertiary animate-spin flex-shrink-0" />
            <span className="text-sm text-text-secondary truncate">
              Uploading {uploadState.filename}…
            </span>
          </div>
        );

      case 'processing': {
        const stagesWithStatus = PROCESS_STAGES.map((stage) => {
          const stageIndex = PROCESS_STAGES.indexOf(stage);
          const activeIndex = processingStage ? PROCESS_STAGES.indexOf(processingStage as typeof PROCESS_STAGES[number]) : -1;
          const isActive = processingStage === stage;
          const isDone = activeIndex > stageIndex;
          return { stage, isActive, isDone };
        }).filter(({ isActive, isDone }) => isActive || isDone);

        return (
          <div className="px-4 py-3.5 rounded-lg border border-border-subtle bg-surface-elevated space-y-3">
            <div className="flex items-center gap-3">
              <Loader2 className="h-4 w-4 text-text-tertiary animate-spin flex-shrink-0" />
              <p className="text-sm text-text-primary truncate flex-1">{uploadState.filename}</p>
              <button
                onClick={handleRemove}
                className="text-xs text-text-tertiary hover:text-text-secondary flex-shrink-0"
              >
                Cancel
              </button>
            </div>
            {stagesWithStatus.length > 0 && (
              <div className="space-y-1 pl-7">
                {stagesWithStatus.map(({ stage, isActive, isDone }) => {
                  const elapsed = stageStartedAt[stage]
                    ? Math.floor((Date.now() - stageStartedAt[stage]) / 1000)
                    : 0;
                  return (
                    <div key={stage} className="flex items-center gap-2">
                      {isDone ? (
                        <CheckCircle className="h-3 w-3 text-success flex-shrink-0" />
                      ) : (
                        <div className="h-3 w-3 flex items-center justify-center flex-shrink-0">
                          <div className="h-1.5 w-1.5 rounded-full bg-brand-primary animate-pulse" />
                        </div>
                      )}
                      <span className="text-xs text-text-secondary">
                        {PROCESS_STAGE_LABELS[stage]}{isActive ? '...' : ''}
                      </span>
                      {stageStartedAt[stage] && (
                        <span className="text-xs text-text-tertiary ml-auto">
                          {formatElapsed(elapsed)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      }

      case 'ready':
        return (
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border-subtle bg-surface-elevated">
            <CheckCircle className="h-4 w-4 text-success flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-text-primary truncate">
                {uploadState.record.filename}
              </p>
              <p className="text-xs text-text-tertiary mt-0.5">Profile extracted</p>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-xs text-text-tertiary hover:text-text-secondary"
              >
                Replace
              </button>
              <button
                onClick={handleRemove}
                className="text-xs text-text-tertiary hover:text-error"
              >
                Remove
              </button>
            </div>
          </div>
        );

      case 'error':
        return (
          <div className="space-y-2">
            <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border-subtle bg-surface-elevated">
              <AlertCircle className="h-4 w-4 text-error flex-shrink-0" />
              <p className="text-sm text-error flex-1 truncate">{uploadState.message}</p>
              <button
                onClick={handleRemove}
                className="text-xs text-text-tertiary hover:text-text-secondary flex-shrink-0"
              >
                Clear
              </button>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-xs text-text-link hover:underline"
            >
              Try again
            </button>
          </div>
        );
    }
  };

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-2xl mx-auto p-6 lg:p-8 space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">My Experience</h1>
          <p className="mt-1 text-text-secondary">
            Add your background using one or more sources — we&apos;ll combine them.
          </p>
        </div>

        {/* Resume */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-text-tertiary" />
            <h2 className="text-sm font-medium text-text-primary">Resume</h2>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx,.txt"
            className="hidden"
            onChange={handleFileChange}
          />
          {renderResumeContent()}
        </section>

        {/* GitHub */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Github className="h-4 w-4 text-text-tertiary" />
            <h2 className="text-sm font-medium text-text-primary">GitHub Profile</h2>
          </div>
          {uploadState.phase === 'ready' && uploadState.record.github_username ? (
            <div className="flex items-center gap-3 px-4 py-3 rounded-lg border border-border-subtle bg-surface-elevated">
              <CheckCircle className="h-4 w-4 text-success flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text-primary truncate">
                  {uploadState.record.github_username}
                </p>
                <p className="text-xs text-text-tertiary mt-0.5">
                  {uploadState.record.github_repos?.length ?? 0} repos imported
                </p>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <button
                  onClick={() => setGithubState('idle')}
                  className="text-xs text-text-tertiary hover:text-text-secondary"
                >
                  Change
                </button>
                <button
                  onClick={handleGithubRemove}
                  disabled={githubState === 'removing'}
                  className="text-xs text-text-tertiary hover:text-error disabled:opacity-50"
                >
                  {githubState === 'removing' ? 'Removing…' : 'Remove'}
                </button>
              </div>
            </div>
          ) : (
            <>
              <form onSubmit={handleGithubSave} className="flex gap-2">
                <Input
                  type="text"
                  value={githubUrl}
                  onChange={(e) => {
                    setGithubUrl(e.target.value);
                    setGithubState('idle');
                    setGithubError(null);
                  }}
                  placeholder="https://github.com/username or username"
                />
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  disabled={!githubUrl.trim() || githubState === 'saving'}
                  className="flex-shrink-0"
                >
                  {githubState === 'saving' ? 'Saving…' : 'Save'}
                </Button>
              </form>
              {githubState === 'error' && githubError && (
                <p className="text-xs text-error">{githubError}</p>
              )}
            </>
          )}
        </section>

        {/* Direct input */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-text-tertiary" />
            <h2 className="text-sm font-medium text-text-primary">Additional Context</h2>
            {directState === 'saved' && (
              <span className="text-xs text-success ml-auto">Saved</span>
            )}
          </div>
          <form onSubmit={handleDirectSave} className="space-y-2">
            <textarea
              value={directText}
              onChange={(e) => {
                setDirectText(e.target.value);
                setDirectState('idle');
              }}
              placeholder="Describe your skills, projects, or achievements not captured in your resume…"
              rows={6}
              className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm text-text-primary placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-none"
            />
            <div className="flex justify-end">
              <Button
                type="submit"
                variant="outline"
                size="sm"
                disabled={!directText.trim() || directState === 'saving'}
              >
                {directState === 'saving' ? 'Saving…' : 'Save'}
              </Button>
            </div>
          </form>
        </section>

        {/* Parsed profile */}
        {uploadState.phase === 'ready' && uploadState.record.extracted_profile && (
          <section className="space-y-3 pt-4 border-t border-border-subtle">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-text-primary">Parsed Profile</h2>
              {!editingProfile && uploadState.record.extracted_profile.resume && (
                <button
                  onClick={() => { setEditingProfile(true); setProfileSaved(false); }}
                  className="flex items-center gap-1.5 text-xs text-text-tertiary hover:text-text-primary transition-colors"
                >
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
              )}
            </div>

            {profileSaved && (
              <div className="flex items-center justify-between px-3 py-2 rounded-md bg-surface-elevated border border-border-subtle text-xs">
                <span className="text-text-secondary">
                  Profile updated — you may want to regenerate tailorings for active applications.
                </span>
                <a
                  href="/dashboard/tailorings"
                  className="text-text-link hover:underline flex-shrink-0 ml-3 whitespace-nowrap"
                >
                  View tailorings →
                </a>
              </div>
            )}

            {editingProfile && uploadState.record.extracted_profile.resume ? (
              <EditableResumeProfile
                profile={uploadState.record.extracted_profile.resume}
                onSave={handleSaveProfile}
                onCancel={() => setEditingProfile(false)}
              />
            ) : (
              <ParsedProfile
                profile={uploadState.record.extracted_profile}
                rawResumeText={uploadState.record.raw_resume_text}
              />
            )}
          </section>
        )}
      </div>
    </div>
  );
}
