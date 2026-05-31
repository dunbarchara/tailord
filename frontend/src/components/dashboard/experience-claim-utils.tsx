import { Briefcase, Box, GitBranch, GraduationCap, Sparkles, Layers, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ExperienceClaim, ExperienceGroup } from '@/types';

/* ─── Group ordering ─────────────────────────────────────────────────────── */

export const GROUP_TYPE_ORDER: Record<string, number> = {
  role: 0, repository: 1, project: 2, education: 3, custom: 4,
};

const _MONTH_ABBR: Record<string, string> = {
  jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06',
  jul: '07', aug: '08', sep: '09', oct: '10', nov: '11', dec: '12',
};

/** Parse partial date strings (YYYY, YYYY-MM, YYYY-MM-DD, "Mon YYYY") to ms. */
export function parseDateMs(d: string | null | undefined): number | null {
  if (!d) return null;
  const s = d.trim();
  let normalized = s;
  if (/^\d{4}$/.test(s)) {
    normalized = `${s}-01-01`;
  } else if (/^\d{4}-\d{2}$/.test(s)) {
    normalized = `${s}-01`;
  } else {
    // Legacy stored values like "Jan 2020" from pre-ISO chunker
    const m = s.match(/^([A-Za-z]{3})\s+(\d{4})$/);
    if (m) {
      const mo = _MONTH_ABBR[m[1].toLowerCase()];
      if (mo) normalized = `${m[2]}-${mo}-01`;
    }
  }
  const ms = new Date(normalized).getTime();
  return isNaN(ms) ? null : ms;
}

/**
 * Sort groups by: type order → end_date desc (null = ongoing = first) →
 * start_date desc → name alphabetically.
 */
export function sortGroups(groups: ExperienceGroup[]): ExperienceGroup[] {
  return [...groups].sort((a, b) => {
    const typeA = GROUP_TYPE_ORDER[a.group_type] ?? 5;
    const typeB = GROUP_TYPE_ORDER[b.group_type] ?? 5;
    if (typeA !== typeB) return typeA - typeB;

    // null end_date = ongoing = sort first
    const aEnd = parseDateMs(a.end_date) ?? Infinity;
    const bEnd = parseDateMs(b.end_date) ?? Infinity;
    if (aEnd !== bEnd) return bEnd - aEnd;

    const aStart = parseDateMs(a.start_date) ?? 0;
    const bStart = parseDateMs(b.start_date) ?? 0;
    if (aStart !== bStart) return bStart - aStart;

    return a.name.localeCompare(b.name);
  });
}

/**
 * Sort claims by updated_at descending (most recently added/edited first).
 */
export function sortClaims(claims: ExperienceClaim[]): ExperienceClaim[] {
  return [...claims].sort((a, b) => {
    const aTime = a.updated_at ? new Date(a.updated_at).getTime() : 0;
    const bTime = b.updated_at ? new Date(b.updated_at).getTime() : 0;
    return bTime - aTime;
  });
}

/* ─── Source labels & dots ──────────────────────────────────────────────── */

export const SOURCE_LABELS: Record<string, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct',
  gap_response: 'Response',
  partial_response: 'Response',
  additional_experience: 'Direct',
};

export const SOURCE_DOT_CLS: Record<string, string> = {
  resume: 'bg-blue-400',
  github: 'bg-zinc-800 dark:bg-zinc-200',
  user_input: 'bg-zinc-400',
  gap_response: 'bg-violet-400',
  partial_response: 'bg-violet-400',
  additional_experience: 'bg-zinc-400',
};

/* ─── Content normalizer ─────────────────────────────────────────────────── */

export function normalizeContent(s: string): string {
  return s.replace(/\s*\n\s*/g, ' ').replace(/  +/g, ' ').trim();
}

/* ─── Icons ──────────────────────────────────────────────────────────────── */

export function ThreeDashIcon({ className }: { className?: string }) {
  return (
    <svg
      width="16" height="16" viewBox="0 0 16 16"
      fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M2 8 h2.5 M6.75 8 h2.5 M11.5 8 h2.5" />
    </svg>
  );
}

export function DashedSquareIcon({ className }: { className?: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={className} aria-hidden="true">
      <rect
        x="2.5" y="2.5" width="11" height="11" rx="2.5"
        stroke="currentColor" strokeWidth="1.2" strokeDasharray="2.4 2.4"
      />
    </svg>
  );
}

export function ClaimTypeIcon({ type, className }: { type: ExperienceClaim['claim_type']; className?: string }) {
  const cls = cn('h-3.5 w-3.5', className);
  switch (type) {
    case 'work_experience': return <Briefcase className={cls} />;
    case 'skill':           return <Layers className={cls} />;
    case 'project':         return <Box className={cls} />;
    case 'education':       return <GraduationCap className={cls} />;
    default:                return <FileText className={cls} />;
  }
}

export function GroupTypeIcon({ type, className }: { type: ExperienceGroup['group_type'] | 'ungrouped'; className?: string }) {
  const cls = cn('h-4 w-4', className);
  switch (type) {
    case 'role':       return <Briefcase className={cls} />;
    case 'project':    return <Box className={cls} />;
    case 'repository': return <GitBranch className={cls} />;
    case 'education':  return <GraduationCap className={cls} />;
    case 'custom':     return <Sparkles className={cls} />;
    default:           return <DashedSquareIcon className={cls} />;
  }
}
