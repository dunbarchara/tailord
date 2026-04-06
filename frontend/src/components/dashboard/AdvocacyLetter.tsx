'use client';

import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import { TailoringHeader } from '@/components/dashboard/TailoringHeader';
import type { Tailoring } from '@/types';

interface AdvocacyLetterProps {
  tailoring: Tailoring;
  authorName?: string | null;
}

export function AdvocacyLetter({ tailoring, authorName }: AdvocacyLetterProps) {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <TailoringHeader
        company={tailoring.company}
        title={tailoring.title}
        jobUrl={tailoring.job_url}
        authorName={authorName}
        className="mb-8"
      />
      {tailoring.generated_output && (
        <div className={cn(
          'prose prose-sm max-w-none text-text-primary',
          'prose-headings:text-text-primary prose-headings:font-semibold',
          'prose-p:text-text-secondary prose-p:leading-relaxed',
          'prose-hr:my-6',
          'prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs',
          'prose-strong:text-text-primary',
          'prose-hr:border-border-subtle',
          'prose-a:text-text-link prose-a:underline prose-a:underline-offset-2',
        )}>
          <ReactMarkdown>{tailoring.generated_output}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
