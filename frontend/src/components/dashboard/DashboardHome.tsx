'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Plus, Globe, Lock, Loader2, AlertCircle, ChevronRight,
} from 'lucide-react';
import type { TailoringListItem } from '@/types';
import { IconCheck, IconWorkflows } from '@/components/ui/icons';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function buildGreeting(displayName: string | null): string {
  const hour = new Date().getHours();
  const period = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening';
  const firstName = displayName?.split(' ')[0] ?? null;
  return `Good ${period}${firstName ? `, ${firstName}` : ''}`;
}

function tailoringLabel(t: TailoringListItem): string {
  if (t.title) return t.title;
  if (t.job_url) {
    try { return new URL(t.job_url).hostname.replace(/^www\./, ''); } catch {}
  }
  return 'Untitled';
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  const diffDays = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

/* ─── Status badge ───────────────────────────────────────────────────────── */

function StatusBadge({ status }: { status: TailoringListItem['generation_status'] }) {
  if (status === 'ready') {
    return (
      <span className="inline-flex items-center gap-1 py-0.5 px-1.5 rounded-md text-xs font-medium bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400">
        <IconCheck />
        Ready
      </span>
    );
  }
  if (status === 'generating') {
    return (
      <span className="inline-flex items-center gap-1 py-0.5 px-1.5 rounded-md text-xs font-medium bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400">
        <Loader2 className="h-2.5 w-2.5 animate-spin" />
        Generating
      </span>
    );
  }
  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 py-0.5 px-1.5 rounded-md text-xs font-medium bg-red-100 dark:bg-red-950/20 text-red-600 dark:text-red-400">
        <AlertCircle className="h-2.5 w-2.5" />
        Failed
      </span>
    );
  }
  // pending
  return (
    <span className="inline-flex items-center gap-1 py-0.5 px-1.5 rounded-md text-xs font-medium bg-surface-overlay text-text-tertiary">
      Pending
    </span>
  );
}

/* ─── Visibility badge ───────────────────────────────────────────────────── */

function VisibilityBadge({ isPublic }: { isPublic: boolean }) {
  if (isPublic) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-700 dark:text-green-400">
        <Globe className="h-3 w-3" />
        Public
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-text-disabled">
      <Lock className="h-3 w-3" />
      Private
    </span>
  );
}

/* ─── Component ─────────────────────────────────────────────────────────── */

interface DashboardHomeProps {
  name: string | null;
  tailorings: TailoringListItem[];
}

export function DashboardHome({ name, tailorings }: DashboardHomeProps) {
  const router = useRouter();
  const isEmpty = tailorings.length === 0;
  const [displayName, setDisplayName] = useState<string | null>(name);
  const [greeting, setGreeting] = useState('');

  useEffect(() => {
    setGreeting(buildGreeting(displayName));
  }, [displayName]);

  useEffect(() => {
    function onNameChanged(e: Event) {
      const { firstName, lastName } = (e as CustomEvent).detail;
      const n = [firstName, lastName].filter(Boolean).join(' ');
      setDisplayName(n || name);
    }
    window.addEventListener('preferred-name-changed', onNameChanged);
    return () => window.removeEventListener('preferred-name-changed', onNameChanged);
  }, [name]);

  return (
    <div className="h-full flex flex-col bg-surface-elevated">
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="max-w-6xl mx-auto px-6 lg:px-16 pt-12 pb-24">

          {/* ── Greeting ───────────────────────────────────────────────── */}
          <div className="flex flex-col gap-1 pb-8 border-b border-zinc-950/5 dark:border-white/5">
            <h2
              suppressHydrationWarning
              className="text-lg font-medium text-text-primary tracking-[-0.2px]"
            >
              {greeting}
            </h2>
            <p className="text-sm text-text-secondary">Welcome back to Tailord</p>
          </div>

          {/* ── Empty state ─────────────────────────────────────────────── */}
          {isEmpty && (
            <div className="mt-20 flex flex-col items-center text-center gap-5">
              <div className="h-10 w-10 rounded-2xl bg-surface-overlay flex items-center justify-center">
                <IconWorkflows className="h-[18px] w-[18px] text-text-tertiary" />
              </div>
              <div className="space-y-1 max-w-xs">
                <p className="text-sm font-medium text-text-primary">No tailorings yet</p>
                <p className="text-sm text-text-secondary leading-relaxed">
                  Add your experience, then paste a job URL to generate your first tailoring.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Link
                  href="/dashboard/experience"
                  className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] border border-border-default bg-surface-elevated text-text-secondary hover:bg-surface-base hover:border-border-strong hover:text-text-primary transition-colors"
                >
                  Add Experience
                </Link>
                <Link
                  href="/dashboard/tailorings/new"
                  className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 transition-opacity"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New Tailoring
                </Link>
              </div>
            </div>
          )}

          {/* ── Tailorings table ────────────────────────────────────────── */}
          {!isEmpty && (
            <div className="mt-8">

              {/* Section header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-medium text-text-primary">Your Tailorings</h3>
                  <p className="text-sm text-text-secondary mt-0.5">
                    {tailorings.length} tailoring{tailorings.length !== 1 ? 's' : ''} generated
                  </p>
                </div>
                <Link
                  href="/dashboard/tailorings/new"
                  className="inline-flex items-center gap-1.5 h-9 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 transition-opacity shrink-0"
                >
                  <Plus className="h-4 w-4" />
                  New Tailoring
                </Link>
              </div>

              {/* Table */}
              <div className="rounded-2xl overflow-hidden border border-border-subtle overflow-x-auto">
                <table className="w-full min-w-[480px] table-fixed text-sm">
                  <thead>
                    <tr className="bg-surface-base border-b border-border-subtle">
                      <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[55%]">
                        Role
                      </th>
                      <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[15%]">
                        Status
                      </th>
                      <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[15%]">
                        Visibility
                      </th>
                      <th className="px-4 h-9 text-left text-xs font-medium text-text-tertiary tracking-wider w-[15%]">
                        Created
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {tailorings.map((t) => {
                      const label = tailoringLabel(t);
                      return (
                        <tr
                          key={t.id}
                          onClick={() => router.push(`/dashboard/tailorings/${t.id}`)}
                          className="bg-surface-elevated border-t border-border-subtle hover:bg-surface-base transition-colors cursor-pointer group"
                        >
                          {/* Role + company */}
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-3">
                              <div className="h-7 w-7 rounded-[8px] bg-surface-overlay flex items-center justify-center shrink-0">
                                <IconWorkflows className="h-[14px] w-[14px] text-text-tertiary" />
                              </div>
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-text-primary truncate">{label}</p>
                                {t.company && (
                                  <p className="text-xs text-text-tertiary truncate mt-0.5">{t.company}</p>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Status */}
                          <td className="px-4 py-3.5">
                            <StatusBadge status={t.generation_status} />
                          </td>

                          {/* Visibility */}
                          <td className="px-4 py-3.5">
                            <VisibilityBadge isPublic={t.is_public} />
                          </td>

                          {/* Date + chevron */}
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-2">
                              <span
                                suppressHydrationWarning
                                className="text-xs text-text-tertiary whitespace-nowrap"
                              >
                                {formatRelativeDate(t.created_at)}
                              </span>
                              <ChevronRight className="h-3.5 w-3.5 text-text-disabled opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

            </div>
          )}

        </div>
      </div>
    </div>
  );
}
