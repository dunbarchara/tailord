'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { Loader2, Globe, Plus, User, Sun, Moon, LogOut, Settings, ChevronsUpDown, Trash2, AlertCircle } from 'lucide-react';
import { useSession, signOut } from 'next-auth/react';
import { useTheme } from '@/components/ThemeProvider';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { TailoringListItem } from '@/types';

/* ─── Icons ──────────────────────────────────────────────────────────────── */

function IconHome({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3.145 6.2L8.395 2.21C8.753 1.938 9.248 1.938 9.605 2.21L14.855 6.2C15.104 6.389 15.25 6.684 15.25 6.996V14.25C15.25 15.355 14.355 16.25 13.25 16.25H4.75C3.645 16.25 2.75 15.355 2.75 14.25V6.996C2.75 6.683 2.896 6.389 3.145 6.2Z" />
      <path d="M11.652 12.152C10.188 13.616 7.813 13.616 6.349 12.152" />
    </svg>
  );
}

function IconEditor({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M5.75 6.75H7.75" />
      <path d="M5.75 9.75H10.25" />
      <path d="M15.16 6.24999H11.75C11.198 6.24999 10.75 5.80199 10.75 5.24999V1.85199" />
      <path d="M15.25 8.584V6.664C15.25 6.399 15.145 6.144 14.957 5.957L11.043 2.043C10.855 1.855 10.601 1.75 10.336 1.75H4.75C3.645 1.75 2.75 2.646 2.75 3.75V14.25C2.75 15.354 3.645 16.25 4.75 16.25H8.385" />
      <path d="M10.75 17.25C10.75 17.25 11.432 11.259 17.25 10.75C15.82 12.44 17.25 15.75 13.5 15.75" />
    </svg>
  );
}

function IconWorkflows({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M14.25 10.75H12.25C11.6977 10.75 11.25 11.1977 11.25 11.75V13.75C11.25 14.3023 11.6977 14.75 12.25 14.75H14.25C14.8023 14.75 15.25 14.3023 15.25 13.75V11.75C15.25 11.1977 14.8023 10.75 14.25 10.75Z" />
      <path d="M5.25 3.25H12.875C14.187 3.25 15.25 4.313 15.25 5.625C15.25 6.937 14.187 8 12.875 8H5.125C3.813 8 2.75 9.063 2.75 10.375C2.75 11.687 3.813 12.75 5.125 12.75H8.75" />
    </svg>
  );
}

function IconSearch({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="7.75" cy="7.75" r="5" />
      <path d="M13.25 13.25L11.25 11.25" />
    </svg>
  );
}

function IconCollapse({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M11 2.75H14.25C15.355 2.75 16.25 3.645 16.25 4.75V13.25C16.25 14.355 15.355 15.25 14.25 15.25H11" />
      <path d="M8.25 15.25H3.75C2.645 15.25 1.75 14.355 1.75 13.25V4.75C1.75 3.645 2.645 2.75 3.75 2.75H8.25V15.25Z" />
    </svg>
  );
}

/* ─── Nav item styles ────────────────────────────────────────────────────── */

const navItemBase =
  'flex items-center gap-2 h-8 w-full px-2 rounded-[10px] text-sm font-normal tracking-[-0.1px] leading-5 transition-colors outline-none border border-transparent';

const navItemInactive =
  'text-text-secondary hover:bg-black/5 dark:hover:bg-white/5 hover:text-text-primary';

const navItemActive =
  'text-brand-accent hover:bg-green-600/5';

/* ─── NavItem ────────────────────────────────────────────────────────────── */

function NavItem({
  icon: Icon,
  label,
  href,
  active = false,
  collapsed = false,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href: string;
  active?: boolean;
  collapsed?: boolean;
}) {
  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(navItemBase, active ? navItemActive : navItemInactive)}
    >
      <Icon className="size-[18px] shrink-0" />
      {!collapsed && <span>{label}</span>}
    </Link>
  );
}

