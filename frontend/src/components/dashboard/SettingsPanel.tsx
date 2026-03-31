'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useTheme } from '@/components/ThemeProvider';
import { Moon, Sun, LogOut, Copy, CheckCircle2, Loader2, TriangleAlert } from 'lucide-react';
import { FiGithub } from 'react-icons/fi';
import { SiNotion } from 'react-icons/si';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useSearchParams } from 'next/navigation';
import { cn } from '@/lib/utils';

const _USERNAME_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const _RESERVED = new Set([
  'dashboard', 'admin', 'api', 'settings', 'login', 'register',
  'u', 't', 'auth', 'notion', 'help', 'about', 'pricing', 'terms',
  'privacy', 'careers', 'blog', 'tailord', 'me', 'public',
]);

/* ─── Shared input style ────────────────────────────────────────────────── */

const inputCls =
  'w-full h-10 rounded-xl border border-border-default bg-surface-elevated px-3 text-sm text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
  'hover:border-border-strong hover:bg-surface-base ' +
  'focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)]';

/* ─── Primary (save) button ─────────────────────────────────────────────── */

const saveBtnCls =
  'inline-flex items-center justify-center h-9 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] ' +
  'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 ' +
  'hover:opacity-90 transition-opacity ' +
  'disabled:bg-surface-base dark:disabled:bg-surface-overlay disabled:text-text-disabled ' +
  'disabled:cursor-not-allowed disabled:hover:opacity-100';

/* ─── Outline button ────────────────────────────────────────────────────── */

const outlineBtnCls =
  'inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] ' +
  'border border-border-default bg-surface-elevated text-text-secondary ' +
  'hover:bg-surface-base hover:border-border-strong hover:text-text-primary ' +
  'transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

/* ─── Section row layout ────────────────────────────────────────────────── */

function SettingRow({
  title,
  description,
  danger = false,
  children,
}: {
  title: string;
  description?: string;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="py-8 grid grid-cols-1 lg:grid-cols-8 gap-x-12 gap-y-4">
      <div className="lg:col-span-3 flex flex-col gap-1">
        <h2 className={cn('text-sm font-medium', danger ? 'text-red-600' : 'text-text-primary')}>
          {title}
        </h2>
        {description && (
          <p className="text-sm text-text-secondary">{description}</p>
        )}
      </div>
      <div className="lg:col-span-5">{children}</div>
    </div>
  );
}

/* ─── Save status text ──────────────────────────────────────────────────── */

function SaveStatus({ status }: { status: 'idle' | 'saved' | 'error' }) {
  if (status === 'saved') return <span className="text-sm text-success">Saved</span>;
  if (status === 'error') return <span className="text-sm text-error">Failed to save</span>;
  return null;
}

/* ─── Card box ──────────────────────────────────────────────────────────── */

function CardBox({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-3 rounded-2xl bg-surface-base p-4 text-sm', className)}>
      {children}
    </div>
  );
}

/* ─── Integration row ───────────────────────────────────────────────────── */

function ConnectedBadge() {
  return (
    <span className="inline-flex items-center gap-[3px] py-0.5 pl-1.5 pr-1.5 text-xs font-medium rounded-md bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400">
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 18 18" fill="currentColor" stroke="none" aria-hidden="true">
        <path d="M9 1C4.589 1 1 4.589 1 9C1 13.411 4.589 17 9 17C13.411 17 17 13.411 17 9C17 4.589 13.411 1 9 1ZM12.843 6.708L8.593 12.208C8.457 12.384 8.25 12.491 8.028 12.499C8.018 12.499 8.009 12.499 8 12.499C7.788 12.499 7.585 12.409 7.442 12.251L5.192 9.751C4.915 9.443 4.94 8.969 5.248 8.691C5.557 8.415 6.029 8.439 6.308 8.747L7.956 10.579L11.657 5.79C11.91 5.462 12.382 5.402 12.709 5.655C13.037 5.908 13.097 6.379 12.844 6.707L12.843 6.708Z" />
      </svg>
      Connected
    </span>
  );
}

