'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Loader2, Globe, Plus, User, Sun, Moon, LogOut, Settings, ChevronsUpDown } from 'lucide-react';
import { useSession, signOut } from 'next-auth/react';
import { useTheme } from '@/components/ThemeProvider';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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


function IconSettings({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M9 10.749C9.9665 10.749 10.75 9.96549 10.75 8.99899C10.75 8.03249 9.9665 7.24899 9 7.24899C8.0335 7.24899 7.25 8.03249 7.25 8.99899C7.25 9.96549 8.0335 10.749 9 10.749Z" fill="none" />
      <path d="M15.175 7.278L14.246 6.95C14.144 6.689 14.027 6.43 13.883 6.18C13.739 5.93 13.573 5.7 13.398 5.481L13.578 4.513C13.703 3.842 13.391 3.164 12.8 2.823L12.449 2.62C11.857 2.278 11.115 2.347 10.596 2.791L9.851 3.428C9.291 3.342 8.718 3.342 8.148 3.428L7.403 2.79C6.884 2.346 6.141 2.277 5.55 2.619L5.199 2.822C4.607 3.163 4.296 3.841 4.421 4.512L4.601 5.477C4.241 5.926 3.955 6.423 3.749 6.951L2.825 7.277C2.181 7.504 1.75 8.113 1.75 8.796V9.201C1.75 9.884 2.181 10.493 2.825 10.72L3.754 11.048C3.856 11.309 3.972 11.567 4.117 11.817C4.262 12.067 4.427 12.297 4.602 12.517L4.421 13.485C4.296 14.156 4.608 14.834 5.199 15.175L5.55 15.378C6.142 15.72 6.884 15.651 7.403 15.207L8.148 14.569C8.707 14.655 9.28 14.655 9.849 14.569L10.595 15.208C11.114 15.652 11.857 15.721 12.448 15.379L12.799 15.176C13.391 14.834 13.702 14.157 13.577 13.486L13.397 12.52C13.756 12.071 14.043 11.575 14.248 11.047L15.173 10.721C15.817 10.494 16.248 9.885 16.248 9.202V8.797C16.248 8.114 15.817 7.505 15.173 7.278H15.175Z" />
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
  'text-[#57534E] hover:bg-zinc-950/5 hover:text-[#0C0A09]';

const navItemActive =
  'text-green-600 hover:bg-green-600/5';

/* ─── NavItem ────────────────────────────────────────────────────────────── */

function NavItem({
  icon: Icon,
  label,
  href,
  active = false,
  badge,
  collapsed = false,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  href: string;
  active?: boolean;
  badge?: string;
  collapsed?: boolean;
}) {
  return (
    <Link href={href} tabIndex={0} title={collapsed ? label : undefined}>
      <button
        type="button"
        className={cn(navItemBase, active ? navItemActive : navItemInactive)}
      >
        <div className="flex items-center gap-2">
          <Icon className="size-[18px] shrink-0" />
          {!collapsed && <p>{label}</p>}
          {!collapsed && badge && (
            <span className="inline-flex items-center font-medium bg-[#bbf7d0] text-[#15803d] gap-[3px] py-0.5 px-1.5 text-xs rounded-full">
              {badge}
            </span>
          )}
        </div>
      </button>
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
        className="flex items-center h-8 w-full px-2 rounded-[10px] border border-transparent bg-zinc-950/5 hover:bg-zinc-950/[0.07] transition-colors text-[#78716C]"
      >
        <div className="flex items-center gap-2">
          <IconSearch className="size-[18px] shrink-0" />
        </div>
      </button>
    );
  }
  return (
    <div className="flex items-center h-8 px-2 gap-2 rounded-[10px] border border-transparent bg-zinc-950/5 focus-within:bg-zinc-950/[0.07] transition-colors">
      <IconSearch className="size-[18px] shrink-0 text-[#78716C]" />
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => e.key === 'Escape' && onQueryChange('')}
        placeholder="Search..."
        className="flex-1 bg-transparent outline-none text-sm font-normal tracking-[-0.1px] text-[#57534E] placeholder:text-[#A8A29E] min-w-0"
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

function TailoringItem({
  tailoring,
  active,
  collapsed,
}: {
  tailoring: TailoringListItem;
  active: boolean;
  collapsed: boolean;
}) {
  const label = tailoringLabel(tailoring);
  const generating = tailoring.generation_status === 'generating';
  const Icon = generating
    ? ({ className }: { className?: string }) => <Loader2 className={cn(className, 'animate-spin')} />
    : IconWorkflows;

  if (collapsed) {
    return (
      <Link href={`/dashboard/tailorings/${tailoring.id}`} title={label}>
        <button
          type="button"
          className={cn(navItemBase, active ? navItemActive : navItemInactive)}
        >
          <div className="flex items-center gap-2">
            <Icon className="size-[18px] shrink-0" />
          </div>
        </button>
      </Link>
    );
  }

  return (
    <Link href={`/dashboard/tailorings/${tailoring.id}`}>
      <button
        type="button"
        className={cn(
          'flex items-center gap-2 w-full px-2 py-1.5 rounded-[10px] border border-transparent transition-colors text-left outline-none',
          active ? navItemActive : navItemInactive,
        )}
      >
        <Icon className="size-[18px] shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-normal tracking-[-0.1px] leading-5">{label}</p>
          {tailoring.company && (
            <p className="truncate text-xs text-[#A8A29E] leading-4 mt-0.5">{tailoring.company}</p>
          )}
        </div>
      </button>
    </Link>
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
            <ChevronsUpDown className="size-[14px] shrink-0 text-[#A8A29E]" strokeWidth={1.8} />
          )}
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        side="top"
        align="start"
        sideOffset={8}
        className="w-[220px] rounded-2xl p-1.5 bg-white border border-[#F5F5F4] shadow-lg"
      >
        {/* Name + email */}
        <div className="flex flex-col gap-0.5 px-2 py-2">
          <span className="text-sm font-medium text-[#0C0A09] leading-5 truncate">{displayName}</span>
          <span className="text-xs text-[#78716C] leading-4 truncate">{email}</span>
        </div>

        <DropdownMenuSeparator className="bg-[#F5F5F4] mx-1 my-1" />

        <DropdownMenuItem asChild className="rounded-xl gap-1.5 p-2 text-sm text-[#57534E] cursor-pointer focus:bg-zinc-950/5 focus:text-[#0C0A09]">
          <Link href="/dashboard/settings">
            <Settings className="size-4 text-[#78716C] shrink-0" strokeWidth={1.8} />
            <span>Settings</span>
          </Link>
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => setDarkMode(!darkMode)}
          className="rounded-xl gap-1.5 p-2 text-sm text-[#57534E] cursor-pointer focus:bg-zinc-950/5 focus:text-[#0C0A09]"
        >
          {darkMode
            ? <Sun className="size-4 text-[#78716C] shrink-0" strokeWidth={1.8} />
            : <Moon className="size-4 text-[#78716C] shrink-0" strokeWidth={1.8} />}
          <span>{darkMode ? 'Light mode' : 'Dark mode'}</span>
        </DropdownMenuItem>

        <DropdownMenuSeparator className="bg-[#F5F5F4] mx-1 my-1" />

        <DropdownMenuItem
          onClick={() => signOut({ callbackUrl: '/' })}
          className="rounded-xl gap-1.5 p-2 text-sm text-red-600 cursor-pointer focus:bg-red-50 focus:text-red-600"
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
      <div className="h-px bg-[#F5F5F4]" />
    </div>
  );
}

