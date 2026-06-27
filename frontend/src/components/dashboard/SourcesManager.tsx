'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  ChevronDown, FileText, AlignLeft, Globe, Upload,
  Loader2, AlertCircle, X, RefreshCw, Check, Trash2, MessageSquare, ExternalLink,
} from 'lucide-react';
import { SiGithub, SiLinear, SiSlack, SiDiscord } from 'react-icons/si';
import { toast } from 'sonner';
import { cn, toastError, formatRelativeDate, formatElapsed } from '@/lib/utils';
import type { ExperienceRecord } from '@/types';
import type { UploadPhase } from '@/components/dashboard/ResumeUploadSection';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';

/* ─── Types ─────────────────────────────────────────────────────────────── */

interface GitHubRepoInfo {
  name: string;
  full_name: string;
  private: boolean;
  default_branch: string;
}
interface GitHubRepoConfig {
  enabled: boolean;
  pr_capture: boolean;
  last_webhook_at: string | null;
  last_scanned_at: string | null;
}
interface GitHubAppInfo {
  connected: boolean;
  login: string | null;
  install_url: string | null;
  installation_id: string | null;
  repos: GitHubRepoInfo[];
  watch_branch: string | null;
  repo_config: Record<string, GitHubRepoConfig>;
}

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
    title: 'Disconnect GitHub',
    description: 'What should happen to the experience claims and groups captured from your GitHub repos and pull requests?',
    keepLabel: 'Keep claims',
    deleteLabel: 'Delete everything',
  },
} as const;

type ConfirmAction = keyof typeof CONFIRM_CONFIGS;
type CardStatus = 'connected' | 'processing' | 'error' | 'idle';

const PROCESS_STAGES = ['extracting', 'analyzing'] as const;
const PROCESS_STAGE_LABELS: Record<string, string> = { extracting: 'Extracting text', analyzing: 'Analyzing profile' };

/* ─── Shared styles ─────────────────────────────────────────────────────── */

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

