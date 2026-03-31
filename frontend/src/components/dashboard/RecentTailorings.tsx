import Link from 'next/link';
import { Plus, FileText, ArrowRight } from 'lucide-react';
import type { TailoringListItem } from '@/types';

function tailoringLabel(t: TailoringListItem): string {
  if (t.title) return t.title;
  if (t.job_url) {
    try { return new URL(t.job_url).hostname.replace(/^www\./, ''); } catch {}
  }
  return 'Untitled';
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

interface RecentTailoringsProps {
  tailorings: TailoringListItem[];
}

export function RecentTailorings({ tailorings }: RecentTailoringsProps) {
  const recent = tailorings.slice(0, 6);

  return (
    <div className="max-w-3xl mx-auto px-8 py-10">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-[15px] font-semibold text-text-primary tracking-tight">Recent tailorings</h2>
        <Link
          href="/dashboard/tailorings/new"
          className="inline-flex items-center gap-1.5 h-7 px-3 rounded-full text-[12px] font-medium bg-text-primary text-surface-base hover:opacity-90 transition-opacity"
        >
          <Plus className="h-3 w-3" />
          New tailoring
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {recent.map((t) => (
          <Link
            key={t.id}
            href={`/dashboard/tailorings/${t.id}`}
            className="group flex items-start gap-3 p-3.5 rounded-[10px] bg-surface-elevated border border-black/5 dark:border-white/5 hover:border-black/10 dark:hover:border-white/10 hover:shadow-sm transition-all"
          >
            <div className="h-7 w-7 rounded-[8px] bg-brand-accent-subtle flex items-center justify-center flex-shrink-0 mt-0.5">
              <FileText className="h-3.5 w-3.5 text-brand-accent" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium text-text-primary truncate leading-tight">{tailoringLabel(t)}</p>
              {t.company && (
                <p className="text-[12px] text-text-secondary truncate mt-0.5">{t.company}</p>
              )}
              <p className="text-[11px] text-text-tertiary mt-1">{formatDate(t.created_at)}</p>
            </div>
            <ArrowRight className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0 mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>
        ))}
      </div>
    </div>
  );
}