/* ─── Sidebar ────────────────────────────────────────────────────────────── */

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

export function SidebarMintlify({ tailorings = [] }: { tailorings?: TailoringListItem[] }) {
  const pathname = usePathname();
  const activeItem = getActiveItem(pathname);
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState('');

  const filteredTailorings = query.trim()
    ? tailorings.filter((t) => {
        const q = query.toLowerCase();
        return t.title?.toLowerCase().includes(q) || t.company?.toLowerCase().includes(q);
      })
    : tailorings;

  const w = collapsed ? '60px' : '240px';

  return (
    <aside
      className="hidden lg:flex flex-col bg-[#FAFAF9] border-r border-[#F5F5F4] transition-[width] duration-200 overflow-hidden shrink-0"
      style={{ width: w }}
    >
      <div className="flex grow flex-col overflow-hidden" style={{ width: w, minWidth: w }}>

        {/* Workspace header */}
        <div className="flex items-end pb-1.5 h-12 px-3 shrink-0">
          <Link
            href="/"
            className="flex items-center p-1.5 rounded-[10px] hover:bg-zinc-950/5 py-1.5 gap-1 px-[7px] outline-none transition-colors"
          >
            <img alt="Tailord logo" className="h-[22px] w-[22px] shrink-0" src="/logo.svg" />
            {!collapsed && (
              <span
                className="text-[#0C0A09] text-[16px] leading-none font-semibold tracking-tight whitespace-nowrap"
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
            <NavItem icon={IconHome}   label="Home"          href="/dashboard"           active={activeItem === 'Home'}          collapsed={collapsed} />
            <NavItem icon={IconEditor} label="My Experience" href="/dashboard/experience" active={activeItem === 'My Experience'} collapsed={collapsed} />
            <NavItem icon={(p) => <Globe {...p} size={18} strokeWidth={1.8} />} label="My Profile" href="/dashboard/profile" active={activeItem === 'My Profile'} collapsed={collapsed} />
          </nav>

          {/* Tailorings section header + controls */}
          <div className="flex flex-col gap-0.5">
            {collapsed ? (
              <div className="h-7 px-2 flex items-center">
                <div className="h-px w-full bg-[#F5F5F4]" />
              </div>
            ) : (
              <span className="px-2 py-1.5 font-medium text-xs text-[#78716C]">
                Tailorings
              </span>
            )}
            <NavItem icon={(p) => <Plus {...p} size={18} strokeWidth={1.8} />} label="New Tailoring" href="/dashboard/tailorings/new" active={activeItem === 'New Tailoring'} collapsed={collapsed} />
            <SearchBar collapsed={collapsed} onExpand={() => setCollapsed(false)} query={query} onQueryChange={setQuery} />
          </div>

        </div>

        {/* Scrollable tailorings list */}
        <div className="relative flex-1 min-h-0">
          <div className="h-full overflow-y-auto px-3 py-1">
            <div className="flex flex-col gap-0.5 pb-5">
              {collapsed ? (() => {
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
                      />
                    )}
                    {hasMore && (
                      <button
                        type="button"
                        onClick={() => setCollapsed(false)}
                        title="Show all tailorings"
                        className="flex items-center justify-center h-8 w-full rounded-[10px] border border-transparent text-[#A8A29E] hover:bg-zinc-950/5 hover:text-[#57534E] transition-colors"
                      >
                        <span className="text-sm leading-none tracking-widest">···</span>
                      </button>
                    )}
                  </>
                );
              })() : filteredTailorings.length === 0 && query ? (
                <p className="px-2 py-1.5 text-xs text-[#A8A29E]">No results</p>
              ) : filteredTailorings.map((t) => (
                <TailoringItem
                  key={t.id}
                  tailoring={t}
                  active={activeItem === t.id}
                  collapsed={false}
                />
              ))}
            </div>
          </div>
          {!collapsed && (
            <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-[#FAFAF9] to-transparent" />
          )}
        </div>

        {/* Sticky bottom — account + collapse */}
        <div className="shrink-0 px-3 pb-3">
          <div className="mb-2.5 px-2">
            <div className="h-px bg-[#F5F5F4]" />
          </div>
          <div className="flex flex-col gap-0.5">
            <AccountPopover collapsed={collapsed} />
          </div>
          <div className="mt-0.5" />
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className={cn(navItemBase, navItemInactive)}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            <div className="flex items-center gap-2">
              <IconCollapse className="size-[18px] shrink-0" />
              {!collapsed && <p>Collapse</p>}
            </div>
          </button>
        </div>

      </div>
    </aside>
  );
}
