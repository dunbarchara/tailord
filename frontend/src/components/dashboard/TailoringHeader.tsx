import Link from 'next/link';
import { cn } from '@/lib/utils';

interface TailoringHeaderProps {
  company: string | null;
  title: string | null;
  jobUrl?: string | null;
  authorName?: string | null;
  authorUrl?: string | null;
  className?: string;
}

export function TailoringHeader({ company, title, jobUrl, authorName, authorUrl, className }: TailoringHeaderProps) {
  const hasSubtitle = company || authorName;

  return (
    <header className={cn('pb-5 border-b border-border-subtle', className)}>
      {hasSubtitle && (
        <p className="text-xs font-medium uppercase tracking-wider mb-1">
          {company && <span className="text-text-tertiary">{company}</span>}
          {company && authorName && <span className="text-text-tertiary"> · </span>}
          {authorName && authorUrl ? (
            <Link href={authorUrl} className="text-text-tertiary hover:text-text-primary hover:underline">{authorName} <span className="text-text-disabled">→</span></Link>
          ) : authorName ? (
            <span className="text-text-secondary">{authorName}</span>
          ) : null}
        </p>
      )}
      <h1 className="text-xl font-semibold text-text-primary">
        {title ?? ''}
      </h1>
      {jobUrl && (
        <a
          href={jobUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-2 text-sm text-text-link hover:underline print:hidden"
        >
          View job posting →
        </a>
      )}
    </header>
  );
}