function IntegrationRow({
  icon,
  name,
  badge,
  description,
  action,
}: {
  icon: React.ReactNode;
  name: string;
  badge?: React.ReactNode;
  description: React.ReactNode;
  action: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="shrink-0">
        <div className="rounded-xl p-2 bg-surface-elevated border border-border-subtle shadow-[0px_1px_2px_0px_rgba(20,21,26,0.05)]">
          {icon}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary flex items-center gap-2">{name}{badge}</p>
        <div className="text-sm text-text-secondary mt-0.5">{description}</div>
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  );
}

/* ─── Main component ────────────────────────────────────────────────────── */

export function SettingsPanel() {
  const { data: session } = useSession();
  const { darkMode, setDarkMode } = useTheme();

  const searchParams = useSearchParams();
  const notionParam = searchParams.get('notion');

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [savedFirstName, setSavedFirstName] = useState('');
  const [savedLastName, setSavedLastName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');

  const [usernameSlug, setUsernameSlug] = useState<string | null>(null);
  const [copiedProfile, setCopiedProfile] = useState(false);
  const [profilePublic, setProfilePublic] = useState(false);
  const [togglingProfile, setTogglingProfile] = useState(false);
  const [confirmPublicOpen, setConfirmPublicOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteAcknowledged, setDeleteAcknowledged] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [pronouns, setPronouns] = useState<string | null>(null);
  const [customPronouns, setCustomPronouns] = useState('');
  const [savedPronouns, setSavedPronouns] = useState<string | null>(null);
  const [pronounsSaving, setPronounsSaving] = useState(false);
  const [pronounsSaveStatus, setPronounsSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');

  const [usernameInput, setUsernameInput] = useState('');
  const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
  const [usernameChecking, setUsernameChecking] = useState(false);
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [usernameSaving, setUsernameSaving] = useState(false);
  const [usernameSaveStatus, setUsernameSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');
  const usernameDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [notionWorkspace, setNotionWorkspace] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const [disconnectError, setDisconnectError] = useState(false);

  useEffect(() => {
    fetch('/api/users')
      .then((r) => r.json())
      .then((data) => {
        const fn = data.preferred_first_name ?? '';
        const ln = data.preferred_last_name ?? '';
        setFirstName(fn);
        setLastName(ln);
        setSavedFirstName(fn);
        setSavedLastName(ln);
        const p = data.pronouns ?? null;
        const preset = p && ['she/her', 'he/him', 'they/them'].includes(p) ? p : p ? 'custom' : null;
        setPronouns(preset);
        setCustomPronouns(preset === 'custom' ? (p ?? '') : '');
        setSavedPronouns(p);
        setNotionWorkspace(data.notion_workspace_name ?? null);
        setUsernameSlug(data.username_slug ?? null);
        setUsernameInput(data.username_slug ?? '');
        setProfilePublic(data.profile_public ?? false);
      })
      .catch(() => {});
  }, []);

  const PRONOUN_PRESETS = ['she/her', 'he/him', 'they/them'] as const;

  async function handleSavePronouns() {
    const value = pronouns === 'custom' ? customPronouns.trim() || null : pronouns;
    setPronounsSaving(true);
    setPronounsSaveStatus('idle');
    try {
      const res = await fetch('/api/users', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pronouns: value }),
      });
      if (res.ok) {
        setSavedPronouns(value);
        setPronounsSaveStatus('saved');
      } else {
        setPronounsSaveStatus('error');
      }
    } catch {
      setPronounsSaveStatus('error');
    } finally {
      setPronounsSaving(false);
    }
  }

  function validateUsernameFormat(v: string): string | null {
    if (!v) return null;
    if (v.length < 3 || v.length > 30) return 'Must be 3–30 characters';
    if (!_USERNAME_RE.test(v)) return 'Only lowercase letters, numbers, and hyphens; cannot start or end with a hyphen';
    if (_RESERVED.has(v)) return 'That username is reserved';
    return null;
  }

  function handleUsernameChange(v: string) {
    setUsernameInput(v);
    setUsernameAvailable(null);
    setUsernameSaveStatus('idle');
    if (usernameDebounceRef.current) clearTimeout(usernameDebounceRef.current);
    const formatErr = validateUsernameFormat(v);
    if (formatErr) { setUsernameError(formatErr); return; }
    setUsernameError(null);
    if (!v || (v || null) === (usernameSlug || null)) return;
    usernameDebounceRef.current = setTimeout(async () => {
      setUsernameChecking(true);
      try {
        const res = await fetch(`/api/users/check-username/${encodeURIComponent(v)}`);
        if (res.ok) {
          const data = await res.json();
          setUsernameAvailable(data.available);
        }
      } finally {
        setUsernameChecking(false);
      }
    }, 500);
  }

  async function handleSaveUsername() {
    const formatErr = validateUsernameFormat(usernameInput);
    if (formatErr) { setUsernameError(formatErr); return; }
    if ((usernameInput || null) === (usernameSlug || null)) return;
    if (usernameAvailable === false) return;
    setUsernameSaving(true);
    setUsernameSaveStatus('idle');
    try {
      const res = await fetch('/api/users', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username_slug: usernameInput || null }),
      });
      if (res.ok) {
        const data = await res.json();
        setUsernameSlug(data.username_slug ?? null);
        setUsernameInput(data.username_slug ?? '');
        setUsernameAvailable(null);
        setUsernameSaveStatus('saved');
      } else {
        const data = await res.json().catch(() => ({}));
        setUsernameError(data.detail ?? 'Failed to save username');
        setUsernameSaveStatus('error');
      }
    } catch {
      setUsernameSaveStatus('error');
    } finally {
      setUsernameSaving(false);
    }
  }

  async function applyProfilePublic(newValue: boolean) {
    setTogglingProfile(true);
    try {
      const res = await fetch('/api/users', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_public: newValue }),
      });
      if (res.ok) {
        const data = await res.json();
        setProfilePublic(data.profile_public);
      }
    } finally {
      setTogglingProfile(false);
    }
  }

  function handleToggleProfilePublic(checked: boolean) {
    if (checked) setConfirmPublicOpen(true);
    else applyProfilePublic(false);
  }

  async function handleNotionDisconnect() {
    setDisconnecting(true);
    setDisconnectError(false);
    try {
      const res = await fetch('/api/notion', { method: 'DELETE' });
      if (res.ok) setNotionWorkspace(null);
      else setDisconnectError(true);
    } catch {
      setDisconnectError(true);
    } finally {
      setDisconnecting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaveStatus('idle');
    try {
      const res = await fetch('/api/users', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          preferred_first_name: firstName.trim() || null,
          preferred_last_name: lastName.trim() || null,
        }),
      });
      if (res.ok) {
        setSavedFirstName(firstName.trim());
        setSavedLastName(lastName.trim());
        setSaveStatus('saved');
        window.dispatchEvent(new CustomEvent('preferred-name-changed', {
          detail: { firstName: firstName.trim(), lastName: lastName.trim() },
        }));
      } else {
        setSaveStatus('error');
      }
    } catch {
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  }

  const userInitials = session?.user?.name
    ? session.user.name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : '??';

  const pronounsSaveValue = pronouns === 'custom' ? customPronouns.trim() || null : pronouns;

  // FiGithub imported for future GitHub OAuth integration
  void FiGithub;

  return (
    <div className="h-full flex flex-col bg-surface-elevated">

      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <div className="shrink-0 flex items-center h-12 px-6 bg-surface-elevated">
        <h1 className="text-sm font-medium text-text-primary tracking-[-0.1px]">Settings</h1>
      </div>

      {/* ── Scrollable area ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0">

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6 lg:px-16 pt-12 pb-24">
        <div className="divide-y divide-zinc-950/5 dark:divide-white/5 [&>*:first-child]:pt-0">

          {/* Account */}
          <SettingRow title="Account" description="Your Google account information.">
            <CardBox>
              <div className="flex items-center gap-3">
                <Avatar className="h-10 w-10 shrink-0">
                  <AvatarImage src={session?.user?.image ?? undefined} alt={session?.user?.name ?? ''} />
                  <AvatarFallback className="text-sm bg-surface-overlay text-text-secondary">
                    {userInitials}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary truncate">
                    {session?.user?.name || '—'}
                  </p>
                  <p className="text-sm text-text-secondary truncate">{session?.user?.email ?? '—'}</p>
                </div>
              </div>
            </CardBox>
          </SettingRow>

          {/* Display Name */}
          <SettingRow
            title="Display Name"
            description="Used when generating tailorings. Defaults to your Google name if not set."
          >
            <div className="flex flex-col gap-4">
              <div className="flex gap-3">
                <div className="flex flex-col gap-1.5 flex-1">
                  <label className="text-sm font-medium text-text-primary">First name</label>
                  <input
                    type="text"
                    placeholder="First name"
                    value={firstName}
                    onChange={(e) => { setFirstName(e.target.value); setSaveStatus('idle'); }}
                    className={inputCls}
                  />
                </div>
                <div className="flex flex-col gap-1.5 flex-1">
                  <label className="text-sm font-medium text-text-primary">Last name</label>
                  <input
                    type="text"
                    placeholder="Last name"
                    value={lastName}
                    onChange={(e) => { setLastName(e.target.value); setSaveStatus('idle'); }}
                    className={inputCls}
                  />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving || (firstName.trim() === savedFirstName && lastName.trim() === savedLastName)}
                  className={saveBtnCls}
                >
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
                <SaveStatus status={saveStatus} />
              </div>
            </div>
          </SettingRow>

          {/* Pronouns */}
          <SettingRow
            title="Pronouns"
            description="Used in AI-generated content that references you in third person."
          >
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-2">
                {PRONOUN_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => { setPronouns(pronouns === preset ? null : preset); setPronounsSaveStatus('idle'); }}
                    className={cn(
                      'px-3 h-8 rounded-[10px] text-sm border transition-colors',
                      pronouns === preset
                        ? 'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 border-transparent'
                        : 'bg-surface-elevated text-text-secondary border-border-default hover:border-border-strong hover:text-text-primary'
                    )}
                  >
                    {preset}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => { setPronouns(pronouns === 'custom' ? null : 'custom'); setPronounsSaveStatus('idle'); }}
                  className={cn(
                    'px-3 h-8 rounded-[10px] text-sm border transition-colors',
                    pronouns === 'custom'
                      ? 'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 border-transparent'
                      : 'bg-surface-elevated text-text-secondary border-border-default hover:border-border-strong hover:text-text-primary'
                  )}
                >
                  Custom
                </button>
              </div>
              {pronouns === 'custom' && (
                <input
                  type="text"
                  placeholder="e.g. ze/zir"
                  value={customPronouns}
                  onChange={(e) => { setCustomPronouns(e.target.value); setPronounsSaveStatus('idle'); }}
                  className={cn(inputCls, 'max-w-xs')}
                />
              )}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSavePronouns}
                  disabled={pronounsSaving || pronounsSaveValue === savedPronouns}
                  className={saveBtnCls}
                >
                  {pronounsSaving ? 'Saving…' : 'Save changes'}
                </button>
                <SaveStatus status={pronounsSaveStatus} />
              </div>
            </div>
          </SettingRow>

          {/* Username */}
          <SettingRow
            title="Username"
            description={`Your public URL: tailord.app/u/${usernameInput || 'your-username'}`}
          >
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-text-primary">Username</label>
                <div className="relative max-w-xs">
                  <input
                    type="text"
                    placeholder="your-username"
                    value={usernameInput}
                    onChange={(e) => handleUsernameChange(e.target.value)}
                    className={cn(inputCls, 'pr-8')}
                  />
                  {usernameChecking && (
                    <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-text-tertiary" />
                  )}
                  {!usernameChecking && usernameAvailable === true && (
                    <CheckCircle2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-success" />
                  )}
                </div>
                {usernameError && <p className="text-xs text-error">{usernameError}</p>}
                {!usernameError && usernameAvailable === false && (
                  <p className="text-xs text-error">That username is already taken</p>
                )}
                {!usernameError && usernameAvailable === true && (
                  <p className="text-xs text-success">Available</p>
                )}
                {usernameSlug && usernameInput !== usernameSlug && usernameInput && (
                  <p className="text-xs text-warning">
                    Changing your username will break existing links to your profile and tailorings.
                  </p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSaveUsername}
                  disabled={
                    usernameSaving ||
                    (usernameInput || null) === (usernameSlug || null) ||
                    !!usernameError ||
                    usernameAvailable === false ||
                    (!!usernameInput && (usernameInput || null) !== (usernameSlug || null) && usernameAvailable === null && !usernameChecking)
                  }
                  className={saveBtnCls}
                >
                  {usernameSaving ? 'Saving…' : 'Save changes'}
                </button>
                <SaveStatus status={usernameSaveStatus} />
              </div>
            </div>
          </SettingRow>

          {/* Public Profile — only shown when username is set */}
          {usernameSlug && (
            <SettingRow
              title="Public Profile"
              description="Share your experience and public tailorings with recruiters or in your bio."
            >
              <CardBox>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-text-primary">Enable public profile</p>
                    <p className="text-sm text-text-secondary mt-0.5">Anyone with the link can view your profile</p>
                  </div>
                  <Switch
                    checked={profilePublic}
                    onCheckedChange={handleToggleProfilePublic}
                    disabled={togglingProfile}
                  />
                </div>
                {profilePublic && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-surface-elevated border border-border-subtle">
                    <a
                      href={`/u/${usernameSlug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 text-sm text-text-link hover:underline truncate"
                    >
                      {typeof window !== 'undefined' ? `${window.location.origin}/u/${usernameSlug}` : `/u/${usernameSlug}`}
                    </a>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(`${window.location.origin}/u/${usernameSlug}`);
                        setCopiedProfile(true);
                        setTimeout(() => setCopiedProfile(false), 2000);
                      }}
                      className="shrink-0 text-text-tertiary hover:text-text-primary transition-colors"
                      title="Copy link"
                    >
                      {copiedProfile
                        ? <CheckCircle2 className="h-4 w-4 text-success" />
                        : <Copy className="h-4 w-4" />}
                    </button>
                  </div>
                )}
              </CardBox>
            </SettingRow>
          )}

          {/* Appearance */}
          <SettingRow title="Appearance" description="Customize how Tailord looks for you.">
            <CardBox>
              <IntegrationRow
                icon={darkMode
                  ? <Sun className="h-5 w-5 text-text-primary" />
                  : <Moon className="h-5 w-5 text-text-primary" />}
                name="Theme"
                description={darkMode ? 'Dark mode is active' : 'Light mode is active'}
                action={
                  <button
                    type="button"
                    onClick={() => setDarkMode(!darkMode)}
                    className={outlineBtnCls}
                  >
                    {darkMode
                      ? <Sun className="h-3.5 w-3.5" />
                      : <Moon className="h-3.5 w-3.5" />}
                    {darkMode ? 'Light mode' : 'Dark mode'}
                  </button>
                }
              />
            </CardBox>
          </SettingRow>

          {/* Integrations */}
          <SettingRow
            title="Integrations"
            description="Connect and authorize apps to use with Tailord."
          >
            <CardBox>
              <IntegrationRow
                icon={<SiNotion className="h-5 w-5 text-text-primary" />}
                name="Notion"
                badge={notionWorkspace ? <ConnectedBadge /> : undefined}
                description={
                  notionWorkspace
                    ? <span>Connected to <span className="font-medium text-text-primary">{notionWorkspace}</span></span>
                    : notionParam === 'error'
                      ? <span className="text-error">Connection failed. Please try again.</span>
                      : 'Export tailorings directly to your Notion workspace'
                }
                action={
                  <div className="flex flex-col items-end gap-1">
                    {notionWorkspace ? (
                      <button
                        type="button"
                        onClick={handleNotionDisconnect}
                        disabled={disconnecting}
                        className={outlineBtnCls}
                      >
                        {disconnecting ? 'Disconnecting…' : 'Disconnect'}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => { window.location.href = '/api/auth/notion'; }}
                        className={outlineBtnCls}
                      >
                        Connect
                      </button>
                    )}
                    {disconnectError && (
                      <p className="text-xs text-error">Disconnect failed.</p>
                    )}
                  </div>
                }
              />
            </CardBox>
          </SettingRow>

          {/* Sign Out */}
          <SettingRow title="Sign Out" description="Sign out of your Tailord account.">
            <button
              type="button"
              onClick={() => signOut({ callbackUrl: '/' })}
              className={cn(
                outlineBtnCls,
                'text-red-600 border-red-200 dark:border-red-900/40 ',
                'hover:bg-red-50 dark:hover:bg-red-950/20 hover:text-red-600 hover:border-red-300 dark:hover:border-red-800/50'
              )}
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </button>
          </SettingRow>

          {/* Danger Zone */}
          <SettingRow
            title="Danger Zone"
            description="Permanently delete your account and all associated data."
            danger
          >
            <CardBox className="border border-red-200 dark:border-red-900/30 bg-red-50/40 dark:bg-red-950/10 gap-0">
              <IntegrationRow
                icon={<TriangleAlert className="h-5 w-5 text-red-500" />}
                name="Delete account"
                description="All your experience, tailorings, and uploaded files will be removed. This cannot be undone."
                action={
                  <button
                    type="button"
                    onClick={() => { setDeleteAcknowledged(false); setDeleteOpen(true); }}
                    className={cn(
                      outlineBtnCls,
                      'text-red-600 border-red-200 dark:border-red-900/40 ',
                      'hover:bg-red-50 dark:hover:bg-red-950/20 hover:text-red-600 hover:border-red-300'
                    )}
                  >
                    Delete account
                  </button>
                }
              />
            </CardBox>
          </SettingRow>

        </div>
      </div>

      {/* ── Dialogs ──────────────────────────────────────────────────────── */}

      <Dialog open={confirmPublicOpen} onOpenChange={setConfirmPublicOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Make profile public?</DialogTitle>
            <DialogDescription>
              Anyone with your profile link will be able to view your experience. You can make it private again at any time.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmPublicOpen(false)}>Cancel</Button>
            <Button onClick={() => { setConfirmPublicOpen(false); applyProfilePublic(true); }}>Make Public</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete account?</DialogTitle>
            <DialogDescription>
              This will permanently delete your account, experience, all tailorings, and any uploaded files. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-start gap-3 py-2">
            <input
              type="checkbox"
              id="delete-ack"
              checked={deleteAcknowledged}
              onChange={(e) => setDeleteAcknowledged(e.target.checked)}
              className="mt-0.5 h-4 w-4 cursor-pointer"
            />
            <label htmlFor="delete-ack" className="text-sm text-text-secondary cursor-pointer">
              I understand this is permanent and cannot be undone
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={deleting}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={!deleteAcknowledged || deleting}
              onClick={async () => {
                setDeleting(true);
                try {
                  const res = await fetch('/api/users', { method: 'DELETE' });
                  if (res.ok) await signOut({ callbackUrl: '/' });
                } finally {
                  setDeleting(false);
                }
              }}
            >
              {deleting ? 'Deleting…' : 'Delete account'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      </div>{/* end scrollable area */}
    </div>
  );
}
