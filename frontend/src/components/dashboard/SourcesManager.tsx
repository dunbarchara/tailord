'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  ChevronDown, FileText, AlignLeft, Globe, Upload,
  Loader2, AlertCircle, X, RefreshCw, Check, Plus, Trash2, MessageSquare,
} from 'lucide-react';
import { SiGithub, SiLinear, SiSlack, SiDiscord } from 'react-icons/si';
import { toast } from 'sonner';
import { cn, toastError, formatRelativeDate, formatElapsed } from '@/lib/utils';
import type { ExperienceRecord, ExperienceGroup, GitHubRepo } from '@/types';
import type { UploadPhase } from '@/components/dashboard/ResumeUploadSection';
import type { GithubState } from '@/components/dashboard/GitHubSection';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';

/* ─── Types ─────────────────────────────────────────────────────────────── */

const CONFIRM_CONFIGS = {
  'resume-remove': {
    title: 'Remove resume',
    description: 'What should happen to the claims and groups derived from this resume?',
    keepLabel: 'Keep claims',
    deleteLabel: 'Delete everything',
  },
  'resume-replace': {
    title: 'Replace resume',
    description: 'Your current resume will be replaced. What should happen to the existing claims and groups derived from it?',
    keepLabel: 'Keep existing claims',
    deleteLabel: 'Replace with new',
  },
  'github-remove': {
    title: 'Remove GitHub',
    description: 'What should happen to the claims and groups derived from your GitHub repos?',
    keepLabel: 'Keep claims',
    deleteLabel: 'Delete everything',
  },
  'github-change': {
    title: 'Change GitHub profile',
    description: 'What should happen to the claims and groups derived from the current GitHub profile?',
    keepLabel: 'Keep claims',
    deleteLabel: 'Delete everything',
  },
  'github-repos-remove': {
    title: 'Remove repositories',
    description: 'What should happen to the claims and groups derived from the removed repos?',
    keepLabel: 'Keep claims',
    deleteLabel: 'Delete everything',
  },
} as const;

type ConfirmAction = keyof typeof CONFIRM_CONFIGS;
type CardStatus = 'connected' | 'processing' | 'error' | 'idle';

const PROCESS_STAGES = ['extracting', 'analyzing'] as const;
const PROCESS_STAGE_LABELS: Record<string, string> = { extracting: 'Extracting text', analyzing: 'Analyzing profile' };

/* ─── Shared styles ─────────────────────────────────────────────────────── */

const inputCls =
  'w-full h-9 rounded-xl border border-border-default bg-surface-elevated px-3 text-sm text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
  'hover:border-border-strong hover:bg-surface-base ' +
  'focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)] disabled:opacity-50 disabled:cursor-not-allowed';

const btnPrimary =
  'inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-medium tracking-[-0.1px] ' +
  'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 ' +
  'hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed';

const btnGhost =
  'inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] ' +
  'border border-border-default bg-surface-elevated text-text-secondary ' +
  'hover:bg-surface-base hover:border-border-strong hover:text-text-primary ' +
  'transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

const btnDanger =
  'inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] ' +
  'text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20 transition-colors disabled:opacity-50';

const btnSubtle =
  'inline-flex items-center gap-1.5 h-7 px-2 rounded-lg text-sm font-normal text-text-secondary ' +
  'hover:bg-surface-base hover:text-text-primary transition-colors';

/* ─── UI helpers ─────────────────────────────────────────────────────────── */

const STATUS_CONFIG: Record<CardStatus, { dotCls: string; textCls: string; label: string }> = {
  connected: { dotCls: 'bg-emerald-500', textCls: 'text-emerald-600 dark:text-emerald-400', label: 'Connected' },
  processing: { dotCls: 'bg-amber-500 animate-pulse', textCls: 'text-amber-600 dark:text-amber-400', label: 'Processing' },
  error: { dotCls: 'bg-red-500', textCls: 'text-red-600 dark:text-red-400', label: 'Needs attention' },
  idle: { dotCls: 'border border-border-strong bg-transparent', textCls: 'text-text-disabled', label: 'Not connected' },
};

function StatusBadge({ status }: { status: CardStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', cfg.textCls)}>
      <span className={cn('w-[7px] h-[7px] rounded-full flex-none', cfg.dotCls)} />
      {cfg.label}
    </span>
  );
}

function LogoTile({ children, idle }: { children: React.ReactNode; idle?: boolean }) {
  return (
    <div className={cn(
      'w-10 h-10 flex-none rounded-xl border flex items-center justify-center',
      idle
        ? 'bg-surface-base border-border-subtle opacity-60'
        : 'bg-surface-base border-border-subtle',
    )}>
      {children}
    </div>
  );
}

function Drawer({ open, children }: { open: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateRows: open ? '1fr' : '0fr', transition: 'grid-template-rows 0.18s ease' }}>
      <div style={{ overflow: 'hidden', minHeight: 0 }}>
        {children}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-widest text-text-tertiary mb-2.5">
      {children}
    </p>
  );
}

function ConnectedItem({
  icon,
  name,
  sub,
  scanning,
  onRemove,
}: {
  icon: React.ReactNode;
  name: string;
  sub?: string;
  scanning?: boolean;
  onRemove?: () => void;
}) {
  return (
    <div className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-surface-base group transition-colors">
      <span className="w-4 h-4 flex-none text-text-tertiary">{icon}</span>
      <span className="flex-1 min-w-0 text-sm text-text-primary truncate">
        {name}
        {sub && <span className="text-text-tertiary"> · {sub}</span>}
      </span>
      {scanning ? (
        <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
          <Loader2 className="h-3 w-3 animate-spin" />
          Scanning…
        </span>
      ) : (
        onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="opacity-0 group-hover:opacity-100 w-6 h-6 rounded-md flex items-center justify-center text-text-tertiary hover:bg-red-50 dark:hover:bg-red-950/20 hover:text-red-500 transition-all"
            aria-label={`Remove ${name}`}
          >
            <X className="h-3 w-3" />
          </button>
        )
      )}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-red-50/60 dark:bg-red-950/10 border border-red-200/60 dark:border-red-900/30 mb-4">
      <AlertCircle className="h-4 w-4 text-red-500 flex-none" />
      <span className="text-sm text-red-700 dark:text-red-400 font-medium">{message}</span>
    </div>
  );
}

