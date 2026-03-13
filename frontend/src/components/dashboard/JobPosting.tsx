'use client';

import { Loader2 } from 'lucide-react';
import type { ChunksResponse, JobChunk } from '@/types';

interface JobPostingProps {
  data: ChunksResponse | null;
  error: string | null;
  title: string | null;
  company: string | null;
  jobUrl: string | null;
}

function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '').replace(/\*/g, '').trim();
}

function groupBySection(chunks: JobChunk[]): Map<string, JobChunk[]> {
  const groups = new Map<string, JobChunk[]>();
  for (const chunk of chunks) {
    if (chunk.chunk_type === 'header') continue;
    if (chunk.section === null) continue; // skip job board chrome (logo, nav, etc.)
    const key = chunk.section;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(chunk);
  }
  return groups;
}

function SectionBlock({ section, chunks }: { section: string; chunks: JobChunk[] }) {
  const bullets = chunks.filter(c => c.chunk_type === 'bullet');
  const paragraphs = chunks.filter(c => c.chunk_type === 'paragraph');

  return (
    <div className="mb-6">
      <h2 className="text-sm font-semibold text-text-primary mb-3 pb-1 border-b border-border-subtle">
        {stripMarkdown(section)}
      </h2>
      {paragraphs.map(chunk => (
        <p key={chunk.id} className="text-sm text-text-secondary leading-relaxed mb-2">
          {chunk.content}
        </p>
      ))}
      {bullets.length > 0 && (
        <ul className="space-y-1.5">
          {bullets.map(chunk => (
            <li key={chunk.id} className="flex gap-2 text-sm text-text-secondary leading-relaxed">
              <span className="text-text-tertiary flex-shrink-0 mt-0.5">·</span>
              <span>{chunk.content}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function JobPosting({ data, error, title, company, jobUrl }: JobPostingProps) {
  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-8 py-10 text-sm text-text-secondary">
        Could not load job posting data.
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading…
      </div>
    );
  }

  const groups = groupBySection(data.chunks);

  return (
    <div className="max-w-3xl mx-auto px-8 py-10">
      {/* Header — matches Letter/public page style */}
      <header className="mb-8 pb-5 border-b border-border-subtle">
        <p className="text-xs font-medium uppercase tracking-wider text-text-tertiary mb-1">
          {company ?? 'Company'}
        </p>
        <h1 className="text-xl font-semibold text-text-primary">
          {title ?? 'Job Posting'}
        </h1>
        {jobUrl && (
          <a
            href={jobUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-2 text-sm text-text-link hover:underline"
          >
            View job posting →
          </a>
        )}
      </header>

      {/* Sections */}
      {groups.size === 0 ? (
        <p className="text-sm text-text-tertiary italic">No job posting data available.</p>
      ) : (
        Array.from(groups.entries()).map(([section, chunks]) => (
          <SectionBlock key={section} section={section} chunks={chunks} />
        ))
      )}
    </div>
  );
}
