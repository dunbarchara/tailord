'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { SourcedProfile, ExtractedProfile, GitHubRepo } from '@/types';

interface ParsedProfileProps {
  profile: SourcedProfile;
  rawResumeText?: string | null;
}

// ─── Sub-renderers ────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2 pb-1 border-b border-border-subtle">
        {title}
      </h4>
      {children}
    </div>
  );
}

function EmptyField({ label }: { label: string }) {
  return <p className="text-xs text-text-disabled italic">{label}</p>;
}

function ResumeTab({ resume }: { resume: ExtractedProfile }) {
  return (
    <div className="text-xs">
      {/* Contact */}
      {(resume.email || resume.phone || resume.linkedin || resume.location) && (
        <Section title="Contact">
          <div className="space-y-0.5">
            {resume.location && (
              <p className="text-text-secondary">
                <span className="text-text-tertiary w-16 inline-block">Location</span>
                {resume.location}
              </p>
            )}
            {resume.email && (
              <p className="text-text-secondary">
                <span className="text-text-tertiary w-16 inline-block">Email</span>
                <a href={`mailto:${resume.email}`} className="text-text-link hover:underline">{resume.email}</a>
              </p>
            )}
            {resume.phone && (
              <p className="text-text-secondary">
                <span className="text-text-tertiary w-16 inline-block">Phone</span>
                {resume.phone}
              </p>
            )}
            {resume.linkedin && (
              <p className="text-text-secondary">
                <span className="text-text-tertiary w-16 inline-block">LinkedIn</span>
                <a href={resume.linkedin.startsWith('http') ? resume.linkedin : `https://${resume.linkedin}`} target="_blank" rel="noopener noreferrer" className="text-text-link hover:underline">{resume.linkedin}</a>
              </p>
            )}
          </div>
        </Section>
      )}

      {/* Title + Headline */}
      {(resume.title || resume.headline) && (
        <Section title="Identity">
          {resume.title && (
            <p className="text-text-secondary font-medium">{resume.title}</p>
          )}
          {resume.headline && (
            <p className="text-text-secondary leading-relaxed mt-1">{resume.headline}</p>
          )}
        </Section>
      )}

      {/* Summary */}
      <Section title="Summary">
        {resume.summary
          ? <p className="text-text-secondary leading-relaxed">{resume.summary}</p>
          : <EmptyField label="No summary extracted" />}
      </Section>

      {/* Work Experience */}
      <Section title="Work Experience">
        {resume.work_experience?.length > 0 ? (
          <div className="space-y-4">
            {resume.work_experience.map((job, i) => (
              <div key={i}>
                <p className="font-medium text-text-primary">
                  {job.title}
                  {job.company && <span className="font-normal text-text-secondary"> @ {job.company}</span>}
                  {job.location && <span className="font-normal text-text-tertiary"> · {job.location}</span>}
                  {job.duration && <span className="font-normal text-text-tertiary"> · {job.duration}</span>}
                </p>
                {job.bullets?.length > 0 && (
                  <ul className="mt-1 space-y-0.5 pl-3">
                    {job.bullets.map((b, j) => (
                      <li key={j} className="text-text-secondary before:content-['·'] before:mr-1.5 before:text-text-tertiary">{b}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        ) : <EmptyField label="No work experience extracted" />}
      </Section>

      {/* Skills */}
      <Section title="Skills">
        {(resume.skills?.technical?.length > 0 || resume.skills?.soft?.length > 0) ? (
          <div className="space-y-1.5">
            {resume.skills.technical?.length > 0 && (
              <div className="flex gap-2">
                <span className="text-text-tertiary w-16 flex-shrink-0">Technical</span>
                <span className="text-text-secondary">{resume.skills.technical.join(', ')}</span>
              </div>
            )}
            {resume.skills.soft?.length > 0 && (
              <div className="flex gap-2">
                <span className="text-text-tertiary w-16 flex-shrink-0">Soft</span>
                <span className="text-text-secondary">{resume.skills.soft.join(', ')}</span>
              </div>
            )}
          </div>
        ) : <EmptyField label="No skills extracted" />}
      </Section>

      {/* Education */}
      <Section title="Education">
        {resume.education?.length > 0 ? (
          <div className="space-y-2">
            {resume.education.map((e, i) => (
              <div key={i}>
                <p className="text-text-secondary">
                  {e.degree}
                  {e.institution && <span className="text-text-tertiary"> — {e.institution}</span>}
                  {e.location && <span className="text-text-tertiary">, {e.location}</span>}
                  {e.year && <span className="text-text-tertiary"> ({e.year})</span>}
                </p>
                {e.distinction && (
                  <p className="text-text-tertiary mt-0.5">{e.distinction}</p>
                )}
              </div>
            ))}
          </div>
        ) : <EmptyField label="No education extracted" />}
      </Section>

      {/* Projects */}
      {resume.projects?.length > 0 && (
        <Section title="Projects">
          <div className="space-y-2">
            {resume.projects.map((p, i) => (
              <div key={i}>
                <p className="font-medium text-text-primary">
                  {p.name}
                  {p.technologies?.length > 0 && (
                    <span className="font-normal text-text-tertiary"> · {p.technologies.join(', ')}</span>
                  )}
                </p>
                {p.description && <p className="text-text-secondary mt-0.5">{p.description}</p>}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Certifications */}
      {resume.certifications?.length > 0 && (
        <Section title="Certifications">
          <ul className="space-y-0.5">
            {resume.certifications.map((c, i) => (
              <li key={i} className="text-text-secondary before:content-['·'] before:mr-1.5 before:text-text-tertiary">{c}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function GitHubTab({ repos }: { repos: GitHubRepo[] }) {
  if (repos.length === 0) return <EmptyField label="No repos imported" />;
  return (
    <div className="space-y-3 text-xs">
      {repos.map((repo) => (
        <div key={repo.name} className="border border-border-subtle rounded px-3 py-2 bg-surface-elevated">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-text-primary font-mono">{repo.name}</span>
            {repo.language && (
              <span className="text-text-tertiary">{repo.language}</span>
            )}
            {repo.star_count > 0 && (
              <span className="text-text-tertiary">★ {repo.star_count}</span>
            )}
            {repo.pushed_at && (
              <span className="text-text-disabled ml-auto">
                {new Date(repo.pushed_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short' })}
              </span>
            )}
          </div>
          {repo.description && (
            <p className="text-text-secondary mt-1">{repo.description}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function DirectInputTab({ text }: { text: string }) {
  return (
    <pre className="text-xs text-text-secondary whitespace-pre-wrap leading-relaxed font-sans">
      {text || <span className="text-text-disabled italic">No content</span>}
    </pre>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

type SourceTab = 'resume' | 'github' | 'user_input' | 'raw';

export function ParsedProfile({ profile, rawResumeText }: ParsedProfileProps) {
  const available: SourceTab[] = (
    ['resume', 'github', 'user_input', 'raw'] as SourceTab[]
  ).filter(s => {
    if (s === 'resume') return !!profile.resume;
    if (s === 'github') return !!profile.github?.repos?.length;
    if (s === 'user_input') return !!profile.user_input?.text;
    if (s === 'raw') return !!rawResumeText;
    return false;
  });

  const [activeTab, setActiveTab] = useState<SourceTab>(available[0] ?? 'resume');

  if (available.length === 0) {
    return <p className="text-xs text-text-disabled italic">No parsed data available.</p>;
  }

  const TAB_LABELS: Record<SourceTab, string> = {
    resume: 'Resume',
    github: 'GitHub',
    user_input: 'Direct Input',
    raw: 'Raw Text',
  };

  return (
    <div>
      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b border-border-subtle mb-4">
        {available.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors',
              activeTab === tab
                ? 'border-brand-primary text-text-primary'
                : 'border-transparent text-text-tertiary hover:text-text-secondary'
            )}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'resume' && profile.resume && (
        <ResumeTab resume={profile.resume} />
      )}
      {activeTab === 'github' && profile.github && (
        <GitHubTab repos={profile.github.repos} />
      )}
      {activeTab === 'user_input' && profile.user_input && (
        <DirectInputTab text={profile.user_input.text} />
      )}
      {activeTab === 'raw' && rawResumeText && (
        <DirectInputTab text={rawResumeText} />
      )}
    </div>
  );
}