/* ─── SearchBar ──────────────────────────────────────────────────────────── */

function SearchBar({
  collapsed,
  onExpand,
  query,
  onQueryChange,
}: {
  collapsed: boolean;
  onExpand: () => void;
  query: string;
  onQueryChange: (q: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const prevCollapsed = useRef(collapsed);

  useEffect(() => {
    if (prevCollapsed.current && !collapsed) {
      const t = setTimeout(() => inputRef.current?.focus(), 200);
      return () => clearTimeout(t);
    }
    prevCollapsed.current = collapsed;
  }, [collapsed]);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onExpand}
        className="flex items-center h-8 w-full px-2 rounded-[10px] border border-transparent bg-black/5 dark:bg-white/5 hover:bg-black/[0.07] dark:hover:bg-white/[0.07] transition-colors text-text-tertiary"
      >
        <IconSearch className="size-[18px] shrink-0" />
      </button>
    );
  }

  return (
    <div className="flex items-center h-8 px-2 gap-2 rounded-[10px] border border-transparent bg-black/5 dark:bg-white/5 focus-within:bg-black/[0.07] dark:focus-within:bg-white/[0.07] transition-colors">
      <IconSearch className="size-[18px] shrink-0 text-text-tertiary" />
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && onQueryChange('')}
        placeholder="Search..."
        className="flex-1 bg-transparent outline-none text-sm font-normal tracking-[-0.1px] text-text-secondary placeholder:text-text-disabled min-w-0"
      />
    </div>
  );
}

/* ─── Tailoring list item ────────────────────────────────────────────────── */

function tailoringLabel(t: TailoringListItem): string {
  if (t.title) return t.title;
  if (t.job_url) {
    try { return new URL(t.job_url).hostname.replace(/^www\./, ''); } catch {}
  }
  return 'Untitled';
}

function SpinningLoader({ className }: { className?: string }) {
  return <Loader2 className={cn(className, 'animate-spin')} />;
}

