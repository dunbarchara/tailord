'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, Pencil, Trash2, Check, Loader2, Plus, X } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import type {
  ExperienceChunk,
  ExperienceChunksResponse,
  WorkExperienceGroup,
} from '@/types';

/* ─── Shared button styles ──────────────────────────────────────────────── */

const saveBtnCls =
  'inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium ' +
  'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 ' +
  'hover:opacity-90 disabled:opacity-40 transition-opacity';

const cancelBtnCls =
  'inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium ' +
  'text-text-tertiary hover:text-text-secondary border border-border-default ' +
  'hover:border-border-strong transition-colors';

const actionBtnCls =
  'inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium ' +
  'text-text-tertiary hover:text-text-primary hover:bg-surface-sunken transition-colors';

const deleteBtnCls =
  'inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium ' +
  'text-text-tertiary hover:text-error hover:bg-red-50 dark:hover:bg-red-950/20 ' +
  'transition-colors disabled:opacity-40';

/* ─── Table group type ───────────────────────────────────────────────────── */

interface TableGroup {
  key: string | null;
  chunks: ExperienceChunk[];
  bullet?: boolean;
  context?: (chunk: ExperienceChunk) => string | undefined;
}

/* ─── Chunk row ─────────────────────────────────────────────────────────── */

