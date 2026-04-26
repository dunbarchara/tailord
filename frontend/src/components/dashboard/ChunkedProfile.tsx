'use client';

import { useCallback, useEffect, useState } from 'react';
import { Pencil, X, Check, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type {
  ExperienceChunk,
  ExperienceChunksResponse,
  GitHubRepoGroup,
  ProjectGroup,
  WorkExperienceGroup,
} from '@/types';

/* ─── Shared styles ─────────────────────────────────────────────────────── */

const textareaCls =
  'w-full rounded-lg border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 resize-none ' +
  'focus:border-text-primary focus:shadow-[0_0_0_2px_rgba(0,0,0,0.06)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.06)]';

const inputCls =
  'flex-1 min-w-0 rounded-lg border border-border-default bg-surface-elevated px-2.5 py-1.5 text-xs text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
  'focus:border-text-primary focus:shadow-[0_0_0_2px_rgba(0,0,0,0.06)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.06)]';

/* ─── Inline editable chunk ─────────────────────────────────────────────── */

function EditableChunk({
  chunk,
  render,
  onSave,
}: {
  chunk: ExperienceChunk;
  render: (content: string) => React.ReactNode;
  onSave: (id: string, content: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(chunk.content);
  const [saving, setSaving] = useState(false);

  // Sync if parent updates this chunk (e.g. after successful save from another session)
  useEffect(() => {
    if (!editing) setValue(chunk.content);
  }, [chunk.content, editing]);

  const handleSave = async () => {
    if (!value.trim() || value.trim() === chunk.content) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(chunk.id, value.trim());
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setValue(chunk.content);
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="flex flex-col gap-1.5">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={Math.max(2, Math.ceil(value.length / 80))}
          className={textareaCls}
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Escape') handleCancel();
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
          }}
        />
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !value.trim()}
            className="inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity"
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            Save
          </button>
          <button
            type="button"
            onClick={handleCancel}
            className="inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium text-text-tertiary hover:text-text-secondary border border-border-default hover:border-border-strong transition-colors"
          >
            <X className="h-3 w-3" />
            Cancel
          </button>
          <span className="text-xs text-text-disabled ml-1">⌘↵ to save</span>
        </div>
      </div>
    );
  }

  return (
    <div className="group flex items-start gap-1.5">
      <div className="flex-1">{render(chunk.content)}</div>
      <button
        type="button"
        onClick={() => setEditing(true)}
        title="Edit"
        className="opacity-0 group-hover:opacity-100 shrink-0 mt-0.5 p-0.5 rounded text-text-disabled hover:text-text-secondary transition-all"
      >
        <Pencil className="h-3 w-3" />
      </button>
    </div>
  );
}

/* ─── Editable group header (work experience company / title / date) ─────── */

