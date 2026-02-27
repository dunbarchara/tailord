'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ChevronLeft,
  ChevronRight,
  Briefcase,
  Plus,
  FileText,
  Settings,
  Menu,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import type { Tailoring } from '@/types';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  tailorings?: Pick<Tailoring, 'id' | 'jobTitle' | 'company'>[];
}

interface SidebarContentProps extends SidebarProps {
  pathname: string | null;
}

const navItems = [
  { href: '/dashboard/experience', icon: Briefcase, label: 'My Experience' },
  { href: '/dashboard/tailorings/new', icon: Plus, label: 'New Tailoring' },
];

function SidebarContent({ collapsed, onToggleCollapse, tailorings = [], pathname }: SidebarContentProps) {
  const isActive = (href: string) => pathname === href || Boolean(pathname?.startsWith(href));

  return (
    <>
      {/* Header with branding */}
      <div className={cn(
        'flex items-center gap-3 px-4 py-5 border-b border-border-subtle',
        collapsed && 'justify-center px-2'
      )}>
        <Link href="/" className="flex items-center gap-2 group min-w-0">
          <div className="h-8 w-8 rounded-lg bg-brand-primary flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-105">
            <span className="text-text-inverse font-semibold text-sm">T</span>
          </div>
          {!collapsed && (
            <span className="text-lg font-semibold text-text-primary truncate">Tailord</span>
          )}
        </Link>

        {!collapsed && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            className="ml-auto flex-shrink-0"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        )}
      </div>

      {collapsed && (
        <div className="px-2 py-3 border-b border-border-subtle">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            className="w-full"
            aria-label="Expand sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);

          return (
            <Button
              key={item.href}
              variant={active ? 'secondary' : 'ghost'}
              className={cn('w-full justify-start gap-3', collapsed && 'justify-center px-2')}
              asChild
              title={collapsed ? item.label : undefined}
            >
              <Link href={item.href}>
                <Icon className={cn(
                  'h-5 w-5 flex-shrink-0',
                  active ? 'text-brand-primary' : 'text-text-tertiary'
                )} />
                {!collapsed && <span className="text-sm font-medium truncate">{item.label}</span>}
              </Link>
            </Button>
          );
        })}

        {/* Your Tailorings section */}
        {!collapsed && (
          <div className="pt-6">
            <div className="px-3 mb-2">
              <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">
                Your Tailorings
              </h3>
            </div>
            <div className="space-y-1">
              {tailorings.length === 0 ? (
                <p className="px-3 py-2 text-xs text-text-tertiary">No tailorings yet</p>
              ) : (
                tailorings.map((tailoring) => {
                  const active = pathname === `/dashboard/tailorings/${tailoring.id}`;
                  return (
                    <Link
                      key={tailoring.id}
                      href={`/dashboard/tailorings/${tailoring.id}`}
                      className={cn(
                        'block px-3 py-2 rounded-lg transition-colors',
                        active ? 'bg-surface-overlay' : 'hover:bg-surface-overlay'
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <FileText className={cn(
                          'h-4 w-4 mt-0.5 flex-shrink-0',
                          active ? 'text-brand-primary' : 'text-text-tertiary'
                        )} />
                        <div className="min-w-0 flex-1">
                          <p className={cn(
                            'text-sm font-medium truncate',
                            active ? 'text-text-primary' : 'text-text-secondary'
                          )}>
                            {tailoring.jobTitle}
                          </p>
                          <p className="text-xs text-text-tertiary mt-0.5">{tailoring.company}</p>
                        </div>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </div>
        )}

        {collapsed && tailorings.length > 0 && (
          <div className="space-y-1 pt-6">
            {tailorings.slice(0, 3).map((tailoring) => {
              const active = pathname === `/dashboard/tailorings/${tailoring.id}`;
              return (
                <Link
                  key={tailoring.id}
                  href={`/dashboard/tailorings/${tailoring.id}`}
                  className={cn(
                    'flex items-center justify-center p-2 rounded-lg transition-colors',
                    active ? 'bg-surface-overlay' : 'hover:bg-surface-overlay'
                  )}
                  title={tailoring.jobTitle}
                >
                  <FileText className={cn(
                    'h-5 w-5',
                    active ? 'text-brand-primary' : 'text-text-tertiary'
                  )} />
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* Bottom section - Settings */}
      <div className="border-t border-border-subtle p-3">
        <Button
          variant={pathname === '/dashboard/settings' ? 'secondary' : 'ghost'}
          className={cn('w-full justify-start gap-3', collapsed && 'justify-center px-2')}
          asChild
          title={collapsed ? 'Settings' : undefined}
        >
          <Link href="/dashboard/settings">
            <Settings className="h-5 w-5 flex-shrink-0 text-text-tertiary" />
            {!collapsed && <span className="text-sm font-medium">Settings</span>}
          </Link>
        </Button>
      </div>
    </>
  );
}

export function Sidebar({ collapsed, onToggleCollapse, tailorings = [] }: SidebarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const contentProps = { collapsed, onToggleCollapse, tailorings, pathname };

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden lg:flex flex-col bg-surface-elevated border-r border-border-subtle transition-all duration-300',
          collapsed ? 'w-20' : 'w-72'
        )}
      >
        <SidebarContent {...contentProps} />
      </aside>

      {/* Mobile menu button */}
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
          <aside className="lg:hidden fixed inset-y-0 left-0 z-50 w-72 bg-surface-elevated border-r border-border-subtle flex flex-col">
            <SidebarContent {...contentProps} />
          </aside>
        </>
      )}
    </>
  );
}