function TailoringItem({
  tailoring,
  active,
  collapsed,
  onDelete,
}: {
  tailoring: TailoringListItem;
  active: boolean;
  collapsed: boolean;
  onDelete: (id: string) => void;
}) {
  const label = tailoringLabel(tailoring);
  const generating = tailoring.generation_status === 'generating';
  const failed = tailoring.generation_status === 'error';
  const Icon = generating ? SpinningLoader : IconWorkflows;

  if (collapsed) {
    return (
      <Link
        href={`/dashboard/tailorings/${tailoring.id}`}
        title={[label, tailoring.company].filter(Boolean).join(' — ')}
        className={cn(navItemBase, active ? navItemActive : navItemInactive)}
      >
        <Icon className="size-[18px] shrink-0" />
      </Link>
    );
  }

  return (
    <div className="group relative">
      <Link
        href={`/dashboard/tailorings/${tailoring.id}`}
        title={[label, tailoring.company].filter(Boolean).join(' — ')}
        className={cn(
          'flex items-center gap-2 w-full px-2 py-1.5 pr-8 rounded-[10px] border border-transparent transition-colors outline-none',
          active ? navItemActive : navItemInactive,
        )}
      >
        <Icon className="size-[18px] shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-normal tracking-[-0.1px] leading-5">{label}</p>
          {(tailoring.company || generating || failed) && (
            <div className="flex items-center gap-1.5 mt-0.5">
              <p className="truncate text-xs text-text-disabled leading-4 min-w-0">
                {generating && !tailoring.company ? 'Generating...' : tailoring.company}
              </p>
              {failed && (
                <span className="inline-flex items-center gap-1 py-0.5 px-1.5 rounded-md text-[10px] font-medium bg-red-100 dark:bg-red-950/20 text-red-600 dark:text-red-400 shrink-0">
                  <AlertCircle className="h-2.5 w-2.5" />
                  Failed
                </span>
              )}
            </div>
          )}
        </div>
      </Link>
      <button
        type="button"
        onClick={(e) => { e.preventDefault(); onDelete(tailoring.id); }}
        className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded-[6px] opacity-0 group-hover:opacity-100 transition-opacity text-text-tertiary hover:text-error"
        aria-label="Delete tailoring"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

/* ─── Account popover ────────────────────────────────────────────────────── */

function AccountPopover({ collapsed }: { collapsed: boolean }) {
  const { data: session } = useSession();
  const { darkMode, setDarkMode } = useTheme();
  const [preferredName, setPreferredName] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/users')
      .then((r) => r.json())
      .then((data) => {
        const n = [data.preferred_first_name, data.preferred_last_name].filter(Boolean).join(' ');
        setPreferredName(n || null);
      })
      .catch(() => {});

    function onNameChanged(e: Event) {
      const { firstName, lastName } = (e as CustomEvent).detail;
      const n = [firstName, lastName].filter(Boolean).join(' ');
      setPreferredName(n || null);
    }
    window.addEventListener('preferred-name-changed', onNameChanged);
    return () => window.removeEventListener('preferred-name-changed', onNameChanged);
  }, []);

  const displayName = preferredName ?? session?.user?.name ?? '';
  const email = session?.user?.email ?? '';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(navItemBase, navItemInactive, 'justify-between')}
          title={collapsed ? 'Account' : undefined}
        >
          <div className="flex items-center gap-2">
            <User className="size-[18px] shrink-0" strokeWidth={1.8} />
            {!collapsed && <span>Account</span>}
          </div>
          {!collapsed && (
            <ChevronsUpDown className="size-[14px] shrink-0 text-text-disabled" strokeWidth={1.8} />
          )}
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        side="top"
        align="start"
        sideOffset={8}
        className="w-[220px] rounded-2xl p-1.5 bg-surface-elevated border-border-subtle shadow-lg"
      >
        {/* Name + email */}
        <div className="flex flex-col gap-0.5 px-2 py-2">
          <span className="text-sm font-medium text-text-primary leading-5 truncate">{displayName}</span>
          <span className="text-xs text-text-tertiary leading-4 truncate">{email}</span>
        </div>

        <DropdownMenuSeparator className="bg-border-subtle mx-1 my-1" />

        <DropdownMenuItem asChild className="rounded-xl gap-1.5 p-2 text-sm text-text-secondary cursor-pointer focus:bg-black/5 dark:focus:bg-white/5 focus:text-text-primary">
          <Link href="/dashboard/settings">
            <Settings className="size-4 text-text-tertiary shrink-0" strokeWidth={1.8} />
            <span>Settings</span>
          </Link>
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => setDarkMode(!darkMode)}
          className="rounded-xl gap-1.5 p-2 text-sm text-text-secondary cursor-pointer focus:bg-black/5 dark:focus:bg-white/5 focus:text-text-primary"
        >
          {darkMode
            ? <Sun className="size-4 text-text-tertiary shrink-0" strokeWidth={1.8} />
            : <Moon className="size-4 text-text-tertiary shrink-0" strokeWidth={1.8} />}
          <span>{darkMode ? 'Light mode' : 'Dark mode'}</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator className="bg-border-subtle mx-1 my-1" />

        <DropdownMenuItem
          onClick={() => signOut({ callbackUrl: '/' })}
          className="rounded-xl gap-1.5 p-2 text-sm text-red-600 cursor-pointer focus:bg-red-50 dark:focus:bg-red-950/20 focus:text-red-600"
        >
          <LogOut className="size-4 shrink-0" strokeWidth={1.8} />
          <span>Sign out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/* ─── Divider ────────────────────────────────────────────────────────────── */

function Divider() {
  return (
    <div className="px-5 shrink-0">
      <div className="h-px bg-border-subtle" />
    </div>
  );
}