function EditableGroupHeader({
  group,
  chunkId,
  onSaved,
}: {
  group: WorkExperienceGroup;
  chunkId: string;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const parts = (group.group_key ?? '').split(' | ');
  const [company, setCompany] = useState(parts[0] ?? '');
  const [title, setTitle] = useState(parts.slice(1).join(' | '));
  const [dateRange, setDateRange] = useState(group.date_range ?? '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const newGroupKey =
      [company.trim(), title.trim()].filter(Boolean).join(' | ') || null;
    const newDateRange = dateRange.trim() || null;
    setSaving(true);
    try {
      const res = await fetch(`/api/experience/chunks/${chunkId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_key: newGroupKey, date_range: newDateRange }),
      });
      if (!res.ok) throw new Error('Failed to save');
      setEditing(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    const p = (group.group_key ?? '').split(' | ');
    setCompany(p[0] ?? '');
    setTitle(p.slice(1).join(' | '));
    setDateRange(group.date_range ?? '');
    setEditing(false);
  };

  if (!editing) {
    return (
      <div className="group flex items-center gap-1.5 mb-1">
        <p className="font-medium text-text-primary">
          {group.group_key ?? 'Unknown role'}
          {group.date_range && (
            <span className="font-normal text-text-tertiary"> · {group.date_range}</span>
          )}
        </p>
        <button
          type="button"
          onClick={() => setEditing(true)}
          title="Edit position"
          className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-text-disabled hover:text-text-secondary transition-all"
        >
          <Pencil className="h-3 w-3" />
        </button>
      </div>
    );
  }

  return (
    <div className="mb-2 flex flex-col gap-1.5">
      <div className="flex gap-1.5">
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="Company"
          className={inputCls}
          onKeyDown={(e) => {
            if (e.key === 'Escape') handleCancel();
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
          }}
        />
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          className={inputCls}
          onKeyDown={(e) => {
            if (e.key === 'Escape') handleCancel();
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
          }}
        />
        <input
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          placeholder="e.g. Jan 2022 – Mar 2024"
          className={cn(inputCls, 'flex-none w-44')}
          onKeyDown={(e) => {
            if (e.key === 'Escape') handleCancel();
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
          }}
        />
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity"
        >
          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
          Save
        </button>
        <button
          type="button"
          onClick={handleCancel}
          className="inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium text-text-tertiary hover:text-text-secondary border border-border-default hover:border-border-strong transition-colors"
        >
          <X className="h-3 w-3" />
          Cancel
        </button>
        <span className="text-xs text-text-disabled ml-1">⌘↵ to save · updates all bullets</span>
      </div>
    </div>
  );
}

/* ─── Section header ────────────────────────────────────────────────────── */

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

/* ─── Resume tab ────────────────────────────────────────────────────────── */

function ResumeTab({
  resume,
  onSave,
  onRefetch,
}: {
  resume: NonNullable<ExperienceChunksResponse['resume']>;
  onSave: (id: string, content: string) => Promise<void>;
  onRefetch: () => void;
}) {
  // Split "other" into summary (position 0) and certifications (rest)
  const summary = resume.other[0] ?? null;
  const certifications = resume.other.slice(1);

  return (
    <div className="text-xs">
      {/* Summary */}
      {summary && (
        <Section title="Summary">
          <EditableChunk
            chunk={summary}
            onSave={onSave}
            render={(content) => (
              <p className="text-text-secondary leading-relaxed">{content}</p>
            )}
          />
        </Section>
      )}

      {/* Work Experience */}
      {resume.work_experience.length > 0 && (
        <Section title="Work Experience">
          <div className="space-y-4">
            {resume.work_experience.map((group: WorkExperienceGroup, i: number) => (
              <div key={i}>
                {group.chunks[0] && (
                  <EditableGroupHeader
                    group={group}
                    chunkId={group.chunks[0].id}
                    onSaved={onRefetch}
                  />
                )}
                <ul className="space-y-0.5 pl-3">
                  {group.chunks.map((chunk) => (
                    <li key={chunk.id}>
                      <EditableChunk
                        chunk={chunk}
                        onSave={onSave}
                        render={(content) => (
                          <span className="text-text-secondary before:content-['·'] before:mr-1.5 before:text-text-tertiary">
                            {content}
                          </span>
                        )}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Skills */}
      {resume.skills.length > 0 && (
        <Section title="Skills">
          <div className="flex flex-wrap gap-1.5">
            {resume.skills.map((chunk) => (
              <EditableChunk
                key={chunk.id}
                chunk={chunk}
                onSave={onSave}
                render={(content) => (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-surface-base border border-border-subtle text-text-secondary">
                    {content}
                  </span>
                )}
              />
            ))}
          </div>
        </Section>
      )}

      {/* Projects */}
      {resume.projects.length > 0 && (
        <Section title="Projects">
          <div className="space-y-3">
            {resume.projects.map((group: ProjectGroup, i: number) => (
              <div key={i}>
                {group.group_key && (
                  <p className="font-medium text-text-primary mb-0.5">{group.group_key}</p>
                )}
                {group.chunks.map((chunk) => (
                  <div key={chunk.id}>
                    <EditableChunk
                      chunk={chunk}
                      onSave={onSave}
                      render={(content) => (
                        <span className="text-text-secondary leading-relaxed">{content}</span>
                      )}
                    />
                    {chunk.technologies && chunk.technologies.length > 0 && (
                      <p className="text-text-tertiary mt-0.5">{chunk.technologies.join(', ')}</p>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Education */}
      {resume.education.length > 0 && (
        <Section title="Education">
          <div className="space-y-1.5">
            {resume.education.map((chunk) => (
              <EditableChunk
                key={chunk.id}
                chunk={chunk}
                onSave={onSave}
                render={(content) => <p className="text-text-secondary">{content}</p>}
              />
            ))}
          </div>
        </Section>
      )}

      {/* Certifications */}
      {certifications.length > 0 && (
        <Section title="Certifications">
          <ul className="space-y-0.5">
            {certifications.map((chunk) => (
              <li key={chunk.id}>
                <EditableChunk
                  chunk={chunk}
                  onSave={onSave}
                  render={(content) => (
                    <span className="text-text-secondary before:content-['·'] before:mr-1.5 before:text-text-tertiary">
                      {content}
                    </span>
                  )}
                />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {resume.work_experience.length === 0 &&
        resume.skills.length === 0 &&
        resume.projects.length === 0 &&
        resume.education.length === 0 &&
        !summary && <EmptyField label="No resume data parsed yet." />}
    </div>
  );
}

/* ─── GitHub tab ────────────────────────────────────────────────────────── */

function GitHubTab({
  github,
  onSave,
}: {
  github: NonNullable<ExperienceChunksResponse['github']>;
  onSave: (id: string, content: string) => Promise<void>;
}) {
  if (github.repos.length === 0) {
    return <EmptyField label="Enrichment in progress — check back shortly." />;
  }

  return (
    <div className="text-xs space-y-4">
      {github.repos.map((repo: GitHubRepoGroup, i: number) => {
        const projectChunk = repo.chunks.find((c) => c.claim_type === 'project');
        const skillChunks = repo.chunks.filter((c) => c.claim_type === 'skill');
        return (
          <div
            key={i}
            className="border border-border-subtle rounded-lg px-3 py-2.5 bg-surface-elevated space-y-1.5"
          >
            <p className="font-medium text-text-primary font-mono">{repo.group_key}</p>
            {projectChunk && (
              <EditableChunk
                chunk={projectChunk}
                onSave={onSave}
                render={(content) => (
                  <span className="text-text-secondary leading-relaxed">{content}</span>
                )}
              />
            )}
            {skillChunks.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-0.5">
                {skillChunks.map((chunk) => (
                  <EditableChunk
                    key={chunk.id}
                    chunk={chunk}
                    onSave={onSave}
                    render={(content) => (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-surface-base border border-border-subtle text-text-tertiary">
                        {content}
                      </span>
                    )}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Direct Input tab ──────────────────────────────────────────────────── */

function DirectInputTab({
  chunk,
  onSave,
}: {
  chunk: ExperienceChunk;
  onSave: (id: string, content: string) => Promise<void>;
}) {
  return (
    <EditableChunk
      chunk={chunk}
      onSave={onSave}
      render={(content) => (
        <pre className="text-xs text-text-secondary whitespace-pre-wrap leading-relaxed font-sans">
          {content}
        </pre>
      )}
    />
  );
}

/* ─── Main component ────────────────────────────────────────────────────── */

type SourceTab = 'resume' | 'github' | 'user_input';

const TAB_LABELS: Record<SourceTab, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct Input',
};

export function ChunkedProfile({ refreshKey }: { refreshKey?: number }) {
  const [data, setData] = useState<ExperienceChunksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<SourceTab>('resume');

  const fetchChunks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/experience/chunks');
      if (!res.ok) return;
      const json: ExperienceChunksResponse = await res.json();
      setData(json);
      // Auto-select first available tab
      if (json.resume) setActiveTab('resume');
      else if (json.github) setActiveTab('github');
      else if (json.user_input) setActiveTab('user_input');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchChunks();
  }, [fetchChunks, refreshKey]);

  const handleSave = async (id: string, content: string) => {
    const res = await fetch(`/api/experience/chunks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Failed to save');
    }
    const updated: ExperienceChunk = await res.json();
    // Optimistic update: replace the chunk in local state
    setData((prev) => {
      if (!prev) return prev;
      return patchChunkInResponse(prev, updated);
    });
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-xs text-text-tertiary">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading…
      </div>
    );
  }

  if (!data || (!data.resume && !data.github && !data.user_input)) {
    return <p className="text-xs text-text-disabled italic">No parsed data available.</p>;
  }

  const availableTabs = (
    ['resume', 'github', 'user_input'] as SourceTab[]
  ).filter((t) => {
    if (t === 'resume') return !!data.resume;
    if (t === 'github') return !!data.github;
    if (t === 'user_input') return !!data.user_input;
    return false;
  });

  const tab = availableTabs.includes(activeTab) ? activeTab : availableTabs[0];

  return (
    <div>
      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b border-border-subtle mb-4">
        {availableTabs.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setActiveTab(t)}
            className={cn(
              'px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors',
              tab === t
                ? 'border-brand-primary text-text-primary'
                : 'border-transparent text-text-tertiary hover:text-text-secondary'
            )}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'resume' && data.resume && (
        <ResumeTab resume={data.resume} onSave={handleSave} onRefetch={fetchChunks} />
      )}
      {tab === 'github' && data.github && (
        <GitHubTab github={data.github} onSave={handleSave} />
      )}
      {tab === 'user_input' && data.user_input && (
        <DirectInputTab chunk={data.user_input} onSave={handleSave} />
      )}
    </div>
  );
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function patchChunkInResponse(
  prev: ExperienceChunksResponse,
  updated: ExperienceChunk
): ExperienceChunksResponse {
  const replaceIn = (chunks: ExperienceChunk[]) =>
    chunks.map((c) => (c.id === updated.id ? updated : c));

  return {
    ...prev,
    resume: prev.resume
      ? {
          ...prev.resume,
          work_experience: prev.resume.work_experience.map((g) => ({
            ...g,
            chunks: replaceIn(g.chunks),
          })),
          skills: replaceIn(prev.resume.skills),
          projects: prev.resume.projects.map((g) => ({
            ...g,
            chunks: replaceIn(g.chunks),
          })),
          education: replaceIn(prev.resume.education),
          other: replaceIn(prev.resume.other),
        }
      : null,
    github: prev.github
      ? {
          repos: prev.github.repos.map((r) => ({
            ...r,
            chunks: replaceIn(r.chunks),
          })),
        }
      : null,
    user_input:
      prev.user_input?.id === updated.id ? updated : prev.user_input,
  };
}