function ChunkRow({
  chunk,
  bullet,
  context,
  onSave,
  onDelete,
  isLast,
}: {
  chunk: ExperienceChunk;
  bullet?: boolean;
  context?: string;
  onSave: (id: string, content: string) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  isLast?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(chunk.content);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { if (!editing) setValue(chunk.content); }, [chunk.content, editing]);

  useEffect(() => {
    if (editing && textareaRef.current) {
      const el = textareaRef.current;
      el.style.height = '0px';
      el.style.height = `${el.scrollHeight}px`;
    }
  }, [editing]);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === chunk.content) { setEditing(false); return; }
    setSaving(true);
    try { await onSave(chunk.id, trimmed); setEditing(false); } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    setDeleting(true);
    try { await onDelete(chunk.id); } finally { setDeleting(false); }
  };

  return (
    <div className={cn('px-4 py-3', !isLast && 'border-b border-border-subtle')}>
      {context && (
        <p className="text-xs text-text-disabled italic mb-1.5 leading-relaxed">{context}</p>
      )}

      {editing ? (
        <>
          {bullet
            ? (
              <div className="flex gap-2 text-sm leading-relaxed">
                <span className="text-text-tertiary flex-shrink-0 mt-0.5">·</span>
                <textarea
                  ref={textareaRef}
                  value={value}
                  rows={1}
                  onChange={(e) => { setValue(e.target.value); e.target.style.height = '0px'; e.target.style.height = `${e.target.scrollHeight}px`; }}
                  className="flex-1 bg-transparent resize-none overflow-hidden outline-none p-0 text-sm text-text-primary leading-relaxed"
                  autoFocus
                  onKeyDown={(e) => { if (e.key === 'Escape') { setValue(chunk.content); setEditing(false); } if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
                />
              </div>
            )
            : (
              <textarea
                ref={textareaRef}
                value={value}
                rows={1}
                onChange={(e) => { setValue(e.target.value); e.target.style.height = '0px'; e.target.style.height = `${e.target.scrollHeight}px`; }}
                className="w-full bg-transparent resize-none overflow-hidden outline-none p-0 text-sm text-text-primary leading-relaxed"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Escape') { setValue(chunk.content); setEditing(false); } if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
              />
            )
          }
          <div className="flex items-center gap-1.5 mt-2">
            <button type="button" onClick={handleSave} disabled={saving || !value.trim()} className={saveBtnCls}>
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
              Save
            </button>
            <button type="button" onClick={() => { setValue(chunk.content); setEditing(false); }} className={cancelBtnCls}>
              <X className="h-3 w-3" />
              Cancel
            </button>
            <span className="text-xs text-text-disabled ml-1">⌘↵</span>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-start gap-3">
            <p className="flex-1 text-sm text-text-secondary leading-relaxed">
              {bullet && <span className="text-text-tertiary mr-1.5">·</span>}
              {chunk.content}
            </p>
            <button
              type="button"
              onClick={() => setExpanded((o) => !o)}
              className="shrink-0 mt-0.5 rounded-md p-0.5 text-text-disabled hover:text-text-secondary hover:bg-surface-sunken transition-colors"
            >
              <ChevronDown className={cn('h-3.5 w-3.5 transition-transform duration-150', expanded && 'rotate-180')} />
            </button>
          </div>

          {/* Expanded controls */}
          <div className={cn('grid transition-all duration-150', expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
            <div className="overflow-hidden">
              <div className="flex items-center gap-0.5 mt-2">
                <button type="button" onClick={() => { setExpanded(false); setEditing(true); }} className={actionBtnCls}>
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
                {onDelete && (
                  <button type="button" onClick={handleDelete} disabled={deleting} className={deleteBtnCls}>
                    {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                    Delete
                  </button>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ─── Experience table ───────────────────────────────────────────────────── */

function ExperienceTable({
  groups,
  onSave,
  onDelete,
}: {
  groups: TableGroup[];
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const allChunks = groups.flatMap((g) => g.chunks);
  if (allChunks.length === 0) return null;

  return (
    <div className="rounded-2xl overflow-hidden border border-border-subtle">
      {groups.map((group, gi) => {
        if (group.chunks.length === 0) return null;
        const isLastGroup = gi === groups.length - 1 || groups.slice(gi + 1).every(g => g.chunks.length === 0);
        return (
          <div key={gi}>
            {group.key !== null && (
              <div className={cn(
                'flex items-center px-4 h-9 bg-surface-base text-xs font-medium text-text-tertiary tracking-wide',
                'border-b border-border-subtle',
                gi > 0 && groups.slice(0, gi).some(g => g.chunks.length > 0) && 'border-t border-border-subtle',
              )}>
                {group.key || ''}
              </div>
            )}
            {group.chunks.map((chunk, ci) => {
              const isLastInGroup = ci === group.chunks.length - 1;
              const isVeryLast = isLastGroup && isLastInGroup;
              return (
                <ChunkRow
                  key={chunk.id}
                  chunk={chunk}
                  bullet={group.bullet}
                  context={group.context?.(chunk)}
                  onSave={onSave}
                  onDelete={onDelete}
                  isLast={isVeryLast}
                />
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Activity section ───────────────────────────────────────────────────── */

function ActivitySection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-md font-medium text-text-primary">{title}</h3>
          <p className="text-sm text-text-secondary mt-0.5">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

/* ─── Add Experience form ───────────────────────────────────────────────── */

function AddExperienceForm({ onAdded }: { onAdded: (chunks: ExperienceChunk[]) => void }) {
  const [text, setText] = useState('');
  const [parsing, setParsing] = useState(false);
  const [persisting, setPersisting] = useState(false);
  const [preview, setPreview] = useState<string[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const reset = () => { setText(''); setPreview(null); setSelected(new Set()); };

  const handleParseAndAdd = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setParsing(true);
    try {
      const res = await fetch('/api/experience/user-input/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: trimmed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toastError(err.detail ?? 'Failed to parse input');
        return;
      }
      const data: { chunks: string[] } = await res.json();
      if (data.chunks.length <= 1) {
        await persist(data.chunks);
      } else {
        setPreview(data.chunks);
        setSelected(new Set(data.chunks.map((_, i) => i)));
      }
    } finally {
      setParsing(false);
    }
  };

  const persist = async (chunks: string[]) => {
    if (chunks.length === 0) return;
    setPersisting(true);
    try {
      const res = await fetch('/api/experience/user-input/chunks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chunks }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toastError(err.detail ?? 'Failed to save');
        return;
      }
      const data: { chunk_ids: string[] } = await res.json();
      const now = new Date().toISOString();
      const newChunks: ExperienceChunk[] = chunks.map((content, i) => ({
        id: data.chunk_ids[i] ?? `temp-${i}`,
        source_type: 'user_input',
        source_ref: null,
        claim_type: 'other',
        content,
        group_key: null,
        date_range: null,
        technologies: null,
        chunk_metadata: null,
        position: 9999 + i,
        updated_at: now,
      }));
      onAdded(newChunks);
      reset();
      toast.success(`${chunks.length} claim${chunks.length !== 1 ? 's' : ''} added`);
    } finally {
      setPersisting(false);
    }
  };

  const handleConfirm = async () => {
    if (!preview) return;
    await persist(preview.filter((_, i) => selected.has(i)));
  };

  const toggleSelect = (i: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  };

  const textareaCls =
    'w-full rounded-xl border border-border-default bg-surface-elevated px-3 py-2.5 text-sm text-text-primary ' +
    'placeholder:text-text-disabled outline-none transition-colors duration-100 resize-none ' +
    'focus:border-text-primary focus:shadow-[0_0_0_2px_rgba(0,0,0,0.06)] ' +
    'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.06)]';

  return (
    <div className="mb-5 space-y-2">
      {preview ? (
        <div className="space-y-2">
          <p className="text-sm text-text-secondary">Select the claims you want to add:</p>
          <div className="space-y-0.5">
            {preview.map((claim, i) => (
              <label key={i} className="flex items-start gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-sunken cursor-pointer">
                <input type="checkbox" checked={selected.has(i)} onChange={() => toggleSelect(i)} className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 accent-brand-primary" />
                <span className="text-sm text-text-secondary">{claim}</span>
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button type="button" onClick={handleConfirm} disabled={persisting || selected.size === 0}
              className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[8px] text-xs font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity">
              {persisting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              Add {selected.size > 0 ? `${selected.size} ` : ''}selected
            </button>
            <button type="button" onClick={reset} className="text-xs text-text-tertiary hover:text-text-secondary transition-colors">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe experience, projects, or skills not captured above…"
            rows={3}
            className={textareaCls}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleParseAndAdd(); }}
          />
          <button type="button" onClick={handleParseAndAdd} disabled={parsing || !text.trim()}
            className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[8px] text-xs font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity">
            {parsing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
            {parsing ? 'Parsing…' : 'Parse & Add'}
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Group-key helpers ─────────────────────────────────────────────────── */

function formatWorkGroupKey(group: WorkExperienceGroup): string {
  const parts = (group.group_key ?? '').split(' | ').filter(Boolean);
  let label = parts.join(' · ');
  if (group.date_range) label += `  ·  ${group.date_range}`;
  return label || 'Unknown role';
}

/* ─── Main component ────────────────────────────────────────────────────── */

export function ChunkedProfile({ refreshKey }: { refreshKey?: number }) {
  const [data, setData] = useState<ExperienceChunksResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchChunks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/experience/chunks');
      if (!res.ok) return;
      const json: ExperienceChunksResponse = await res.json();
      setData(json);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchChunks(); }, [fetchChunks, refreshKey]);

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
    setData((prev) => prev ? patchChunkInResponse(prev, updated) : prev);
  };

  const handleDelete = async (id: string) => {
    const res = await fetch(`/api/experience/chunks/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? 'Failed to delete');
      return;
    }
    setData((prev) => prev ? removeChunkFromResponse(prev, id) : prev);
  };

  const handleAdded = (newChunks: ExperienceChunk[]) => {
    setData((prev) => {
      if (!prev) return prev;
      return { ...prev, user_input: [...(prev.user_input ?? []), ...newChunks] };
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

  /* ── Build table groups ─────────────────────────────────────────────── */

  const resumeGroups: TableGroup[] = [];
  if (data?.resume) {
    if (data.resume.other[0]) {
      resumeGroups.push({ key: null, chunks: [data.resume.other[0]] });
    }
    data.resume.work_experience.forEach((g) => {
      resumeGroups.push({ key: formatWorkGroupKey(g), chunks: g.chunks, bullet: true });
    });
    if (data.resume.skills.length > 0) {
      resumeGroups.push({ key: 'Skills', chunks: data.resume.skills });
    }
    data.resume.projects.forEach((p) => {
      resumeGroups.push({ key: p.group_key ?? 'Project', chunks: p.chunks });
    });
    if (data.resume.education.length > 0) {
      resumeGroups.push({ key: 'Education', chunks: data.resume.education });
    }
    const certs = data.resume.other.slice(1);
    if (certs.length > 0) {
      resumeGroups.push({ key: 'Certifications', chunks: certs });
    }
  }

  const githubGroups: TableGroup[] = (data?.github?.repos ?? []).map((repo) => ({
    key: repo.group_key ?? 'Unknown repo',
    chunks: repo.chunks,
  }));

  const userInputGroups: TableGroup[] = data?.user_input?.length
    ? [{ key: null, chunks: data.user_input }]
    : [];

  const gapGroups: TableGroup[] = data?.gap_response?.length
    ? [{
        key: null,
        chunks: data.gap_response,
        context: (chunk) => chunk.chunk_metadata?.question,
      }]
    : [];

  const hasResume = resumeGroups.some((g) => g.chunks.length > 0);
  const hasGithub = githubGroups.some((g) => g.chunks.length > 0);
  const hasGapResponse = gapGroups.some((g) => g.chunks.length > 0);

  return (
    <div className="space-y-10">

      {hasResume && (
        <ActivitySection title="Resume" description="Extracted from your uploaded resume">
          <ExperienceTable groups={resumeGroups} onSave={handleSave} onDelete={handleDelete} />
        </ActivitySection>
      )}

      {hasGithub && (
        <ActivitySection title="GitHub" description="Enriched from your linked repositories">
          <ExperienceTable groups={githubGroups} onSave={handleSave} onDelete={handleDelete} />
        </ActivitySection>
      )}

      <ActivitySection title="Additional Experience" description="Manually added experience and context">
        <AddExperienceForm onAdded={handleAdded} />
        {userInputGroups.length > 0 && (
          <ExperienceTable groups={userInputGroups} onSave={handleSave} onDelete={handleDelete} />
        )}
      </ActivitySection>

      {hasGapResponse && (
        <ActivitySection title="Gap Responses" description="Answers to gap questions from your tailorings">
          <ExperienceTable groups={gapGroups} onSave={handleSave} onDelete={handleDelete} />
        </ActivitySection>
      )}

    </div>
  );
}

/* ─── Response helpers ───────────────────────────────────────────────────── */

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
          work_experience: prev.resume.work_experience.map((g) => ({ ...g, chunks: replaceIn(g.chunks) })),
          skills: replaceIn(prev.resume.skills),
          projects: prev.resume.projects.map((g) => ({ ...g, chunks: replaceIn(g.chunks) })),
          education: replaceIn(prev.resume.education),
          other: replaceIn(prev.resume.other),
        }
      : null,
    github: prev.github
      ? { repos: prev.github.repos.map((r) => ({ ...r, chunks: replaceIn(r.chunks) })) }
      : null,
    user_input: prev.user_input ? replaceIn(prev.user_input) : null,
    gap_response: prev.gap_response ? replaceIn(prev.gap_response) : null,
  };
}

function removeChunkFromResponse(
  prev: ExperienceChunksResponse,
  id: string
): ExperienceChunksResponse {
  const filterOut = (chunks: ExperienceChunk[]) => chunks.filter((c) => c.id !== id);

  const newResume = prev.resume
    ? {
        ...prev.resume,
        work_experience: prev.resume.work_experience
          .map((g) => ({ ...g, chunks: filterOut(g.chunks) }))
          .filter((g) => g.chunks.length > 0),
        skills: filterOut(prev.resume.skills),
        projects: prev.resume.projects
          .map((g) => ({ ...g, chunks: filterOut(g.chunks) }))
          .filter((g) => g.chunks.length > 0),
        education: filterOut(prev.resume.education),
        other: filterOut(prev.resume.other),
      }
    : null;

  const resumeEmpty =
    newResume &&
    newResume.work_experience.length === 0 &&
    newResume.skills.length === 0 &&
    newResume.projects.length === 0 &&
    newResume.education.length === 0 &&
    newResume.other.length === 0;

  const newGithub = prev.github
    ? { repos: prev.github.repos.map((r) => ({ ...r, chunks: filterOut(r.chunks) })) }
    : null;

  const newUserInput = prev.user_input ? filterOut(prev.user_input) : null;
  const newGapResponse = prev.gap_response ? filterOut(prev.gap_response) : null;

  return {
    ...prev,
    resume: resumeEmpty ? null : newResume,
    github: newGithub,
    user_input: newUserInput?.length ? newUserInput : null,
    gap_response: newGapResponse?.length ? newGapResponse : null,
  };
}