function ExpandInfo({ points, permission }: { points: string[]; permission: string }) {
  return (
    <div className="mb-4">
      <SectionLabel>What Tailord pulls</SectionLabel>
      <div className="flex flex-col gap-2 mb-3">
        {points.map((p) => (
          <div key={p} className="flex items-start gap-2.5 text-sm text-text-secondary">
            <Check className="h-3.5 w-3.5 mt-0.5 flex-none text-emerald-500" />
            {p}
          </div>
        ))}
      </div>
      <p className="text-xs text-text-tertiary">{permission}</p>
    </div>
  );
}

function DrawerDivider({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-5 pt-5 pb-5 border-t border-zinc-950/5 dark:border-white/5">
      {children}
    </div>
  );
}

function DrawerFooter({ left, children }: { left?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 pt-4 mt-2 border-t border-zinc-950/5 dark:border-white/5">
      {left && <span className="text-xs text-text-tertiary mr-auto">{left}</span>}
      {children}
    </div>
  );
}

/* ─── SourceCard ─────────────────────────────────────────────────────────── */

function SourceCard({
  logo,
  name,
  status,
  meta,
  open,
  onToggle,
  idle,
  children,
}: {
  logo: React.ReactNode;
  name: string;
  status: CardStatus;
  meta: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  idle?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={cn(
      'bg-surface-elevated rounded-2xl border transition-[border-color,box-shadow] duration-150',
      idle
        ? 'border-dashed border-border-default'
        : open
          ? 'border-border-default shadow-[0_4px_14px_rgba(0,0,0,0.06)]'
          : 'border-border-subtle shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:border-border-default hover:shadow-[0_4px_14px_rgba(0,0,0,0.06)]',
    )}>
      {/* Collapsed header */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
        className="flex items-center gap-3.5 px-5 py-4 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent focus-visible:ring-offset-1 rounded-2xl"
      >
        <LogoTile idle={idle}>{logo}</LogoTile>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 mb-0.5">
            <span className="text-sm font-semibold tracking-[-0.01em] text-text-primary">{name}</span>
            <StatusBadge status={status} />
          </div>
          <div className="text-xs text-text-tertiary truncate">{meta}</div>
        </div>

        <div className="flex items-center gap-2 flex-none">
          {idle && (
            <button type="button" onClick={(e) => { e.stopPropagation(); onToggle(); }} className={btnPrimary} style={{ height: '30px', fontSize: '12.5px' }}>
              Connect
            </button>
          )}
          <ChevronDown
            className={cn('h-4.5 w-4.5 text-text-tertiary transition-transform duration-200', open && 'rotate-180')}
            style={{ width: 18, height: 18 }}
          />
        </div>
      </div>

      {/* Expanded drawer */}
      <Drawer open={open}>
        {children}
      </Drawer>
    </div>
  );
}

/* ─── Resume expanded content ────────────────────────────────────────────── */

function ResumeIdle({ onUpload }: { onUpload: () => void }) {
  return (
    <DrawerDivider>
      <ExpandInfo
        points={[
          'Work history — roles, companies, and durations',
          'Skills and technologies you\'ve worked with',
          'Education and certifications',
          'Contact details for your profile',
        ]}
        permission="Your file is processed and never shared with third parties."
      />
      <div className="flex items-center gap-3">
        <button type="button" onClick={onUpload} className={btnPrimary}>
          <Upload className="h-3.5 w-3.5" />
          Upload resume
        </button>
      </div>
    </DrawerDivider>
  );
}

function ResumeProcessing({
  filename,
  processingStage,
  stageStartedAt,
  onCancel,
}: {
  filename: string;
  processingStage: string | null;
  stageStartedAt: Record<string, number>;
  onCancel: () => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const firstStage = Object.keys(stageStartedAt)[0];
  const overallStart = firstStage ? stageStartedAt[firstStage] : undefined;
  const elapsed = overallStart ? Math.floor((now - overallStart) / 1000) : 0;
  const stageLabel = processingStage ? (PROCESS_STAGE_LABELS[processingStage] ?? processingStage) : 'Processing';

  return (
    <DrawerDivider>
      <div className="flex items-center gap-3 mb-4 px-3 py-3 rounded-xl bg-surface-base border border-border-subtle">
        <Loader2 className="h-4 w-4 text-amber-500 animate-spin flex-none" />
        <div className="min-w-0">
          <p className="text-sm text-text-primary font-medium truncate">{filename}</p>
          <p className="text-xs text-text-tertiary">
            {stageLabel}…{overallStart ? ` ${formatElapsed(elapsed)}` : ''}
          </p>
        </div>
      </div>
      <DrawerFooter>
        <button type="button" onClick={onCancel} className={btnDanger}>
          Cancel
        </button>
      </DrawerFooter>
    </DrawerDivider>
  );
}

function ResumeError({ message, onRetry, onClear }: { message: string; onRetry: () => void; onClear: () => void }) {
  return (
    <DrawerDivider>
      <ErrorBanner message={message} />
      <DrawerFooter>
        <button type="button" onClick={onRetry} className={btnPrimary}>
          <Upload className="h-3.5 w-3.5" />
          Try again
        </button>
        <button type="button" onClick={onClear} className={btnDanger}>
          Clear
        </button>
      </DrawerFooter>
    </DrawerDivider>
  );
}

function ResumeConnected({
  record,
  onReplace,
  onRemove,
}: {
  record: ExperienceRecord;
  onReplace: () => void;
  onRemove: () => void;
}) {
  return (
    <DrawerDivider>
      <SectionLabel>Document</SectionLabel>
      <div className="mb-4">
        <ConnectedItem
          icon={<FileText className="h-full w-full" />}
          name={record.filename ?? 'Resume'}
          sub="Processed"
        />
      </div>
      <DrawerFooter left={record.processed_at ? `Updated ${formatRelativeDate(record.processed_at) ?? ''}` : undefined}>
        <button type="button" onClick={onReplace} className={btnGhost}>
          <RefreshCw className="h-3.5 w-3.5" />
          Replace
        </button>
        <button type="button" onClick={onRemove} className={btnDanger}>
          <Trash2 className="h-3.5 w-3.5" />
          Remove
        </button>
      </DrawerFooter>
    </DrawerDivider>
  );
}

/* ─── GitHub expanded content ────────────────────────────────────────────── */

function GitHubRepoIcon() {
  return (
    <svg className="h-full w-full" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 2.5h7.5A1.5 1.5 0 0 1 12 4v9.5H4.5A1.5 1.5 0 0 1 3 12V2.5z" />
      <path d="M3 11.5A1.5 1.5 0 0 1 4.5 10H12" />
    </svg>
  );
}

function GitHubIdle({
  githubUrl,
  githubState,
  githubError,
  previewRepos,
  selectedRepoNames,
  acknowledged,
  onUrlChange,
  onFetch,
  onToggleRepo,
  onAcknowledge,
  onConnect,
  onCancel,
}: {
  githubUrl: string;
  githubState: GithubState;
  githubError: string | null;
  previewRepos: GitHubRepo[] | null;
  selectedRepoNames: Set<string>;
  acknowledged: boolean;
  onUrlChange: (v: string) => void;
  onFetch: (e: React.SyntheticEvent<HTMLFormElement>) => void;
  onToggleRepo: (name: string) => void;
  onAcknowledge: (v: boolean) => void;
  onConnect: () => void;
  onCancel: () => void;
}) {
  const fetching = githubState === 'fetching';
  const saving = githubState === 'saving';

  return (
    <DrawerDivider>
      {!previewRepos && (
        <ExpandInfo
          points={[
            'Repository descriptions and README content',
            'Commit activity and contribution signals',
            'Languages and technologies you\'ve used',
            'Open-source projects and collaborations',
          ]}
          permission="Read-only access — you choose which repositories to include."
        />
      )}

      {githubError && <ErrorBanner message={githubError} />}

      {!previewRepos ? (
        <form onSubmit={onFetch} className="flex gap-2">
          <input
            type="text"
            value={githubUrl}
            onChange={(e) => onUrlChange(e.target.value)}
            placeholder="github.com/username or username"
            className={cn(inputCls, 'flex-1')}
            disabled={fetching}
          />
          <button type="submit" disabled={!githubUrl.trim() || fetching} className={btnPrimary}>
            {fetching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            {fetching ? 'Fetching…' : 'Fetch repos'}
          </button>
        </form>
      ) : (
        <>
          <SectionLabel>Select repositories to include</SectionLabel>
          <div className="flex flex-col gap-1 mb-4 max-h-[260px] overflow-y-auto">
            {previewRepos.map((repo) => (
              <label
                key={repo.name}
                className="flex items-center gap-3 px-2.5 py-2 rounded-lg hover:bg-surface-base cursor-pointer group transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedRepoNames.has(repo.name)}
                  onChange={() => onToggleRepo(repo.name)}
                  className="h-3.5 w-3.5 rounded accent-zinc-900 dark:accent-white"
                />
                <span className="w-4 h-4 flex-none text-text-tertiary"><GitHubRepoIcon /></span>
                <span className="flex-1 min-w-0 text-sm text-text-primary truncate">{repo.name}</span>
                {repo.description && (
                  <span className="text-xs text-text-tertiary truncate max-w-[180px] hidden sm:block">{repo.description}</span>
                )}
              </label>
            ))}
          </div>

          <label className="flex items-start gap-2.5 mb-4 cursor-pointer">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => onAcknowledge(e.target.checked)}
              className="mt-0.5 h-3.5 w-3.5 rounded accent-zinc-900 dark:accent-white"
            />
            <span className="text-xs text-text-secondary">
              I understand Tailord will read the selected repositories to extract experience signals.
            </span>
          </label>

          <DrawerFooter>
            <button
              type="button"
              onClick={onConnect}
              disabled={selectedRepoNames.size === 0 || !acknowledged || saving}
              className={btnPrimary}
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {saving ? 'Connecting…' : `Connect ${selectedRepoNames.size > 0 ? selectedRepoNames.size : ''} repo${selectedRepoNames.size !== 1 ? 's' : ''}`}
            </button>
            <button type="button" onClick={onCancel} className={btnGhost}>
              Cancel
            </button>
          </DrawerFooter>
        </>
      )}
    </DrawerDivider>
  );
}

function GitHubConnected({
  connectedGithub,
  scanningRepos,
  githubEditing,
  githubState,
  githubError,
  previewRepos,
  selectedRepoNames,
  previouslyConnectedRepos,
  onModify,
  onDisconnect,
  onRescan,
  onToggleRepo,
  onSaveEdit,
  onCancelEdit,
}: {
  connectedGithub: { username: string; repos: GitHubRepo[] };
  scanningRepos: Record<string, number>;
  githubEditing: boolean;
  githubState: GithubState;
  githubError: string | null;
  previewRepos: GitHubRepo[] | null;
  selectedRepoNames: Set<string>;
  previouslyConnectedRepos: Set<string>;
  onModify: () => void;
  onDisconnect: () => void;
  onRescan: (name: string) => void;
  onToggleRepo: (name: string) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
}) {
  const saving = githubState === 'saving';
  const fetching = githubState === 'fetching';
  const removing = githubState === 'removing';

  if (githubEditing) {
    const added = [...selectedRepoNames].filter((n) => !previouslyConnectedRepos.has(n));
    const removed = [...previouslyConnectedRepos].filter((n) => !selectedRepoNames.has(n));

    return (
      <DrawerDivider>
        <SectionLabel>Modify connected repositories</SectionLabel>
        {githubError && <ErrorBanner message={githubError} />}

        {!previewRepos ? (
          <div className="flex items-center gap-2 text-sm text-text-tertiary py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading repositories…
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-1 mb-4 max-h-[260px] overflow-y-auto">
              {previewRepos.map((repo) => (
                <label
                  key={repo.name}
                  className="flex items-center gap-3 px-2.5 py-2 rounded-lg hover:bg-surface-base cursor-pointer transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={selectedRepoNames.has(repo.name)}
                    onChange={() => onToggleRepo(repo.name)}
                    className="h-3.5 w-3.5 rounded accent-zinc-900 dark:accent-white"
                  />
                  <span className="w-4 h-4 flex-none text-text-tertiary"><GitHubRepoIcon /></span>
                  <span className="flex-1 min-w-0 text-sm text-text-primary truncate">{repo.name}</span>
                  {previouslyConnectedRepos.has(repo.name) && !selectedRepoNames.has(repo.name) && (
                    <span className="text-xs text-red-500 flex-none">Will remove</span>
                  )}
                  {!previouslyConnectedRepos.has(repo.name) && selectedRepoNames.has(repo.name) && (
                    <span className="text-xs text-emerald-500 flex-none">New</span>
                  )}
                </label>
              ))}
            </div>

            {(added.length > 0 || removed.length > 0) && (
              <p className="text-xs text-text-tertiary mb-3">
                {added.length > 0 && `+${added.length} to add`}
                {added.length > 0 && removed.length > 0 && ' · '}
                {removed.length > 0 && `${removed.length} to remove`}
              </p>
            )}

            <DrawerFooter>
              <button
                type="button"
                onClick={onSaveEdit}
                disabled={selectedRepoNames.size === 0 || saving || fetching}
                className={btnPrimary}
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                {saving ? 'Saving…' : 'Save changes'}
              </button>
              <button type="button" onClick={onCancelEdit} className={btnGhost} disabled={saving}>
                Cancel
              </button>
            </DrawerFooter>
          </>
        )}
      </DrawerDivider>
    );
  }

  const syncedAt = connectedGithub.repos[0]?.scanned_at ?? null;

  return (
    <DrawerDivider>
      <SectionLabel>Connected repositories</SectionLabel>
      <div className="mb-3">
        {connectedGithub.repos.map((repo) => (
          <ConnectedItem
            key={repo.name}
            icon={<GitHubRepoIcon />}
            name={repo.name}
            scanning={!!scanningRepos[repo.name]}
            onRemove={() => onRescan(repo.name)}
          />
        ))}
        <button type="button" onClick={onModify} className={cn(btnSubtle, 'mt-1')}>
          <Plus className="h-3 w-3" />
          Add or modify repositories
        </button>
      </div>

      <DrawerFooter left={syncedAt ? `Synced ${formatRelativeDate(syncedAt) ?? ''}` : undefined}>
        <button type="button" onClick={onDisconnect} disabled={removing} className={btnDanger}>
          {removing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
          {removing ? 'Removing…' : 'Disconnect'}
        </button>
      </DrawerFooter>
    </DrawerDivider>
  );
}

function GitHubError({
  error,
  connectedGithub,
  onReconnect,
  onDisconnect,
}: {
  error: string;
  connectedGithub: { username: string; repos: GitHubRepo[] } | null;
  onReconnect: () => void;
  onDisconnect: () => void;
}) {
  return (
    <DrawerDivider>
      <ErrorBanner message={error} />
      {connectedGithub && connectedGithub.repos.length > 0 && (
        <div className="mb-4">
          <SectionLabel>Previously connected</SectionLabel>
          {connectedGithub.repos.map((repo) => (
            <ConnectedItem key={repo.name} icon={<GitHubRepoIcon />} name={repo.name} />
          ))}
        </div>
      )}
      <DrawerFooter>
        <button type="button" onClick={onReconnect} className={btnPrimary}>Reconnect</button>
        <button type="button" onClick={onDisconnect} className={btnDanger}>Disconnect</button>
      </DrawerFooter>
    </DrawerDivider>
  );
}

/* ─── GitHub App expanded content ───────────────────────────────────────── */

function GitHubAppIdle({ installUrl }: { installUrl: string | null }) {
  return (
    <DrawerDivider>
      <SectionLabel>Silent capture</SectionLabel>
      <p className="text-sm text-text-secondary mb-4">
        Install the Tailord GitHub App to automatically capture experience from merged pull requests.
        Your repos are scanned on connection; ongoing capture adds depth over time.
      </p>
      {installUrl ? (
        <a href={installUrl} className={btnPrimary}>
          <SiGithub className="h-3.5 w-3.5" />
          Install GitHub App
        </a>
      ) : (
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-base border border-border-subtle text-xs text-text-tertiary font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-none" />
          Not configured
        </div>
      )}
    </DrawerDivider>
  );
}

function GitHubAppConnected({
  login,
  disconnecting,
  onDisconnect,
}: {
  login: string;
  disconnecting: boolean;
  onDisconnect: () => void;
}) {
  return (
    <DrawerDivider>
      <SectionLabel>Silent capture</SectionLabel>
      <ConnectedItem
        icon={<SiGithub className="h-full w-full" />}
        name={`@${login}`}
        sub="Capture active"
      />
      <DrawerFooter>
        <button type="button" onClick={onDisconnect} disabled={disconnecting} className={btnDanger}>
          {disconnecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
          {disconnecting ? 'Disconnecting…' : 'Disconnect App'}
        </button>
      </DrawerFooter>
    </DrawerDivider>
  );
}

/* ─── Planned source expanded content ───────────────────────────────────── */

function PlannedSourceContent({
  points,
  permission,
  note,
}: {
  points: string[];
  permission: string;
  note?: string;
}) {
  return (
    <DrawerDivider>
      <ExpandInfo points={points} permission={permission} />
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-base border border-border-subtle text-xs text-text-tertiary font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-none" />
        Coming soon
      </div>
      {note && <p className="text-xs text-text-tertiary mt-2">{note}</p>}
    </DrawerDivider>
  );
}

/* ─── Main component ─────────────────────────────────────────────────────── */

export function SourcesManager() {
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
  const [githubAppLogin, setGithubAppLogin] = useState<string | null>(null);
  const [githubAppDisconnecting, setGithubAppDisconnecting] = useState(false);

  const [confirmDialog, setConfirmDialog] = useState<ConfirmAction | null>(null);
  const [previouslyConnectedRepos, setPreviouslyConnectedRepos] = useState<Set<string>>(new Set());
  const [rescanConfirm, setRescanConfirm] = useState<string | null>(null);

  const [scanningRepos, setScanningRepos] = useState<Record<string, number>>({});
  const scanningReposRef = useRef<Record<string, number>>({});
  const scanPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const suggestionToastShownRef = useRef(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingReplaceDestructive = useRef(false);

  // Which card is open (null = none)
  const [openCard, setOpenCard] = useState<string | null>(null);
  const toggleCard = (key: string) => setOpenCard((k) => (k === key ? null : key));

  // Handle post-install redirect from GitHub App OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const url = new URL(window.location.href);

    if (params.get('github_connected') === 'true') {
      toast.success('GitHub App connected — your repos are being scanned.');
      url.searchParams.delete('github_connected');
      window.history.replaceState({}, '', url.toString());
      setOpenCard('github');
    } else if (params.get('github_error')) {
      const reason = params.get('github_error');
      const msg = reason === 'missing_params'
        ? 'GitHub App installation failed — missing parameters from GitHub redirect.'
        : 'GitHub App connection failed. Please try again.';
      toastError(msg);
      url.searchParams.delete('github_error');
      window.history.replaceState({}, '', url.toString());
      setOpenCard('github');
    }
  }, []);

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

  const updateScanningRepos = useCallback((fn: (prev: Record<string, number>) => Record<string, number>) => {
    scanningReposRef.current = fn(scanningReposRef.current);
    setScanningRepos({ ...scanningReposRef.current });
  }, []);

  const stopScanPolling = useCallback(() => {
    if (scanPollRef.current) { clearInterval(scanPollRef.current); scanPollRef.current = null; }
  }, []);

  const checkAndShowSuggestionToast = useCallback(async () => {
    if (suggestionToastShownRef.current) return;
    try {
      const res = await fetch('/api/experience/groups');
      if (!res.ok) return;
      const groups: ExperienceGroup[] = await res.json();
      const pending = groups.filter(
        (g) => g.group_type === 'repository' && g.suggested_parent_id && !g.parent_group_id
      );
      if (pending.length > 0) {
        suggestionToastShownRef.current = true;
        toast(
          `${pending.length} GitHub repo${pending.length > 1 ? 's' : ''} may be related to your work experience.`,
          { description: 'Use the ⋯ menu on a repo header to associate it with a role.', duration: 8000 },
        );
      }
    } catch { /* ignore */ }
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
          if (Object.keys(scanningReposRef.current).length === 0) stopScanPolling();
          checkAndShowSuggestionToast();
        }
      } catch { /* ignore */ }
    }, 3000);
  }, [stopScanPolling, updateScanningRepos, checkAndShowSuggestionToast]);

  useEffect(() => {
    async function loadInitialState() {
      try {
        const res = await fetch('/api/experience');
        if (!res.ok) { setUploadState({ phase: 'idle' }); return; }
        const record: ExperienceRecord | null = await res.json();
        if (!record) { setUploadState({ phase: 'idle' }); return; }

        if (record.github_app_login) {
          setGithubAppLogin(record.github_app_login);
        }

        if (record.github_username) {
          setGithubUrl(record.github_username);
          setConnectedGithub({ username: record.github_username, repos: record.github_repos ?? [] });
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
        } else if (record.status === 'processing' || record.status === 'pending') {
          if (record.last_process_requested_at) {
            const startTs = new Date(record.last_process_requested_at).getTime();
            setStageStartedAt({ [PROCESS_STAGES[0]]: startTs });
            setProcessingStage(PROCESS_STAGES[0]);
          }
          setUploadState({ phase: 'processing', filename: record.filename ?? '', experienceId: record.id ?? '' });
          startPolling();
        } else if (record.status === 'error') {
          setUploadState({ phase: 'error', message: record.error_message ?? 'Processing failed' });
        } else {
          setUploadState({ phase: 'idle' });
        }
      } catch {
        setUploadState({ phase: 'idle' });
      }
    }

    loadInitialState();
    return () => { stopPolling(); stopScanPolling(); };
  }, [startPolling, stopPolling, stopScanPolling, startScanPolling, updateScanningRepos]);

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
      const destructive = pendingReplaceDestructive.current;
      pendingReplaceDestructive.current = false;
      const processRes = await fetch('/api/experience/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ storage_key, experience_id, destructive }),
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
              if (record.github_username) {
                setGithubUrl(record.github_username);
                setConnectedGithub({ username: record.github_username, repos: record.github_repos ?? [] });
              }
              checkAndShowSuggestionToast();
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

  const handleRemove = async (cascade = true) => {
    stopPolling();
    const res = await fetch(`/api/experience?cascade=${cascade}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? `Failed to remove (${res.status})`);
      return;
    }
    setUploadState({ phase: 'idle' });
    setProcessingStage(null);
    setStageStartedAt({});
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleConfirmAction = async (cascade = true) => {
    const action = confirmDialog;
    setConfirmDialog(null);
    if (action === 'resume-remove') await handleRemove(cascade);
    else if (action === 'resume-replace') {
      pendingReplaceDestructive.current = cascade;
      fileInputRef.current?.click();
    }
    else if (action === 'github-remove') await handleGithubRemove(cascade);
    else if (action === 'github-change') await doGithubSave(parseGithubUsername(githubUrl), [...selectedRepoNames], undefined, cascade);
    else if (action === 'github-repos-remove') {
      const added = [...selectedRepoNames].filter((n) => !previouslyConnectedRepos.has(n));
      await doGithubSave(parseGithubUsername(githubUrl), [...selectedRepoNames], added, cascade);
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

  const doGithubSave = async (username: string, repoNames: string[], enrichOnly?: string[], cascade = true) => {
    setGithubState('saving');
    setGithubError(null);
    const payload: Record<string, unknown> = {
      github_username: username,
      selected_repo_names: repoNames,
      cascade_removed_repos: cascade,
    };
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
      if (updated.github_username) {
        setConnectedGithub({ username: updated.github_username, repos: updated.github_repos ?? [] });
      }
      const toScan = enrichOnly ?? repoNames;
      const now = Date.now();
      const scanning: Record<string, number> = {};
      for (const name of toScan) {
        const repo = updated.github_repos?.find((r) => r.name === name);
        if (!repo?.scanned_at || new Date(repo.scanned_at).getTime() < now) scanning[name] = now;
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
    setSelectedRepoNames(preselect ? new Set(preselect) : new Set());
    setGithubState('idle');
  };

  const handleGithubFetch = async (e: React.SyntheticEvent<HTMLFormElement>) => {
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
    setAcknowledged(true);
    await fetchReposForUsername(username, currentRepos);
  };

  const handleGithubConnect = async () => {
    const username = parseGithubUsername(githubUrl);
    if (!username || selectedRepoNames.size === 0 || !acknowledged) return;
    if (githubEditing) {
      const added = [...selectedRepoNames].filter((n) => !previouslyConnectedRepos.has(n));
      const removed = [...previouslyConnectedRepos].filter((n) => !selectedRepoNames.has(n));
      if (removed.length > 0) { setConfirmDialog('github-repos-remove'); return; }
      await doGithubSave(username, [...selectedRepoNames], added.length > 0 ? added : undefined);
      return;
    }
    await doGithubSave(username, [...selectedRepoNames]);
  };

  const toggleRepo = (name: string) => {
    setSelectedRepoNames((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
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
    updateScanningRepos((prev) => ({ ...prev, [repoName]: Date.now() }));
    startScanPolling();
  };

  const handleGithubAppDisconnect = async () => {
    setGithubAppDisconnecting(true);
    const res = await fetch('/api/integrations/github', { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? 'Failed to disconnect GitHub App');
      setGithubAppDisconnecting(false);
      return;
    }
    setGithubAppLogin(null);
    toast.success('GitHub App disconnected');
    setGithubAppDisconnecting(false);
  };

  const handleGithubRemove = async (cascade = true) => {
    setGithubState('removing');
    const res = await fetch(`/api/experience/github?cascade=${cascade}`, { method: 'DELETE' });
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
    if (updated) setUploadState({ phase: 'ready', record: updated });
  };

  /* ─── Derive card state ──────────────────────────────────────────────── */

  const installUrl = process.env.NEXT_PUBLIC_GITHUB_APP_SLUG
    ? `https://github.com/apps/${process.env.NEXT_PUBLIC_GITHUB_APP_SLUG}/installations/new`
    : null;

  const resumeIsConnected =
    uploadState.phase === 'ready' && !!(uploadState.record.filename) ||
    uploadState.phase === 'uploading' ||
    uploadState.phase === 'processing' ||
    uploadState.phase === 'error';

  const resumeStatus: CardStatus = (() => {
    switch (uploadState.phase) {
      case 'uploading':
      case 'processing': return 'processing';
      case 'error': return 'error';
      case 'ready': return uploadState.record.filename ? 'connected' : 'idle';
      default: return 'idle';
    }
  })();

  const githubIsConnected = connectedGithub !== null || githubState === 'saving' || githubAppLogin !== null;
  const githubStatus: CardStatus = (() => {
    if (!connectedGithub && githubAppLogin === null && githubState !== 'saving') return 'idle';
    if (githubState === 'error' && !connectedGithub) return 'error';
    if (githubState === 'saving' || githubState === 'removing' || githubState === 'fetching' || scanIsActive) return 'processing';
    if (githubState === 'error') return 'error';
    return 'connected';
  })();

  const resumeMeta: React.ReactNode = (() => {
    switch (uploadState.phase) {
      case 'loading': return 'Loading…';
      case 'uploading': return `Uploading ${uploadState.filename}…`;
      case 'processing': return (processingStage ? (PROCESS_STAGE_LABELS[processingStage] ?? processingStage) : 'Processing') + '…';
      case 'error': return 'Processing failed';
      case 'ready':
        if (!uploadState.record.filename) return 'Upload a resume to get started';
        return `${uploadState.record.filename}${uploadState.record.processed_at ? ` · Processed ${formatRelativeDate(uploadState.record.processed_at) ?? ''}` : ''}`;
      default: return 'Upload a resume to get started';
    }
  })();

  const githubMeta: React.ReactNode = (() => {
    if (!connectedGithub) {
      if (githubAppLogin) return `@${githubAppLogin} · Capture active`;
      if (githubState === 'fetching') return 'Fetching repositories…';
      if (githubState === 'saving') return 'Connecting…';
      return 'Connect your GitHub profile to extract project signals';
    }
    const repoCount = connectedGithub.repos.length;
    const scanCount = Object.keys(scanningRepos).length;
    if (scanCount > 0) return `${repoCount} ${repoCount === 1 ? 'repository' : 'repositories'} · Scanning ${scanCount}…`;
    const lastSync = connectedGithub.repos
      .map((r) => r.scanned_at)
      .filter(Boolean)
      .sort()
      .reverse()[0];
    return `${repoCount} ${repoCount === 1 ? 'repository' : 'repositories'}${lastSync ? ` · Synced ${formatRelativeDate(lastSync) ?? ''}` : ''}`;
  })();

  /* ─── Groups ─────────────────────────────────────────────────────────── */

  const connectedCount = [resumeIsConnected, githubIsConnected].filter(Boolean).length;
  const availableCount = [!resumeIsConnected, !githubIsConnected].filter(Boolean).length + 6; // +6 for planned sources

  /* ─── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="h-full flex flex-col bg-surface-elevated">

      {/* Hidden file input */}
      <input ref={fileInputRef} type="file" accept=".pdf,.doc,.docx,.txt" className="hidden" onChange={handleFileChange} />

      {/* Topbar */}
      <div className="shrink-0 flex items-center h-12 px-6 bg-surface-elevated">
        <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">Sources</span>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="mx-auto px-6 lg:px-10 pt-12 pb-24 max-w-3xl">

          {/* Page header */}
          <div className="flex items-start justify-between gap-6 mb-1">
            <div>
              <h1 className="text-2xl font-semibold tracking-[-0.02em] text-text-primary">Capture surfaces</h1>
              <p className="mt-1.5 text-sm text-text-secondary max-w-[44ch]">
                Connect the places your work lives. Tailord reads them to build your experience profile — visible in{' '}
                <span className="font-medium text-text-primary">My Experience</span>.
              </p>
            </div>
            <span className="text-sm text-text-tertiary whitespace-nowrap pt-1 tabular-nums">
              <span className="font-semibold text-text-primary">{connectedCount}</span> connected{' · '}{availableCount} available
            </span>
          </div>

          <div className="mt-5 h-px bg-border-subtle" />

          {/* Connected group */}
          {connectedCount > 0 && (
            <>
              <p className="mt-5 mb-3 text-[11px] font-semibold uppercase tracking-widest text-text-tertiary">
                Connected · {connectedCount}
              </p>
              <div className="flex flex-col gap-2.5">

                {resumeIsConnected && (
                  <SourceCard
                    logo={<FileText className="h-5 w-5 text-text-secondary" strokeWidth={1.6} />}
                    name="Resume"
                    status={resumeStatus}
                    meta={resumeMeta}
                    open={openCard === 'resume'}
                    onToggle={() => toggleCard('resume')}
                  >
                    {uploadState.phase === 'ready' && uploadState.record.filename && (
                      <ResumeConnected
                        record={uploadState.record}
                        onReplace={() => setConfirmDialog('resume-replace')}
                        onRemove={() => setConfirmDialog('resume-remove')}
                      />
                    )}
                    {(uploadState.phase === 'uploading' || uploadState.phase === 'processing') && (
                      <ResumeProcessing
                        filename={uploadState.filename}
                        processingStage={processingStage}
                        stageStartedAt={stageStartedAt}
                        onCancel={handleRemove}
                      />
                    )}
                    {uploadState.phase === 'error' && (
                      <ResumeError
                        message={uploadState.message}
                        onRetry={() => fileInputRef.current?.click()}
                        onClear={() => handleRemove(true)}
                      />
                    )}
                  </SourceCard>
                )}

                {githubIsConnected && (
                  <SourceCard
                    logo={<SiGithub className="h-5 w-5 text-text-primary" />}
                    name="GitHub"
                    status={githubStatus}
                    meta={githubMeta}
                    open={openCard === 'github'}
                    onToggle={() => toggleCard('github')}
                  >
                    {githubAppLogin && (
                      <GitHubAppConnected
                        login={githubAppLogin}
                        disconnecting={githubAppDisconnecting}
                        onDisconnect={handleGithubAppDisconnect}
                      />
                    )}
                    {githubStatus === 'error' && githubError ? (
                      <GitHubError
                        error={githubError}
                        connectedGithub={connectedGithub}
                        onReconnect={handleGithubModify}
                        onDisconnect={() => setConfirmDialog('github-remove')}
                      />
                    ) : connectedGithub && (
                      <GitHubConnected
                        connectedGithub={connectedGithub}
                        scanningRepos={scanningRepos}
                        githubEditing={githubEditing}
                        githubState={githubState}
                        githubError={githubError}
                        previewRepos={previewRepos}
                        selectedRepoNames={selectedRepoNames}
                        previouslyConnectedRepos={previouslyConnectedRepos}
                        onModify={handleGithubModify}
                        onDisconnect={() => setConfirmDialog('github-remove')}
                        onRescan={setRescanConfirm}
                        onToggleRepo={toggleRepo}
                        onSaveEdit={handleGithubConnect}
                        onCancelEdit={() => { resetGithubPreview(); setGithubState('idle'); setGithubError(null); setGithubEditing(false); }}
                      />
                    )}
                  </SourceCard>
                )}

              </div>
            </>
          )}

          {/* Available group */}
          <p className="mt-7 mb-3 text-[11px] font-semibold uppercase tracking-widest text-text-tertiary">
            Available · {availableCount}
          </p>
          <div className="flex flex-col gap-2.5">

            {!resumeIsConnected && (
              <SourceCard
                logo={<FileText className="h-5 w-5 text-text-tertiary" strokeWidth={1.6} />}
                name="Resume"
                status="idle"
                meta="Upload a resume to extract roles, skills, and education"
                open={openCard === 'resume'}
                onToggle={() => toggleCard('resume')}
                idle
              >
                <ResumeIdle onUpload={() => { setOpenCard('resume'); fileInputRef.current?.click(); }} />
              </SourceCard>
            )}

            {!githubIsConnected && (
              <SourceCard
                logo={<SiGithub className="h-5 w-5 text-text-tertiary" />}
                name="GitHub"
                status={githubState === 'error' ? 'error' : 'idle'}
                meta="Connect your profile to surface open-source contributions"
                open={openCard === 'github'}
                onToggle={() => toggleCard('github')}
                idle
              >
                <GitHubAppIdle installUrl={installUrl} />
                <GitHubIdle
                  githubUrl={githubUrl}
                  githubState={githubState}
                  githubError={githubError}
                  previewRepos={previewRepos}
                  selectedRepoNames={selectedRepoNames}
                  acknowledged={acknowledged}
                  onUrlChange={(url) => { setGithubUrl(url); setGithubState('idle'); setGithubError(null); }}
                  onFetch={handleGithubFetch}
                  onToggleRepo={toggleRepo}
                  onAcknowledge={setAcknowledged}
                  onConnect={handleGithubConnect}
                  onCancel={() => { resetGithubPreview(); setGithubState('idle'); setGithubError(null); }}
                />
              </SourceCard>
            )}

            {/* Linear — planned */}
            <SourceCard
              logo={<SiLinear className="h-4.5 w-4.5 text-text-tertiary" style={{ width: 18, height: 18 }} />}
              name="Linear"
              status="idle"
              meta="Pull completed issues and projects as experience claims"
              open={openCard === 'linear'}
              onToggle={() => toggleCard('linear')}
              idle
            >
              <PlannedSourceContent
                points={[
                  'Completed issues assigned to you — turned into accomplishment bullets',
                  'Projects and cycles you led or contributed to',
                  'Team context: stack, scope, and scale of work',
                ]}
                permission="Read-only access to your assigned issues — no write permissions required."
                note="Useful for engineers and PMs whose most impactful work lives in Linear rather than GitHub."
              />
            </SourceCard>

            {/* Quick Capture — planned */}
            <SourceCard
              logo={<AlignLeft className="h-5 w-5 text-text-tertiary" strokeWidth={1.6} />}
              name="Quick Capture"
              status="idle"
              meta="Send experience dumps via SMS, Slack, or Discord — claims get staged for review"
              open={openCard === 'quick-capture'}
              onToggle={() => toggleCard('quick-capture')}
              idle
            >
              <PlannedSourceContent
                points={[
                  'Text a memory, narrative, or accomplishment to your Tailord number',
                  'Send a message in Slack or Discord — Tailord stages it as draft claims',
                  'Claims are held for review before being added to your profile',
                ]}
                permission="Messages are processed to extract structured claims and never stored verbatim."
                note="Designed for capturing experience in the moment — right after shipping, a retro, or a performance review."
              />
            </SourceCard>

            {/* SMS — planned */}
            <SourceCard
              logo={<MessageSquare className="h-5 w-5 text-text-tertiary" strokeWidth={1.6} />}
              name="SMS"
              status="idle"
              meta="Text experience dumps to your Tailord number — claims staged for review"
              open={openCard === 'sms'}
              onToggle={() => toggleCard('sms')}
              idle
            >
              <PlannedSourceContent
                points={[
                  'Text any accomplishment, project summary, or work narrative',
                  'Claims are extracted and held in a staging queue for your review',
                  'Approve or discard before anything reaches your profile',
                ]}
                permission="Your number is used only for inbound message routing — no outbound marketing."
                note="Capture experience in the moment: after a retro, a ship, or a performance review conversation."
              />
            </SourceCard>

            {/* Slack — planned */}
            <SourceCard
              logo={<SiSlack className="text-text-tertiary" style={{ width: 18, height: 18 }} />}
              name="Slack"
              status="idle"
              meta="Send messages to the Tailord bot in any workspace"
              open={openCard === 'slack'}
              onToggle={() => toggleCard('slack')}
              idle
            >
              <PlannedSourceContent
                points={[
                  'DM the Tailord bot with any work narrative or accomplishment',
                  'Bot responds with staged claims for you to review and approve',
                  'Works in personal DMs — no channel access required',
                ]}
                permission="Read-only access to direct messages you send to the Tailord bot. No channel history or workspace data."
                note="Pairs well with end-of-sprint retrospectives or after you write a particularly good status update."
              />
            </SourceCard>

            {/* Discord — planned */}
            <SourceCard
              logo={<SiDiscord className="text-text-tertiary" style={{ width: 18, height: 18 }} />}
              name="Discord"
              status="idle"
              meta="DM the Tailord bot to capture and stage experience claims"
              open={openCard === 'discord'}
              onToggle={() => toggleCard('discord')}
              idle
            >
              <PlannedSourceContent
                points={[
                  'DM the Tailord bot on Discord with any work narrative',
                  'Claims are extracted and staged — you approve before they land in your profile',
                  'Works across any server where the bot is installed',
                ]}
                permission="Bot only reads direct messages you initiate. No server message access."
                note="Useful for contributors whose work lives in open-source or community-run Discord servers."
              />
            </SourceCard>

            {/* Browser extension — planned */}
            <SourceCard
              logo={<Globe className="h-5 w-5 text-text-tertiary" strokeWidth={1.6} />}
              name="Browser extension"
              status="idle"
              meta="Capture job postings and context as you browse"
              open={openCard === 'browser-ext'}
              onToggle={() => toggleCard('browser-ext')}
              idle
            >
              <PlannedSourceContent
                points={[
                  'Job postings you view on any job board',
                  'Role requirements and company context — extracted on-page',
                  'Capture triggers a tailoring without leaving your browser',
                ]}
                permission="The extension reads only pages you explicitly activate it on — no background browsing."
                note="Eliminates scraping failures on ATS-heavy job boards that block bots. Supports Ashby, Greenhouse, Lever, and LinkedIn."
              />
            </SourceCard>

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
            <button type="button" onClick={() => setRescanConfirm(null)} className={btnGhost}>Cancel</button>
            <button type="button" onClick={() => { handleRepoRescan(rescanConfirm!); setRescanConfirm(null); }} className={btnPrimary}>
              Re-scan
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cascade confirm dialog */}
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
            <button type="button" onClick={() => setConfirmDialog(null)} className={btnGhost}>Cancel</button>
            {confirmDialog && (
              <>
                <button type="button" onClick={() => handleConfirmAction(false)} className={btnGhost}>
                  {CONFIRM_CONFIGS[confirmDialog].keepLabel}
                </button>
                <button
                  type="button"
                  onClick={() => handleConfirmAction(true)}
                  className="inline-flex items-center justify-center h-9 px-3 rounded-[10px] text-sm font-normal bg-red-600 text-white hover:bg-red-700 transition-colors"
                >
                  {CONFIRM_CONFIGS[confirmDialog].deleteLabel}
                </button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