function GitHubIdle({ installUrl }: { installUrl: string | null }) {
  return (
    <DrawerDivider>
      <ExpandInfo
        points={[
          'Repository descriptions, languages, and README content',
          'Experience claims automatically captured from merged pull requests',
          'Private repos included — scoped to what you grant during installation',
        ]}
        permission="Read-only access to repos you explicitly grant during GitHub App installation."
      />
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

function PrCaptureToggle({ enabled, onChange }: { enabled: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={() => onChange(!enabled)}
      title={enabled ? 'PR capture on — click to disable' : 'PR capture off — click to enable'}
      className={cn(
        'relative flex-none w-7 h-4 rounded-full transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent',
        enabled ? 'bg-emerald-500' : 'bg-border-strong',
      )}
    >
      <span className={cn(
        'absolute top-0.5 w-3 h-3 rounded-full bg-white shadow-sm transition-transform duration-150',
        enabled ? 'translate-x-[14px]' : 'translate-x-0.5',
      )} />
    </button>
  );
}

function GitHubConnected({
  login,
  appInfo,
  appInfoLoading,
  refreshingRepos,
  disconnecting,
  onDisconnect,
  onRepoEnable,
  onRepoDisable,
  onRepoPrCapture,
  onRepoRescan,
  onRefreshRepos,
}: {
  login: string;
  appInfo: GitHubAppInfo | null;
  appInfoLoading: boolean;
  refreshingRepos: boolean;
  disconnecting: boolean;
  onDisconnect: () => void;
  onRepoEnable: (fullName: string) => Promise<void>;
  onRepoDisable: (repo: { fullName: string; name: string }) => void;
  onRepoPrCapture: (fullName: string, enabled: boolean) => Promise<void>;
  onRepoRescan: (fullName: string) => Promise<void>;
  onRefreshRepos: () => void;
}) {
  const [enablingRepo, setEnablingRepo] = useState<string | null>(null);
  const [scanningRepo, setScanningRepo] = useState<string | null>(null);

  const handleEnable = async (fullName: string) => {
    setEnablingRepo(fullName);
    try { await onRepoEnable(fullName); }
    finally { setEnablingRepo(null); }
  };

  const handleRescan = async (fullName: string) => {
    setScanningRepo(fullName);
    try { await onRepoRescan(fullName); }
    finally { setScanningRepo(null); }
  };

  const enabled = appInfo?.repos.filter((r) => appInfo.repo_config[r.full_name]?.enabled) ?? [];
  const available = appInfo?.repos.filter((r) => !appInfo.repo_config[r.full_name]?.enabled) ?? [];
  const manageUrl = appInfo?.installation_id
    ? `https://github.com/settings/installations/${appInfo.installation_id}`
    : null;

  return (
    <DrawerDivider>
      <ConnectedItem
        icon={<SiGithub className="h-full w-full" />}
        name={`@${login}`}
        sub="GitHub App connected"
      />

      {/* Repos */}
      <div className="mt-4">
        <div className="flex items-center mb-2.5">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-text-tertiary flex-1">Repositories</span>
          <button
            type="button"
            disabled={refreshingRepos}
            onClick={onRefreshRepos}
            title="Refresh repo list from GitHub"
            className={btnSubtle}
          >
            {refreshingRepos ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </button>
        </div>

        {appInfoLoading ? (
          <div className="flex items-center gap-1.5 text-xs text-text-tertiary py-1">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading…
          </div>
        ) : appInfo && appInfo.repos.length === 0 ? (
          <p className="text-xs text-text-tertiary">
            No repos found.{' '}
            <button type="button" onClick={onRefreshRepos} className="underline hover:text-text-secondary transition-colors">Refresh</button>
            {manageUrl && <> or <a href={manageUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-text-secondary transition-colors">grant access on GitHub</a></>}.
          </p>
        ) : (
          <div className="space-y-3">
            {/* Enabled repos */}
            {enabled.length > 0 && (
              <div>
                <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide mb-1 px-0.5">Enabled</p>
                <div className="divide-y divide-border-subtle border border-border-subtle rounded-xl overflow-hidden">
                  {enabled.map((repo) => {
                    const cfg = appInfo!.repo_config[repo.full_name];
                    const prCapture = cfg?.pr_capture !== false; // default true
                    const isScanning = scanningRepo === repo.full_name;
                    return (
                      <div key={repo.full_name} className="px-3 py-2.5">
                        <div className="flex items-center gap-2.5">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <span className="text-sm text-text-primary truncate">{repo.name}</span>
                              <span className="text-[11px] font-mono text-text-disabled flex-none">{repo.default_branch}</span>
                            </div>
                            <p className="text-xs text-text-tertiary">
                              {repo.private ? 'Private' : 'Public'}
                              {cfg?.last_webhook_at ? ` · Last PR ${formatRelativeDate(cfg.last_webhook_at) ?? ''}` : ''}
                            </p>
                          </div>
                          {/* Rescan */}
                          <button
                            type="button"
                            disabled={isScanning}
                            onClick={() => handleRescan(repo.full_name)}
                            title="Rescan repo content"
                            className={cn(btnSubtle, 'flex-none')}
                          >
                            {isScanning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                          </button>
                          {/* Disable */}
                          <button
                            type="button"
                            onClick={() => onRepoDisable({ fullName: repo.full_name, name: repo.name })}
                            className={cn(btnSubtle, 'text-text-tertiary hover:text-error hover:bg-error-bg flex-none')}
                            title={`Disable ${repo.name}`}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        {/* PR capture toggle */}
                        <div className="flex items-center gap-2 mt-2 pl-0.5">
                          <PrCaptureToggle enabled={prCapture} onChange={(v) => onRepoPrCapture(repo.full_name, v)} />
                          <span className="text-xs text-text-tertiary">PR capture</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Available repos */}
            {available.length > 0 && (
              <div>
                <p className="text-[11px] font-medium text-text-tertiary uppercase tracking-wide mb-1 px-0.5">Available</p>
                <div className="divide-y divide-border-subtle border border-border-subtle rounded-xl overflow-hidden">
                  {available.map((repo) => {
                    const isEnabling = enablingRepo === repo.full_name;
                    return (
                      <div key={repo.full_name} className="flex items-center gap-2.5 px-3 py-2.5">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className="text-sm text-text-secondary truncate">{repo.name}</span>
                            <span className="text-[11px] font-mono text-text-disabled flex-none">{repo.default_branch}</span>
                          </div>
                          <p className="text-xs text-text-tertiary">{repo.private ? 'Private' : 'Public'}</p>
                        </div>
                        <button
                          type="button"
                          disabled={isEnabling}
                          onClick={() => handleEnable(repo.full_name)}
                          className={cn(
                            'inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-lg transition-colors flex-none',
                            'bg-surface-base border border-border-default text-text-secondary',
                            'hover:border-border-strong hover:text-text-primary disabled:opacity-50',
                          )}
                        >
                          {isEnabling ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Enable'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <DrawerFooter left={
        manageUrl ? (
          <a
            href={manageUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-text-link hover:underline"
          >
            Add repos on GitHub
            <ExternalLink className="h-3 w-3" />
          </a>
        ) : undefined
      }>
        <button type="button" onClick={onDisconnect} disabled={disconnecting} className={btnDanger}>
          {disconnecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
          {disconnecting ? 'Disconnecting…' : 'Disconnect'}
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
  const [processingStage, setProcessingStage] = useState<string | null>(null);
  const [stageStartedAt, setStageStartedAt] = useState<Record<string, number>>({});
  const [, setTick] = useState(0);

  const [githubLogin, setGithubLogin] = useState<string | null>(null);
  const [githubDisconnecting, setGithubDisconnecting] = useState(false);
  const [githubAppInfo, setGithubAppInfo] = useState<GitHubAppInfo | null>(null);
  const [githubAppInfoLoading, setGithubAppInfoLoading] = useState(false);
  const [refreshingRepos, setRefreshingRepos] = useState(false);
  const [repoDisableTarget, setRepoDisableTarget] = useState<{ fullName: string; name: string } | null>(null);

  const [confirmDialog, setConfirmDialog] = useState<ConfirmAction | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingReplaceDestructive = useRef(false);

  // Which card is open (null = none)
  const [openCard, setOpenCard] = useState<string | null>(null);
  const toggleCard = (key: string) => setOpenCard((k) => (k === key ? null : key));

  // Handle post-install redirect from GitHub App callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const url = new URL(window.location.href);

    if (params.get('github_connected') === 'true') {
      toast.success('GitHub connected — your repos are being scanned.');
      url.searchParams.delete('github_connected');
      window.history.replaceState({}, '', url.toString());
      setOpenCard('github');
    } else if (params.get('github_error')) {
      const reason = params.get('github_error');
      const msg = reason === 'missing_params'
        ? 'GitHub connection failed — missing parameters from redirect.'
        : 'GitHub connection failed. Please try again.';
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

  const fetchGithubAppInfo = useCallback(async () => {
    setGithubAppInfoLoading(true);
    try {
      const res = await fetch('/api/integrations/github/app-info');
      if (res.ok) {
        const data: GitHubAppInfo = await res.json();
        setGithubAppInfo(data);
      }
    } catch { /* ignore */ }
    finally {
      setGithubAppInfoLoading(false);
    }
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
        if (!res.ok) { setUploadState({ phase: 'idle' }); return; }
        const record: ExperienceRecord | null = await res.json();
        if (!record) { setUploadState({ phase: 'idle' }); return; }

        if (record.github_app_login) {
          setGithubLogin(record.github_app_login);
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
    return () => { stopPolling(); };
  }, [startPolling, stopPolling]);

  // Fetch per-repo config when the connected GitHub card is opened
  useEffect(() => {
    if (openCard === 'github' && githubLogin !== null) {
      fetchGithubAppInfo();
    }
  }, [openCard, githubLogin, fetchGithubAppInfo]);

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
    else if (action === 'github-remove') await doGithubDisconnect(cascade);
  };

  const patchRepoConfig = useCallback(async (payload: Record<string, unknown>) => {
    const res = await fetch('/api/integrations/github/config', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Failed to update repo');
    }
  }, []);

  const handleRepoEnable = useCallback(async (fullName: string) => {
    await patchRepoConfig({ repo_full_name: fullName, enabled: true });
    setGithubAppInfo((prev) => {
      if (!prev) return prev;
      const existing = prev.repo_config[fullName] ?? { enabled: false, pr_capture: true, last_webhook_at: null, last_scanned_at: null };
      return { ...prev, repo_config: { ...prev.repo_config, [fullName]: { ...existing, enabled: true } } };
    });
  }, [patchRepoConfig]);

  const handleRepoPrCapture = useCallback(async (fullName: string, prCapture: boolean) => {
    await patchRepoConfig({ repo_full_name: fullName, pr_capture: prCapture });
    setGithubAppInfo((prev) => {
      if (!prev) return prev;
      const existing = prev.repo_config[fullName] ?? { enabled: true, pr_capture: true, last_webhook_at: null, last_scanned_at: null };
      return { ...prev, repo_config: { ...prev.repo_config, [fullName]: { ...existing, pr_capture: prCapture } } };
    });
  }, [patchRepoConfig]);

  const handleRepoRescan = useCallback(async (fullName: string) => {
    const res = await fetch('/api/integrations/github/scan-repo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_full_name: fullName }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Failed to trigger rescan');
    }
    toast.success('Scan started — claims will appear shortly');
  }, []);

  const handleRepoDisableConfirm = async (deleteClaims: boolean) => {
    const target = repoDisableTarget;
    setRepoDisableTarget(null);
    if (!target) return;
    try {
      await patchRepoConfig({ repo_full_name: target.fullName, enabled: false, delete_claims: deleteClaims });
      setGithubAppInfo((prev) => {
        if (!prev) return prev;
        const existing = prev.repo_config[target.fullName] ?? { enabled: true, pr_capture: true, last_webhook_at: null, last_scanned_at: null };
        return { ...prev, repo_config: { ...prev.repo_config, [target.fullName]: { ...existing, enabled: false } } };
      });
      toast.success(`${target.name} disabled`);
    } catch (e) {
      toastError(e instanceof Error ? e.message : 'Failed to disable repo');
    }
  };

  const handleRefreshRepos = useCallback(async () => {
    setRefreshingRepos(true);
    try {
      const res = await fetch('/api/integrations/github/refresh-repos', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Failed to refresh repos');
      }
      const repos: GitHubRepoInfo[] = await res.json();
      setGithubAppInfo((prev) => prev ? { ...prev, repos } : prev);
      toast.success('Repos refreshed');
    } catch (e) {
      toastError(e instanceof Error ? e.message : 'Failed to refresh repos');
    } finally {
      setRefreshingRepos(false);
    }
  }, []);

  const doGithubDisconnect = async (cascade = true) => {
    setGithubDisconnecting(true);
    const res = await fetch(`/api/integrations/github?cascade=${cascade}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? 'Failed to disconnect GitHub');
      setGithubDisconnecting(false);
      return;
    }
    setGithubLogin(null);
    setGithubAppInfo(null);
    toast.success('GitHub disconnected');
    setGithubDisconnecting(false);
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

  const githubIsConnected = githubLogin !== null;
  const githubStatus: CardStatus = githubIsConnected ? 'connected' : 'idle';

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

  const githubMeta: React.ReactNode = githubLogin
    ? `@${githubLogin} · Capture active`
    : 'Install the GitHub App to capture experience from pull requests';

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
                    <GitHubConnected
                      login={githubLogin!}
                      appInfo={githubAppInfo}
                      appInfoLoading={githubAppInfoLoading}
                      refreshingRepos={refreshingRepos}
                      disconnecting={githubDisconnecting}
                      onDisconnect={() => setConfirmDialog('github-remove')}
                      onRepoEnable={handleRepoEnable}
                      onRepoDisable={setRepoDisableTarget}
                      onRepoPrCapture={handleRepoPrCapture}
                      onRepoRescan={handleRepoRescan}
                      onRefreshRepos={handleRefreshRepos}
                    />
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
                status="idle"
                meta="Install the GitHub App to capture experience from pull requests"
                open={openCard === 'github'}
                onToggle={() => toggleCard('github')}
                idle
              >
                <GitHubIdle installUrl={installUrl} />
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

      {/* Per-repo disable dialog */}
      <Dialog open={repoDisableTarget !== null} onOpenChange={(o) => !o && setRepoDisableTarget(null)}>
        <DialogContent className="max-w-sm bg-surface-elevated border-border-subtle rounded-2xl">
          <DialogHeader>
            <DialogTitle className="text-sm font-medium text-text-primary">
              Disable {repoDisableTarget?.name}?
            </DialogTitle>
            <DialogDescription className="text-sm text-text-secondary">
              This repo will no longer contribute to your experience. What should happen to the claims already captured from it?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-row justify-end gap-2 sm:gap-2">
            <button type="button" onClick={() => setRepoDisableTarget(null)} className={btnGhost}>Cancel</button>
            <button type="button" onClick={() => handleRepoDisableConfirm(false)} className={btnGhost}>Keep claims</button>
            <button
              type="button"
              onClick={() => handleRepoDisableConfirm(true)}
              className="inline-flex items-center justify-center h-9 px-3 rounded-[10px] text-sm font-normal bg-red-600 text-white hover:bg-red-700 transition-colors"
            >
              Delete claims
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
