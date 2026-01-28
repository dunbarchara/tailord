'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ChevronLeft,
  ChevronRight,
  Home,
  Briefcase,
  Plus,
  FileText,
  Settings,
  User,
  Menu,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

// Mock data for tailorings - in production, this would come from an API
const mockTailorings = [
  { id: '1', title: 'Senior Frontend Engineer at TechCorp', date: '2 days ago' },
  { id: '2', title: 'Product Designer at StartupXYZ', date: '5 days ago' },
  { id: '3', title: 'Full Stack Developer at MegaCorp', date: '1 week ago' },
  { id: '4', title: 'UX Researcher at DesignCo', date: '2 weeks ago' },
];

export function Sidebar({ collapsed, onToggleCollapse }: SidebarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    { href: '/dashboard/experience', icon: Briefcase, label: 'My Experience' },
    { href: '/dashboard/tailorings/new', icon: Plus, label: 'New Tailoring' },
  ];

  const isActive = (href: string) => pathname === href || pathname?.startsWith(href);

  const SidebarContent = () => (
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
            <span className="text-lg font-semibold text-text-primary truncate">
              Tailord
            </span>
          )}
        </Link>
        
        {!collapsed && (
          <button
            onClick={onToggleCollapse}
            className="ml-auto p-1.5 rounded-md hover:bg-surface-overlay transition-colors flex-shrink-0"
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4 text-text-secondary" />
          </button>
        )}
      </div>

      {/* Collapsed toggle when sidebar is collapsed */}
      {collapsed && (
        <div className="px-2 py-3 border-b border-border-subtle">
          <button
            onClick={onToggleCollapse}
            className="w-full p-2 rounded-md hover:bg-surface-overlay transition-colors"
            aria-label="Expand sidebar"
          >
            <ChevronRight className="h-4 w-4 text-text-secondary mx-auto" />
          </button>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-1">
        {/* Main nav items */}
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group',
                active
                  ? 'bg-surface-overlay text-text-primary'
                  : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary',
                collapsed && 'justify-center px-2'
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={cn(
                'h-5 w-5 flex-shrink-0',
                active ? 'text-brand-primary' : 'text-text-tertiary group-hover:text-text-secondary'
              )} />
              {!collapsed && (
                <span className="text-sm font-medium truncate">{item.label}</span>
              )}
            </Link>
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
              {mockTailorings.map((tailoring) => {
                const active = pathname === `/dashboard/tailorings/${tailoring.id}`;
                
                return (
                  <Link
                    key={tailoring.id}
                    href={`/dashboard/tailorings/${tailoring.id}`}
                    className={cn(
                      'block px-3 py-2 rounded-lg transition-colors group',
                      active
                        ? 'bg-surface-overlay'
                        : 'hover:bg-surface-overlay'
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
                          {tailoring.title}
                        </p>
                        <p className="text-xs text-text-tertiary mt-0.5">
                          {tailoring.date}
                        </p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {collapsed && (
          <div className="space-y-1 pt-6">
            {mockTailorings.slice(0, 3).map((tailoring) => {
              const active = pathname === `/dashboard/tailorings/${tailoring.id}`;
              
              return (
                <Link
                  key={tailoring.id}
                  href={`/dashboard/tailorings/${tailoring.id}`}
                  className={cn(
                    'flex items-center justify-center p-2 rounded-lg transition-colors',
                    active
                      ? 'bg-surface-overlay'
                      : 'hover:bg-surface-overlay'
                  )}
                  title={tailoring.title}
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
      <div className="border-t border-border-subtle p-3 space-y-1">
        <Link
          href="/dashboard/settings"
          className={cn(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors group',
            pathname === '/settings'
              ? 'bg-surface-overlay text-text-primary'
              : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? 'Settings' : undefined}
        >
          <Settings className={cn(
            'h-5 w-5 flex-shrink-0',
            pathname === '/settings' ? 'text-brand-primary' : 'text-text-tertiary'
          )} />
          {!collapsed && (
            <span className="text-sm font-medium">Settings</span>
          )}
        </Link>

        {!collapsed && (
          <button
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-secondary hover:bg-surface-overlay hover:text-text-primary transition-colors group"
          >
            <User className="h-5 w-5 flex-shrink-0 text-text-tertiary" />
            <div className="flex-1 text-left min-w-0">
              <p className="text-sm font-medium truncate">John Doe</p>
              <p className="text-xs text-text-tertiary truncate">john@example.com</p>
            </div>
          </button>
        )}
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden lg:flex flex-col bg-surface-elevated border-r border-border-subtle transition-all duration-300',
          collapsed ? 'w-20' : 'w-72'
        )}
      >
        <SidebarContent />
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
          {/* Backdrop */}
          <div
            className="lg:hidden fixed inset-0 bg-black/50 z-40 animate-fade-in"
            onClick={() => setMobileOpen(false)}
          />
          
          {/* Sidebar */}
          <aside className="lg:hidden fixed inset-y-0 left-0 z-50 w-72 bg-surface-elevated border-r border-border-subtle flex flex-col animate-slide-in-left">
            <SidebarContent />
          </aside>
        </>
      )}
    </>
  );
}
