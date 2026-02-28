'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useSession, signOut } from 'next-auth/react';
import { useTheme } from '@/components/ThemeProvider';
import {
  Briefcase,
  Plus,
  FileText,
  Settings,
  Moon,
  Sun,
  Menu,
  X,
  LogOut,
  ChevronsUpDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import type { TailoringListItem } from '@/types';

interface SidebarProps {
  tailorings?: TailoringListItem[];
}

interface SidebarContentProps {
  tailorings: TailoringListItem[];
  pathname: string | null;
}

const navItems = [
  { href: '/dashboard/experience', icon: Briefcase, label: 'My Experience' },
];

function SidebarContent({ tailorings, pathname }: SidebarContentProps) {
  const { darkMode, setDarkMode } = useTheme();
  const { data: session } = useSession();

  const isActive = (href: string) => pathname === href || Boolean(pathname?.startsWith(href));

  const userInitials = session?.user?.name
    ? session.user.name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : '??';

  return (
    <div className="flex flex-col h-full">
      {/* Brand */}
      <div className="px-4 py-5">
        <Link href="/" className="flex items-center gap-2 group">
          <img src="/logo.svg" alt="Tailord logo" className="h-8 w-8 dark:invert" />
          <span className="text-xl font-display text-text-primary">Tailord</span>
        </Link>
      </div>

      {/* New Tailoring */}
      <div className="px-3 pb-3">
        <Button asChild variant="outline" size="sm" className="w-full justify-start gap-2">
          <Link href="/dashboard/tailorings/new">
            <Plus className="h-4 w-4" />
            New Tailoring
          </Link>
        </Button>
      </div>

      {/* Nav items */}
      <nav className="px-3 pb-4 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Button
              key={item.href}
              variant={active ? 'secondary' : 'ghost'}
              size="sm"
              className="w-full justify-start gap-2"
              asChild
            >
              <Link href={item.href}>
                <Icon className="h-4 w-4 flex-shrink-0" />
                {item.label}
              </Link>
            </Button>
          );
        })}
      </nav>

      {/* Tailorings list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-3">
        <p className="text-xs font-medium text-text-tertiary px-2 mb-2 uppercase tracking-wider">
          Tailorings
        </p>
        {tailorings.length === 0 ? (
          <p className="px-2 py-1.5 text-xs text-text-tertiary">No tailorings yet</p>
        ) : (
          <div className="space-y-0.5">
            {tailorings.map((tailoring) => {
              const active = pathname === `/dashboard/tailorings/${tailoring.id}`;
              return (
                <Link
                  key={tailoring.id}
                  href={`/dashboard/tailorings/${tailoring.id}`}
                  className={cn(
                    'flex items-start gap-2 px-2 py-2 rounded-md text-sm transition-colors',
                    active
                      ? 'bg-surface-overlay text-text-primary'
                      : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
                  )}
                >
                  <FileText className="h-4 w-4 mt-0.5 flex-shrink-0 text-text-tertiary" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium leading-tight">{tailoring.title ?? 'Untitled'}</p>
                    <p className="truncate text-xs text-text-tertiary mt-0.5">{tailoring.company ?? ''}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom section */}
      <div className="px-3 pt-3 pb-3 border-t border-border-subtle">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="w-full flex items-center gap-3 px-2 py-2 rounded-md hover:bg-surface-overlay transition-colors text-left">
              <Avatar className="h-7 w-7 flex-shrink-0">
                <AvatarImage src={session?.user?.image ?? undefined} alt={session?.user?.name ?? ''} />
                <AvatarFallback className="text-xs bg-brand-primary/10 text-brand-primary">
                  {userInitials}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text-primary truncate leading-tight">
                  {session?.user?.name ?? 'Account'}
                </p>
                <p className="text-xs text-text-tertiary truncate">
                  {session?.user?.email ?? ''}
                </p>
              </div>
              <ChevronsUpDown className="h-4 w-4 text-text-tertiary flex-shrink-0" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" sideOffset={8} className="w-56">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">{session?.user?.name ?? 'Account'}</p>
                <p className="text-xs leading-none text-muted-foreground">{session?.user?.email ?? ''}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild className="cursor-pointer">
              <Link href="/dashboard/settings">
                <Settings className="mr-2 h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setDarkMode(!darkMode)} className="cursor-pointer">
              {darkMode ? <Sun className="mr-2 h-4 w-4" /> : <Moon className="mr-2 h-4 w-4" />}
              {darkMode ? 'Light mode' : 'Dark mode'}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="cursor-pointer text-destructive focus:text-destructive"
              onClick={() => signOut({ callbackUrl: '/' })}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

export function Sidebar({ tailorings = [] }: SidebarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const contentProps = { tailorings, pathname };

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-64 bg-surface-elevated border-r border-border-subtle">
        <SidebarContent {...contentProps} />
      </aside>

      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-surface-elevated border border-border-subtle shadow-md"
        aria-label="Toggle menu"
      >
        {mobileOpen ? (
          <X className="h-5 w-5 text-text-primary" />
        ) : (
          <Menu className="h-5 w-5 text-text-primary" />
        )}
      </button>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <>
          <div
            className="lg:hidden fixed inset-0 bg-black/50 z-40 animate-fade-in"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="lg:hidden fixed inset-y-0 left-0 z-50 w-64 bg-surface-elevated border-r border-border-subtle flex flex-col">
            <SidebarContent {...contentProps} />
          </aside>
        </>
      )}
    </>
  );
}
