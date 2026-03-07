'use client';

import { useEffect, useState } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { useTheme } from '@/components/ThemeProvider';
import { Moon, Sun, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';

export function SettingsPanel() {
  const { data: session } = useSession();
  const { darkMode, setDarkMode } = useTheme();

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');

  useEffect(() => {
    fetch('/api/users')
      .then((r) => r.json())
      .then((data) => {
        setFirstName(data.preferred_first_name ?? '');
        setLastName(data.preferred_last_name ?? '');
      })
      .catch(() => {});
  }, []);

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
      </div>
    </div>
  );
}
