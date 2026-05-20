'use client';

import { Loader2, Pencil, X, RefreshCw, GitBranch, ArrowUpRight } from 'lucide-react';
import { LuGithub } from 'react-icons/lu';
import { cn, formatElapsed, formatRelativeDate } from '@/lib/utils';
import { MintButton } from '@/components/ui/MintButton';
import type { GitHubRepo } from '@/types';

/* ─── Types (exported so ExperienceManager can import them) ─────────────── */

export type GithubState = 'idle' | 'fetching' | 'saving' | 'saved' | 'removing' | 'error';

/* ─── Shared button styles ──────────────────────────────────────────────── */

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

/* ─── LiveBadge ──────────────────────────────────────────────────────────── */

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

/* ─── Props ─────────────────────────────────────────────────────────────── */

interface GitHubSectionProps {
  isInitialLoad: boolean;
  connectedGithub: { username: string; repos: GitHubRepo[] } | null;
  githubEditing: boolean;
  githubUrl: string;
  githubState: GithubState;
  githubError: string | null;
  previewRepos: GitHubRepo[] | null;
  selectedRepoNames: Set<string>;
  acknowledged: boolean;
  previouslyConnectedRepos: Set<string>;
  scanningRepos: Record<string, number>;
  readOnly?: boolean;
  onGithubUrlChange: (url: string) => void;
  onGithubFetch: (e: React.FormEvent<HTMLFormElement>) => void;
  onGithubConnect: () => void;
  onGithubModify: () => void;
  onDisconnectRequest: () => void;
  onToggleRepo: (name: string) => void;
  onAcknowledgeChange: (val: boolean) => void;
  onCancelEdit: () => void;
  onRescanRequest: (name: string) => void;
  /** Parse github.com/username or bare username to just the username */
  parseUsername: (input: string) => string;
}

/* ─── Component ─────────────────────────────────────────────────────────── */

export function GitHubSection({
  isInitialLoad,
  connectedGithub,
  githubEditing,
  githubUrl,
  githubState,
  githubError,
  previewRepos,
  selectedRepoNames,
  acknowledged,
  previouslyConnectedRepos,
  scanningRepos,
  readOnly,
  onGithubUrlChange,
  onGithubFetch,
  onGithubConnect,
  onGithubModify,
  onDisconnectRequest,
  onToggleRepo,
  onAcknowledgeChange,
  onCancelEdit,
  onRescanRequest,
  parseUsername,
}: GitHubSectionProps) {
  const githubConnected = !!connectedGithub;

  const renderControls = () => {
    // ── Connected (view mode) ────────────────────────────────────────────────
    if (githubConnected && !githubEditing && connectedGithub) {
      const { repos, username } = connectedGithub;
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
                        onClick={() => onRescanRequest(r.name)}
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
            <MintButton icon={<Pencil />} label="Modify" onClick={onGithubModify} disabled={readOnly} />
            <MintButton
              icon={githubState === 'removing' ? <Loader2 className="animate-spin" /> : <X />}
              label="Disconnect"
              onClick={onDisconnectRequest}
              danger
              disabled={readOnly || githubState === 'removing'}
            />
          </div>
        </div>
      );
    }

    // ── Step 2: repo selection ───────────────────────────────────────────────
    if (previewRepos !== null || githubState === 'fetching') {
      const previewUsername = parseUsername(githubUrl);
      const hasNoChange =
        githubEditing &&
        selectedRepoNames.size === previouslyConnectedRepos.size &&
        [...selectedRepoNames].every((n) => previouslyConnectedRepos.has(n));
      const connectDisabled =
        selectedRepoNames.size === 0 ||
        !acknowledged ||
        githubState === 'saving' ||
        githubState === 'fetching' ||
        hasNoChange;

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
                    <Toggle checked={selectedRepoNames.has(r.name)} onChange={() => onToggleRepo(r.name)} />
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
              <input
                type="checkbox"
                checked={acknowledged}
                onChange={(e) => onAcknowledgeChange(e.target.checked)}
                className="h-3.5 w-3.5 my-1 flex-shrink-0 accent-brand-primary cursor-pointer"
              />
              <span className="text-xs text-text-secondary leading-relaxed">
                I confirm the selected repositories are representative of my engineering work. For repos with multiple contributors, Tailord treats the codebase as indicative of my experience.
              </span>
            </label>
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onGithubConnect}
              disabled={readOnly || connectDisabled}
              className={saveBtnCls}
            >
              {githubState === 'saving'
                ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Connecting…</>
                : `Connect (${selectedRepoNames.size} repo${selectedRepoNames.size !== 1 ? 's' : ''})`}
            </button>
            <button type="button" onClick={onCancelEdit} className={outlineBtnCls}>
              Cancel
            </button>
          </div>
        </div>
      );
    }

    // ── Step 1: username input ───────────────────────────────────────────────
    return (
      <form onSubmit={readOnly ? (e) => e.preventDefault() : onGithubFetch} className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-xs">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <LuGithub className="h-4 w-4 text-text-tertiary" />
            </div>
            <input
              type="text"
              value={githubUrl}
              onChange={(e) => { onGithubUrlChange(e.target.value); }}
              placeholder="github.com/username or username"
              disabled={readOnly}
              className={cn(
                'w-full h-10 rounded-xl border border-border-default bg-surface-elevated px-3 pl-9 text-sm text-text-primary ' +
                'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
                'hover:border-border-strong hover:bg-surface-base ' +
                'focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] ' +
                'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)] disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            />
          </div>
          <button type="submit" disabled={readOnly || !githubUrl.trim()} className={saveBtnCls}>
            Connect
          </button>
        </div>
        {githubState === 'error' && githubError && <p className="text-xs text-error">{githubError}</p>}
        {githubEditing && (
          <button type="button" onClick={onCancelEdit} className={cn(outlineBtnCls, 'w-fit')}>Cancel</button>
        )}
      </form>
    );
  };

  return (
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
      {!isInitialLoad && renderControls()}
    </div>
  );
}
