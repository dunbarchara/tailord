import Link from 'next/link';
import { Plus, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
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
  const recent = tailorings.slice(0, 5);

  return (
    <div className="max-w-3xl mx-auto px-8 py-12">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-text-primary">Recent tailorings</h2>
        <Button asChild size="sm">
          <Link href="/dashboard/tailorings/new">
            <Plus className="h-4 w-4 mr-1.5" />
            New tailoring
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {recent.map((t) => (
          <Link
            key={t.id}
            href={`/dashboard/tailorings/${t.id}`}
            className="flex items-start gap-3 p-4 rounded-lg bg-surface-elevated border border-border-default hover:border-border-strong transition-colors"
          >
            <FileText className="h-4 w-4 mt-0.5 flex-shrink-0 text-text-tertiary" />
            <div className="min-w-0">
              <p className="font-medium text-text-primary truncate">{tailoringLabel(t)}</p>
              {t.company && (
                <p className="text-sm text-text-secondary truncate mt-0.5">{t.company}</p>
              )}
              <p className="text-xs text-text-tertiary mt-1">{formatDate(t.created_at)}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
