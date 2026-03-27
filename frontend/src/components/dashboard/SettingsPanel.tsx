'use client';

import { useEffect, useRef, useState } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useTheme } from '@/components/ThemeProvider';
import { Moon, Sun, LogOut, Copy, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useSearchParams } from 'next/navigation';

const _USERNAME_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const _RESERVED = new Set([
  'dashboard', 'admin', 'api', 'settings', 'login', 'register',
  'u', 't', 'auth', 'notion', 'help', 'about', 'pricing', 'terms',
  'privacy', 'careers', 'blog', 'tailord', 'me', 'public',
]);

export function SettingsPanel() {
  const { data: session } = useSession();
  const { darkMode, setDarkMode } = useTheme();

  const searchParams = useSearchParams();
  const notionParam = searchParams.get('notion');

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
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
        setFirstName(data.preferred_first_name ?? '');
        setLastName(data.preferred_last_name ?? '');
        const p = data.pronouns ?? null;
        const preset = p && ['she/her', 'he/him', 'they/them'].includes(p) ? p : p ? 'custom' : null;
        setPronouns(preset);
        setCustomPronouns(preset === 'custom' ? (p ?? '') : '');
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
    if (formatErr) {
      setUsernameError(formatErr);
      return;
    }
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
    if (checked) {
      setConfirmPublicOpen(true);
    } else {
      applyProfilePublic(false);
    }
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

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-2xl mx-auto p-6 lg:p-8 space-y-8">
        <h1 className="text-2xl font-semibold text-text-primary">Settings</h1>

        {/* Account */}
        <section className="space-y-4">
          <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Account</h2>
          <div className="flex items-center gap-4">
            <Avatar className="h-12 w-12">
              <AvatarImage src={session?.user?.image ?? undefined} alt={session?.user?.name ?? ''} />
              <AvatarFallback className="text-sm">{userInitials}</AvatarFallback>
            </Avatar>
            <div>
              <p className="font-medium text-text-primary">
                {[firstName, lastName].filter(Boolean).join(' ') || session?.user?.name || '—'}
              </p>
              <p className="text-sm text-text-secondary">{session?.user?.email ?? '—'}</p>
            </div>
          </div>
        </section>

        <Separator />

        {/* Pronouns */}
        <section className="space-y-4">
          <div>
            <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Pronouns</h2>
            <p className="text-xs text-text-tertiary mt-1">
              Used in all AI-generated content that references you in third person.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {PRONOUN_PRESETS.map((preset) => (
              <button
                key={preset}
                onClick={() => { setPronouns(pronouns === preset ? null : preset); setPronounsSaveStatus('idle'); }}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  pronouns === preset
                    ? 'bg-brand-primary text-white border-brand-primary'
                    : 'bg-surface-base text-text-secondary border-border-default hover:border-border-strong'
                }`}
              >
                {preset}
              </button>
            ))}
            <button
              onClick={() => { setPronouns(pronouns === 'custom' ? null : 'custom'); setPronounsSaveStatus('idle'); }}
              className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                pronouns === 'custom'
                  ? 'bg-brand-primary text-white border-brand-primary'
                  : 'bg-surface-base text-text-secondary border-border-default hover:border-border-strong'
              }`}
            >
              Custom
            </button>
          </div>
          {pronouns === 'custom' && (
            <Input
              placeholder="e.g. ze/zir"
              value={customPronouns}
              onChange={(e) => { setCustomPronouns(e.target.value); setPronounsSaveStatus('idle'); }}
              className="max-w-xs"
            />
          )}
          <div className="flex items-center gap-3">
            <Button onClick={handleSavePronouns} disabled={pronounsSaving}>
              {pronounsSaving ? 'Saving…' : 'Save pronouns'}
            </Button>
            {pronounsSaveStatus === 'saved' && <p className="text-sm text-success">Saved</p>}
            {pronounsSaveStatus === 'error' && <p className="text-sm text-error">Failed to save</p>}
          </div>
        </section>

        <Separator />

        {/* Display name */}
        <section className="space-y-4">
          <div>
            <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Display name</h2>
            <p className="text-xs text-text-tertiary mt-1">
              Used when generating tailorings. Defaults to your Google name if not set.
            </p>
          </div>
          <div className="flex gap-3">
            <Input
              placeholder="First name"
              value={firstName}
              onChange={(e) => { setFirstName(e.target.value); setSaveStatus('idle'); }}
            />
            <Input
              placeholder="Last name"
              value={lastName}
              onChange={(e) => { setLastName(e.target.value); setSaveStatus('idle'); }}
            />
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save name'}
            </Button>
            {saveStatus === 'saved' && <p className="text-sm text-success">Saved</p>}
            {saveStatus === 'error' && <p className="text-sm text-error">Failed to save</p>}
          </div>
        </section>

        <Separator />

        {/* Username */}
        <section className="space-y-4">
          <div>
            <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Username</h2>
            <p className="text-xs text-text-tertiary mt-1">
              Your public URL: tailord.app/u/<span className="font-medium">{usernameInput || 'your-username'}</span>
            </p>
          </div>
          <div className="space-y-2">
            <div className="relative">
              <Input
                placeholder="your-username"
                value={usernameInput}
                onChange={(e) => handleUsernameChange(e.target.value)}
                className="pr-8"
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
          </div>
          {usernameSlug && usernameInput !== usernameSlug && usernameInput && (
            <p className="text-xs text-warning">
              Changing your username will break existing links to your profile and tailorings.
            </p>
          )}
          <div className="flex items-center gap-3">
            <Button
              onClick={handleSaveUsername}
              disabled={
                usernameSaving ||
                (usernameInput || null) === (usernameSlug || null) ||
                !!usernameError ||
                usernameAvailable === false ||
                (!!usernameInput && (usernameInput || null) !== (usernameSlug || null) && usernameAvailable === null && !usernameChecking)
              }
            >
              {usernameSaving ? 'Saving…' : 'Save username'}
            </Button>
            {usernameSaveStatus === 'saved' && <p className="text-sm text-success">Saved</p>}
            {usernameSaveStatus === 'error' && !usernameError && <p className="text-sm text-error">Failed to save</p>}
          </div>
        </section>

        <Separator />

        {/* Public profile */}
        {usernameSlug && (
          <>
            <section className="space-y-4">
              <div>
                <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Public profile</h2>
                <p className="text-xs text-text-tertiary mt-1">
                  Share your experience and public tailorings with recruiters or in your bio.
                </p>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-primary">Enable public profile</p>
                  <p className="text-xs text-text-tertiary mt-0.5">Anyone with the link can view your profile</p>
                </div>
                <Switch
                  checked={profilePublic}
                  onCheckedChange={handleToggleProfilePublic}
                  disabled={togglingProfile}
                />
              </div>

              <Dialog open={confirmPublicOpen} onOpenChange={setConfirmPublicOpen}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Make profile public?</DialogTitle>
                    <DialogDescription>
                      Anyone with your profile link will be able to view your experience. You can make it private again at any time.
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setConfirmPublicOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={() => { setConfirmPublicOpen(false); applyProfilePublic(true); }}>
                      Make Public
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              {profilePublic && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-surface-sunken border border-border-subtle">
                  <a
                    href={`/u/${usernameSlug}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 text-sm text-text-link hover:underline truncate"
                  >
                    {typeof window !== 'undefined' ? `${window.location.origin}/u/${usernameSlug}` : `/u/${usernameSlug}`}
                  </a>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(`${window.location.origin}/u/${usernameSlug}`);
                      setCopiedProfile(true);
                      setTimeout(() => setCopiedProfile(false), 2000);
                    }}
                    className="flex-shrink-0 text-text-tertiary hover:text-text-primary transition-colors"
                    title="Copy link"
                  >
                    {copiedProfile
                      ? <CheckCircle2 className="h-4 w-4 text-success" />
                      : <Copy className="h-4 w-4" />}
                  </button>
                </div>
              )}
            </section>

            <Separator />
          </>
        )}

        {/* Appearance */}
        <section className="space-y-4">
          <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Appearance</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-primary">Dark mode</p>
              <p className="text-xs text-text-tertiary mt-0.5">Switch between light and dark theme</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDarkMode(!darkMode)}
              className="gap-2"
            >
              {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              {darkMode ? 'Light mode' : 'Dark mode'}
            </Button>
          </div>
        </section>

        <Separator />

        {/* Connected apps */}
        <section className="space-y-4">
          <h2 className="text-xs font-medium text-text-tertiary uppercase tracking-wider">Connected apps</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-primary">Notion</p>
              {notionWorkspace ? (
                <p className="text-xs text-text-secondary mt-0.5">Connected to <span className="font-medium">{notionWorkspace}</span></p>
              ) : (
                <p className="text-xs text-text-tertiary mt-0.5">Export tailorings directly to your Notion workspace</p>
              )}
              {notionParam === 'error' && !notionWorkspace && (
                <p className="text-xs text-error mt-1">Connection failed. Please try again.</p>
              )}
            </div>
            <div className="flex flex-col items-end gap-1">
              {notionWorkspace ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNotionDisconnect}
                  disabled={disconnecting}
                >
                  {disconnecting ? 'Disconnecting…' : 'Disconnect'}
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { window.location.href = '/api/auth/notion'; }}
                >
                  Connect
                </Button>
              )}
              {disconnectError && (
                <p className="text-xs text-error">Disconnect failed. Please try again.</p>
              )}
            </div>
          </div>
        </section>

        <Separator />

        {/* Sign out */}
        <section>
          <Button
            variant="outline"
            className="gap-2 text-destructive hover:bg-destructive/5 hover:text-destructive border-destructive/30"
            onClick={() => signOut({ callbackUrl: '/' })}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </section>

        <Separator />

        {/* Danger zone */}
        <section className="space-y-4">
          <h2 className="text-xs font-medium text-error uppercase tracking-wider">Danger zone</h2>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-primary">Delete account</p>
              <p className="text-xs text-text-tertiary mt-0.5">Permanently delete your account and all data</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:bg-destructive/5 hover:text-destructive border-destructive/30"
              onClick={() => { setDeleteAcknowledged(false); setDeleteOpen(true); }}
            >
              Delete account
            </Button>
          </div>

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
                <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={deleting}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  disabled={!deleteAcknowledged || deleting}
                  onClick={async () => {
                    setDeleting(true);
                    try {
                      const res = await fetch('/api/users', { method: 'DELETE' });
                      if (res.ok) {
                        await signOut({ callbackUrl: '/' });
                      }
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
        </section>
      </div>
    </div>
  );
}
