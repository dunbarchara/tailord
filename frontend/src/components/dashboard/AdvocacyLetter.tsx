'use client';

import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import { TailoringHeader } from '@/components/dashboard/TailoringHeader';
import type { Tailoring, AdvocacyStatement } from '@/types';

interface AdvocacyLetterProps {
  tailoring: Tailoring;
  authorName?: string | null;
}

const proseCls = cn(
  'prose prose-sm max-w-none text-text-primary',
  'prose-headings:text-text-primary prose-headings:font-semibold',
  'prose-p:text-text-secondary prose-p:leading-relaxed',
  'prose-hr:my-6',
  'prose-em:text-text-tertiary prose-em:not-italic prose-em:text-xs',
  'prose-strong:text-text-primary',
  'prose-hr:border-border-subtle',
  'prose-a:text-text-link prose-a:underline prose-a:underline-offset-2',
);

function SourceTags({ sources }: { sources: string[] }) {
  if (!sources.length) return null;
  return (
    <span className="text-xs text-text-tertiary ml-1">
      {sources.map((s) => `[${s}]`).join(' ')}
    </span>
  );
}

function StructuredLetter({
  statements,
  closing,
  company,
  jobTitle,
  jobUrl,
  candidateName,
  candidateEmail,
  candidateTitle,
  candidateLinkedin,
}: {
  statements: AdvocacyStatement[];
  closing: string;
  company: string | null;
  jobTitle: string | null;
  jobUrl: string | null;
  candidateName: string | null;
  candidateEmail: string | null;
  candidateTitle: string | null;
  candidateLinkedin: string | null;
}) {
  const firstName = candidateName?.split(' ')[0] ?? candidateName;
  const jobTitleDisplay = jobUrl
    ? <a href={jobUrl} target="_blank" rel="noopener noreferrer" className="text-text-link underline underline-offset-2">{jobTitle}</a>
    : <span>{jobTitle}</span>;
  const linkedinUrl = candidateLinkedin
    ? (candidateLinkedin.startsWith('http') ? candidateLinkedin : `https://${candidateLinkedin}`)
    : null;

  return (
    <div className={proseCls}>
      {/* Greeting */}
      <p><strong>Hello {company},</strong></p>
      <p>
        Given the requirements in your {jobTitleDisplay} job posting, here are some reasons <strong>{candidateName}</strong> would be a strong fit for the role.
      </p>
      <hr />

      {/* Advocacy statements */}
      {statements.map((stmt, i) => (
        <div key={i}>
          <p><strong>{stmt.header}</strong></p>
          <p>
            <ReactMarkdown components={{ p: ({ children }) => <>{children}</> }}>
              {stmt.body}
            </ReactMarkdown>
            <SourceTags sources={stmt.sources} />
          </p>
        </div>
      ))}

      <hr />

      {/* LLM closing */}
      <ReactMarkdown>{closing}</ReactMarkdown>

      {/* Deterministic contact line */}
      {candidateEmail && (
        <p>
          If you&apos;re interested in continuing the conversation, {firstName} can be reached at{' '}
          <a href={`mailto:${candidateEmail}`}>{candidateEmail}</a>.
        </p>
      )}

      <hr />

      {/* Brief footer */}
      <p className="text-xs text-text-tertiary not-prose">
        <em>
          {[
            candidateName,
            candidateTitle,
            candidateEmail ? <a key="email" href={`mailto:${candidateEmail}`} className="text-text-link hover:underline">{candidateEmail}</a> : null,
            linkedinUrl ? <a key="li" href={linkedinUrl} target="_blank" rel="noopener noreferrer" className="text-text-link hover:underline">LinkedIn</a> : null,
          ]
            .filter(Boolean)
            .flatMap((part, i, arr) => i < arr.length - 1 ? [part, <span key={`dot-${i}`} className="text-text-disabled"> · </span>] : [part])}
        </em>
      </p>
    </div>
  );
}

export function AdvocacyLetter({ tailoring, authorName }: AdvocacyLetterProps) {
  const lc = tailoring.letter_content;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <TailoringHeader
        company={tailoring.company}
        title={tailoring.title}
        jobUrl={tailoring.job_url}
        authorName={authorName}
        className="mb-8"
      />
      {lc ? (
        <StructuredLetter
          statements={lc.advocacy_statements}
          closing={lc.closing}
          company={tailoring.company}
          jobTitle={tailoring.title}
          jobUrl={tailoring.job_url}
          candidateName={authorName ?? null}
          candidateEmail={tailoring.author_email ?? null}
          candidateTitle={tailoring.author_title ?? null}
          candidateLinkedin={tailoring.author_linkedin ?? null}
        />
      ) : tailoring.generated_output ? (
        <div className={proseCls}>
          <ReactMarkdown
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
              ),
            }}
          >
            {tailoring.generated_output}
          </ReactMarkdown>
        </div>
      ) : null}
    </div>
  );
}