/* ─── Active item ────────────────────────────────────────────────────────── */

function getActiveItem(pathname: string | null): string {
  if (!pathname || pathname === '/dashboard') return 'Home';
  if (pathname.startsWith('/dashboard/experience')) return 'My Experience';
  if (pathname.startsWith('/dashboard/profile')) return 'My Profile';
  if (pathname.startsWith('/dashboard/settings')) return 'Settings';
  if (pathname === '/dashboard/tailorings/new') return 'New Tailoring';
  const match = pathname.match(/^\/dashboard\/tailorings\/([^/]+)$/);
  if (match) return match[1];
  return 'Home';
}

/* ─── Sidebar ────────────────────────────────────────────────────────────── */

export function Sidebar({ tailorings = [] }: { tailorings?: TailoringListItem[] }) {
  const pathname = usePathname();
  const router = useRouter();
  const activeItem = getActiveItem(pathname);
  const [collapsed, setCollapsed] = useState(false);
  const [smallScreen, setSmallScreen] = useState(false);
  const [query, setQuery] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Derive combined collapsed state
  const isCollapsed = collapsed || smallScreen;

  // Expand handler: clears both manual and auto-collapse
  function handleExpand() {
    setCollapsed(false);
    setSmallScreen(false);
  }

  // Responsive auto-collapse via matchMedia
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1023px)');
    setSmallScreen(mq.matches);
    function onChange(e: MediaQueryListEvent) {
      setSmallScreen(e.matches);
    }
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const filteredTailorings = query.trim()
    ? tailorings.filter((t) => {
        const q = query.toLowerCase();
        return t.title?.toLowerCase().includes(q) || t.company?.toLowerCase().includes(q);
      })
    : tailorings;

  async function handleDelete(id: string) {
    setDeleting(true);
    try {
      await fetch(`/api/tailorings/${id}`, { method: 'DELETE' });
    } finally {
      setDeleting(false);
      setConfirmDeleteId(null);
      if (pathname === `/dashboard/tailorings/${id}`) {
        router.push('/dashboard');
      }
      router.refresh();
    }
  }

  return (
    <>
      <aside
        className={cn(
          'flex flex-col bg-surface-base border-r border-border-subtle transition-[width] duration-200 overflow-hidden shrink-0',
          isCollapsed ? 'w-[60px]' : 'w-[240px]',
        )}
      >
        <div
          className={cn(
            'flex grow flex-col overflow-hidden',
            isCollapsed ? 'w-[60px] min-w-[60px]' : 'w-[240px] min-w-[240px]',
          )}
        >

          {/* Workspace header */}
          <div className="flex items-end pb-1.5 h-12 px-3 shrink-0">
            <Link
              href="/"
              className="flex items-center py-1.5 gap-1 px-[7px] rounded-[10px] hover:bg-black/5 dark:hover:bg-white/5 outline-none transition-colors"
            >
              <Image alt="Tailord logo" width={22} height={22} className="h-[22px] w-[22px] shrink-0" src="/logo.svg" />
              {!isCollapsed && (
                <span
                  className="text-text-primary text-[16px] leading-none font-semibold tracking-tight whitespace-nowrap"
                  style={{ fontFamily: 'var(--font-inter), ui-sans-serif, system-ui' }}
                >
                  Tailord
                </span>
              )}
            </Link>
          </div>

          <Divider />

          {/* Sticky top: primary nav + tailorings header/controls */}
          <div className="flex flex-col gap-3.5 px-3 pt-3 shrink-0">

            {/* Primary nav */}
            <nav className="flex flex-col gap-0.5">
              <NavItem icon={IconHome}   label="Home"          href="/dashboard"           active={activeItem === 'Home'}          collapsed={isCollapsed} />
              <NavItem icon={IconEditor} label="My Experience" href="/dashboard/experience" active={activeItem === 'My Experience'} collapsed={isCollapsed} />
              <NavItem icon={(p) => <Globe {...p} size={18} strokeWidth={1.8} />} label="My Profile" href="/dashboard/profile" active={activeItem === 'My Profile'} collapsed={isCollapsed} />
            </nav>

            {/* Tailorings section header + controls */}
            <div className="flex flex-col gap-0.5">
              {isCollapsed ? (
                <div className="h-7 px-2 flex items-center">
                  <div className="h-px w-full bg-border-subtle" />
                </div>
              ) : (
                <span className="px-2 py-1.5 font-medium text-xs text-text-tertiary">
                  Tailorings
                </span>
              )}
              <NavItem icon={(p) => <Plus {...p} size={18} strokeWidth={1.8} />} label="New Tailoring" href="/dashboard/tailorings/new" active={activeItem === 'New Tailoring'} collapsed={isCollapsed} />
              <SearchBar collapsed={isCollapsed} onExpand={handleExpand} query={query} onQueryChange={setQuery} />
            </div>

          </div>

          {/* Scrollable tailorings list */}
          <div className="relative flex-1 min-h-0">
            <div className="h-full overflow-y-auto px-3 py-1">
              <div className="flex flex-col gap-0.5 pb-5">
                {isCollapsed ? (() => {
                  const activeTailoring = tailorings.find(t => activeItem === t.id) ?? tailorings[0];
                  const hasMore = tailorings.length > 1;
                  return (
                    <>
                      {activeTailoring && (
                        <TailoringItem
                          key={activeTailoring.id}
                          tailoring={activeTailoring}
                          active={activeItem === activeTailoring.id}
                          collapsed={true}
                          onDelete={setConfirmDeleteId}
                        />
                      )}
                      {hasMore && (
                        <button
                          type="button"
                          onClick={handleExpand}
                          title="Show all tailorings"
                          className="flex items-center justify-center h-8 w-full rounded-[10px] border border-transparent text-text-disabled hover:bg-black/5 dark:hover:bg-white/5 hover:text-text-secondary transition-colors"
                        >
                          <span className="text-sm leading-none tracking-widest">···</span>
                        </button>
                      )}
                    </>
                  );
                })() : filteredTailorings.length === 0 && query ? (
                  <p className="px-2 py-1.5 text-xs text-text-disabled">No results</p>
                ) : filteredTailorings.map((t) => (
                  <TailoringItem
                    key={t.id}
                    tailoring={t}
                    active={activeItem === t.id}
                    collapsed={false}
                    onDelete={setConfirmDeleteId}
                  />
                ))}
              </div>
            </div>
            {!isCollapsed && (
              <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-surface-base to-transparent" />
            )}
          </div>

          {/* Sticky bottom — account + collapse */}
          <div className="shrink-0 px-3 pb-3">
            <div className="mb-2.5 px-2">
              <div className="h-px bg-border-subtle" />
            </div>
            <div className="flex flex-col gap-0.5">
              <AccountPopover collapsed={isCollapsed} />
            </div>
            <div className="mt-0.5" />
            <button
              type="button"
              onClick={() => isCollapsed ? handleExpand() : setCollapsed(true)}
              className={cn(navItemBase, navItemInactive)}
              title={isCollapsed ? 'Expand' : 'Collapse'}
            >
              <IconCollapse className="size-[18px] shrink-0" />
              {!isCollapsed && <span>Collapse</span>}
            </button>
          </div>

        </div>
      </aside>

      <Dialog open={!!confirmDeleteId} onOpenChange={(open) => !open && setConfirmDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete tailoring?</DialogTitle>
            <DialogDescription>This will permanently delete this tailoring and cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDeleteId(null)}>Cancel</Button>
            <Button variant="destructive" disabled={deleting} onClick={() => confirmDeleteId && handleDelete(confirmDeleteId)}>
              {deleting ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
