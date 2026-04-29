'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Pencil, X, Check, Loader2, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import type {
  ExperienceChunk,
  ExperienceChunksResponse,
  GitHubRepoGroup,
  ProjectGroup,
  WorkExperienceGroup,
} from '@/types';

/* ─── Shared styles ─────────────────────────────────────────────────────── */

const inputCls =
  'flex-1 min-w-0 rounded-lg border border-border-default bg-surface-elevated px-2.5 py-1.5 text-sm text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
  'focus:border-text-primary focus:shadow-[0_0_0_2px_rgba(0,0,0,0.06)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.06)]';

const saveBtnCls =
  'inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium ' +
  'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 ' +
  'hover:opacity-90 disabled:opacity-40 transition-opacity';

const cancelBtnCls =
  'inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium ' +
  'text-text-tertiary hover:text-text-secondary border border-border-default ' +
  'hover:border-border-strong transition-colors';

const deleteBtnCls =
  'inline-flex items-center gap-1 h-6 px-2 rounded-md text-xs font-medium ' +
  'text-text-tertiary hover:text-error border border-border-default ' +
  'hover:border-error/30 transition-colors disabled:opacity-40';

/* ─── Controls panel — buttons only, no background bar ──────────────────── */

function ControlsPanel({
  open,
  onEdit,
  onDelete,
  deleting,
}: {
  open: boolean;
  onEdit: (e: React.MouseEvent) => void;
  onDelete?: (e: React.MouseEvent) => void;
  deleting?: boolean;
}) {
  return (
    <div className={cn('grid transition-all duration-200', open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
      <div className="overflow-hidden">
        <div className="mt-1 flex items-center gap-1.5">
          <button type="button" onClick={onEdit} className={cancelBtnCls}>
            <Pencil className="h-3 w-3" />
            Edit
          </button>
          {onDelete && (
            <button
              type="button"
              onClick={onDelete}
              disabled={deleting}
              className={deleteBtnCls}
            >
              {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : <X className="h-3 w-3" />}
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Experience chunk item ─────────────────────────────────────────────── */
/*
 * Bar sits at -left-3 (outside the pl-3 container, to the left of content).
 * Counter-translate -translate-x-0.5 on the bar cancels the parent's
 * translate-x-0.5, keeping the bar visually fixed while content slides right.
 * Matches JobPosting ChunkItem behavior exactly.
 * Edit mode: parent does not translate; bar just stays at -left-3 with w-1.
 */

function ExperienceChunkItem({
  chunk,
  render,
  onSave,
  onDelete,
  bullet = false,
}: {
  chunk: ExperienceChunk;
  render: (content: string) => React.ReactNode;
  onSave: (id: string, content: string) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  /** Preserve the bullet · indicator in edit mode so the textarea aligns with the text position. */
  bullet?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(chunk.content);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { if (!editing) setValue(chunk.content); }, [chunk.content, editing]);

  // Auto-size textarea to match content height when entering edit mode.
  // Set to 0 first so scrollHeight reflects content only, not prior height.
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

  const handleCancel = () => { setValue(chunk.content); setEditing(false); };

  const handleDelete = async () => {
    if (!onDelete) return;
    setDeleting(true);
    try { await onDelete(chunk.id); } finally { setDeleting(false); }
  };

  return (
    <div
      className={cn(
        'relative pl-3 mb-1.5 group/chunk transition-transform duration-200',
        !editing && 'cursor-pointer select-none',
        // Keep translate in edit mode — edit is always entered from expanded state,
        // so content and controls should stay at the same x position throughout.
        (open || editing) ? 'translate-x-0.5' : 'hover:translate-x-0.5',
      )}
      onClick={!editing ? () => setOpen((o) => !o) : undefined}
    >
      {/*
       * Bar stays fixed: counter-translate cancels the parent's translate-x-0.5.
       * Applied in all active states (hover, open, editing) so the bar never moves.
       */}
      <div className={cn(
        'absolute top-0 bottom-0 -left-3 rounded-sm transition-all duration-200 bg-brand-primary',
        (open || editing)
          ? 'w-1 -translate-x-0.5'
          : 'w-0.5 group-hover/chunk:w-1 group-hover/chunk:-translate-x-0.5',
      )} />

      {editing ? (
        <>
          {bullet ? (
            /* Preserve bullet indicator so textarea aligns with the text position */
            <div className="flex gap-2 text-sm leading-relaxed">
              <span className="text-text-tertiary flex-shrink-0 mt-0.5">·</span>
              <textarea
                ref={textareaRef}
                value={value}
                rows={1}
                onChange={(e) => {
                  setValue(e.target.value);
                  e.target.style.height = '0px';
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                className="flex-1 bg-transparent resize-none overflow-hidden outline-none p-0 text-sm text-text-primary leading-relaxed"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Escape') handleCancel();
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
                }}
              />
            </div>
          ) : (
            <textarea
              ref={textareaRef}
              value={value}
              rows={1}
              onChange={(e) => {
                setValue(e.target.value);
                e.target.style.height = '0px';
                e.target.style.height = `${e.target.scrollHeight}px`;
              }}
              className="w-full bg-transparent resize-none overflow-hidden outline-none p-0 text-sm text-text-primary leading-relaxed"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Escape') handleCancel();
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
              }}
            />
          )}
          <div className="flex items-center gap-1.5 mt-1">
            <button type="button" onClick={handleSave} disabled={saving || !value.trim()} className={saveBtnCls}>
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
              Save
            </button>
            <button type="button" onClick={handleCancel} className={cancelBtnCls}>
              <X className="h-3 w-3" />
              Cancel
            </button>
            <span className="text-xs text-text-disabled ml-1">⌘↵</span>
          </div>
        </>
      ) : (
        <>
          {render(chunk.content)}
          <ControlsPanel
            open={open}
            onEdit={(e) => { e.stopPropagation(); setOpen(false); setEditing(true); }}
            onDelete={onDelete ? (e) => { e.stopPropagation(); handleDelete(); } : undefined}
            deleting={deleting}
          />
        </>
      )}
    </div>
  );
}

/* ─── Skill pill — used inside expanded SkillsGroup ─────────────────────── */

function SkillPill({
  chunk,
  onSave,
  onDelete,
}: {
  chunk: ExperienceChunk;
  onSave: (id: string, content: string) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(chunk.content);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => { if (!editing) setValue(chunk.content); }, [chunk.content, editing]);

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

  if (editing) {
    return (
      <div className="inline-flex items-center gap-1 h-6">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-6 px-2 rounded-md border border-border-default bg-surface-elevated text-xs text-text-primary outline-none focus:border-text-primary"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Escape') { setValue(chunk.content); setEditing(false); }
            if (e.key === 'Enter') handleSave();
          }}
          style={{ width: `${Math.max(60, value.length * 7 + 16)}px` }}
        />
        <button type="button" onClick={handleSave} disabled={saving} className={saveBtnCls}>
          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
        </button>
        <button type="button" onClick={() => { setValue(chunk.content); setEditing(false); }} className={cancelBtnCls}>
          <X className="h-3 w-3" />
        </button>
      </div>
    );
  }

  return (
    <div className="group/pill inline-flex items-center h-6 gap-0.5 px-2 rounded-md bg-surface-base border border-border-subtle text-text-secondary">
      <button type="button" onClick={() => setEditing(true)} title="Edit" className="text-xs leading-none">
        {chunk.content}
      </button>
      {onDelete && (
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleting}
          title="Delete"
          className="opacity-0 group-hover/pill:opacity-100 ml-0.5 rounded text-text-disabled hover:text-error transition-all disabled:opacity-40"
        >
          {deleting ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <X className="h-2.5 w-2.5" />}
        </button>
      )}
    </div>
  );
}

/* ─── Skills group — whole collection as one expandable chunk ────────────── */

function SkillsGroup({
  chunks,
  onSave,
  onDelete,
}: {
  chunks: ExperienceChunk[];
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const preview = chunks.map((c) => c.content).join(', ');

  return (
    <div
      className={cn(
        'relative pl-3 mb-1.5 cursor-pointer select-none group/skills transition-transform duration-200',
        open ? 'translate-x-0.5' : 'hover:translate-x-0.5',
      )}
      onClick={() => setOpen((o) => !o)}
    >
      <div className={cn(
        'absolute top-0 bottom-0 -left-3 rounded-sm transition-all duration-200 bg-brand-primary',
        open ? 'w-1 -translate-x-0.5' : 'w-0.5 group-hover/skills:w-1 group-hover/skills:-translate-x-0.5',
      )} />
      <p className="text-sm text-text-secondary leading-relaxed">{preview}</p>
      <div className={cn('grid transition-all duration-200', open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
        <div className="overflow-hidden">
          <div className="mt-1.5 flex flex-wrap gap-1.5" onClick={(e) => e.stopPropagation()}>
            {chunks.map((chunk) => (
              <SkillPill key={chunk.id} chunk={chunk} onSave={onSave} onDelete={onDelete} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Experience group header (work experience: company · title · dates) ─── */

function ExperienceGroupHeader({
  group,
  chunkId,
  onSaved,
}: {
  group: WorkExperienceGroup;
  chunkId: string;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const parts = (group.group_key ?? '').split(' | ');
  const [company, setCompany] = useState(parts[0] ?? '');
  const [jobTitle, setJobTitle] = useState(parts.slice(1).join(' | '));
  const [dateRange, setDateRange] = useState(group.date_range ?? '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const newGroupKey = [company.trim(), jobTitle.trim()].filter(Boolean).join(' | ') || null;
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
    setJobTitle(p.slice(1).join(' | '));
    setDateRange(group.date_range ?? '');
    setEditing(false);
  };

  return (
    <div
      className={cn(
        'relative pl-3 mb-1 group/header transition-transform duration-200',
        !editing && 'cursor-pointer select-none',
        (open || editing) ? 'translate-x-0.5' : 'hover:translate-x-0.5',
      )}
      onClick={!editing ? () => setOpen((o) => !o) : undefined}
    >
      <div className={cn(
        'absolute top-0 bottom-0 -left-3 rounded-sm transition-all duration-200 bg-brand-primary',
        (open || editing)
          ? 'w-1 -translate-x-0.5'
          : 'w-0.5 group-hover/header:w-1 group-hover/header:-translate-x-0.5',
      )} />

      {editing ? (
        <div className="flex flex-col gap-1.5">
          <div className="flex gap-1.5 flex-wrap">
            <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Company" className={inputCls}
              onKeyDown={(e) => { if (e.key === 'Escape') handleCancel(); if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }} />
            <input value={jobTitle} onChange={(e) => setJobTitle(e.target.value)} placeholder="Title" className={inputCls}
              onKeyDown={(e) => { if (e.key === 'Escape') handleCancel(); if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }} />
            <input value={dateRange} onChange={(e) => setDateRange(e.target.value)} placeholder="e.g. Jan 2022 – Mar 2024"
              className={cn(inputCls, 'flex-none w-44')}
              onKeyDown={(e) => { if (e.key === 'Escape') handleCancel(); if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }} />
          </div>
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={handleSave} disabled={saving} className={saveBtnCls}>
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
              Save
            </button>
            <button type="button" onClick={handleCancel} className={cancelBtnCls}>
              <X className="h-3 w-3" />
              Cancel
            </button>
            <span className="text-xs text-text-disabled ml-1">⌘↵ · updates all bullets</span>
          </div>
        </div>
      ) : (
        <>
          <p className="text-sm font-medium text-text-primary">
            {group.group_key ?? 'Unknown role'}
            {group.date_range && <span className="font-normal text-text-tertiary"> · {group.date_range}</span>}
          </p>
          <ControlsPanel
            open={open}
            onEdit={(e) => { e.stopPropagation(); setOpen(false); setEditing(true); }}
          />
        </>
      )}
    </div>
  );
}

/* ─── Section helpers ────────────────────────────────────────────────────── */

function SectionHeader({ title }: { title: string }) {
  return (
    <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-3 pb-1 border-b border-border-subtle">
      {title}
    </h4>
  );
}

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <SectionHeader title={title} />
      {children}
    </div>
  );
}

/* ─── Resume section ────────────────────────────────────────────────────── */

function ResumeSection({
  resume,
  onSave,
  onDelete,
  onRefetch,
}: {
  resume: NonNullable<ExperienceChunksResponse['resume']>;
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onRefetch: () => void;
}) {
  const summary = resume.other[0] ?? null;
  const certifications = resume.other.slice(1);

  return (
    <div>
      {summary && (
        <SubSection title="Summary">
          <ExperienceChunkItem chunk={summary} onSave={onSave} onDelete={onDelete}
            render={(content) => <p className="text-sm text-text-secondary leading-relaxed">{content}</p>} />
        </SubSection>
      )}

      {resume.work_experience.length > 0 && (
        <SubSection title="Work Experience">
          <div className="space-y-4">
            {resume.work_experience.map((group: WorkExperienceGroup, i: number) => (
              <div key={i}>
                {group.chunks[0] && (
                  <ExperienceGroupHeader group={group} chunkId={group.chunks[0].id} onSaved={onRefetch} />
                )}
                {group.chunks.map((chunk) => (
                  <ExperienceChunkItem key={chunk.id} chunk={chunk} bullet onSave={onSave} onDelete={onDelete}
                    render={(content) => (
                      <div className="flex gap-2 text-sm text-text-secondary leading-relaxed">
                        <span className="text-text-tertiary flex-shrink-0 mt-0.5">·</span>
                        <span>{content}</span>
                      </div>
                    )} />
                ))}
              </div>
            ))}
          </div>
        </SubSection>
      )}

      {resume.skills.length > 0 && (
        <SubSection title="Skills">
          <SkillsGroup chunks={resume.skills} onSave={onSave} onDelete={onDelete} />
        </SubSection>
      )}

      {resume.projects.length > 0 && (
        <SubSection title="Projects">
          <div className="space-y-3">
            {resume.projects.map((group: ProjectGroup, i: number) => (
              <div key={i}>
                {group.group_key && (
                  <p className="text-sm font-medium text-text-primary mb-0.5 pl-3">{group.group_key}</p>
                )}
                {group.chunks.map((chunk) => (
                  <div key={chunk.id}>
                    <ExperienceChunkItem chunk={chunk} onSave={onSave} onDelete={onDelete}
                      render={(content) => <p className="text-sm text-text-secondary leading-relaxed">{content}</p>} />
                    {chunk.technologies && chunk.technologies.length > 0 && (
                      <p className="text-xs text-text-tertiary pl-3 -mt-0.5 mb-1.5">{chunk.technologies.join(', ')}</p>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </SubSection>
      )}

      {resume.education.length > 0 && (
        <SubSection title="Education">
          {resume.education.map((chunk) => (
            <ExperienceChunkItem key={chunk.id} chunk={chunk} onSave={onSave} onDelete={onDelete}
              render={(content) => <p className="text-sm text-text-secondary">{content}</p>} />
          ))}
        </SubSection>
      )}

      {certifications.length > 0 && (
        <SubSection title="Certifications">
          {certifications.map((chunk) => (
            <ExperienceChunkItem key={chunk.id} chunk={chunk} bullet onSave={onSave} onDelete={onDelete}
              render={(content) => (
                <div className="flex gap-2 text-sm text-text-secondary">
                  <span className="text-text-tertiary flex-shrink-0">·</span>
                  <span>{content}</span>
                </div>
              )} />
          ))}
        </SubSection>
      )}
    </div>
  );
}

/* ─── GitHub section ────────────────────────────────────────────────────── */

function GitHubSection({
  github,
  onSave,
  onDelete,
}: {
  github: NonNullable<ExperienceChunksResponse['github']>;
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  if (github.repos.length === 0) {
    return <p className="text-sm text-text-disabled italic">Enrichment in progress — check back shortly.</p>;
  }

  return (
    <div className="space-y-5">
      {github.repos.map((repo: GitHubRepoGroup, i: number) => {
        const projectChunk = repo.chunks.find((c) => c.claim_type === 'project');
        const skillChunks = repo.chunks.filter((c) => c.claim_type === 'skill');
        return (
          <div key={i}>
            <SectionHeader title={repo.group_key ?? 'Unknown repo'} />
            {projectChunk && (
              <ExperienceChunkItem chunk={projectChunk} onSave={onSave} onDelete={onDelete}
                render={(content) => <p className="text-sm text-text-secondary leading-relaxed">{content}</p>} />
            )}
            {skillChunks.length > 0 && (
              <SkillsGroup chunks={skillChunks} onSave={onSave} onDelete={onDelete} />
            )}
          </div>
        );
      })}
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
    'w-full rounded-lg border border-border-default bg-surface-elevated px-2.5 py-2 text-sm text-text-primary ' +
    'placeholder:text-text-disabled outline-none transition-colors duration-100 resize-none ' +
    'focus:border-text-primary focus:shadow-[0_0_0_2px_rgba(0,0,0,0.06)] ' +
    'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.06)]';

  return (
    <div className="mt-3 space-y-2">
      {preview ? (
        <div className="space-y-2">
          <p className="text-sm text-text-secondary">Select the claims you want to add:</p>
          <div className="space-y-1">
            {preview.map((claim, i) => (
              <label key={i} className="flex items-start gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-sunken cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.has(i)}
                  onChange={() => toggleSelect(i)}
                  className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 accent-brand-primary"
                />
                <span className="text-sm text-text-secondary">{claim}</span>
              </label>
            ))}
          </div>
          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={handleConfirm}
              disabled={persisting || selected.size === 0}
              className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[8px] text-xs font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {persisting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              Add {selected.size > 0 ? `${selected.size} ` : ''}selected
            </button>
            <button type="button" onClick={reset} className="text-xs text-text-tertiary hover:text-text-secondary transition-colors">
              Cancel
            </button>
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
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleParseAndAdd();
            }}
          />
          <button
            type="button"
            onClick={handleParseAndAdd}
            disabled={parsing || !text.trim()}
            className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[8px] text-xs font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity"
          >
            {parsing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
            {parsing ? 'Parsing…' : 'Parse & Add'}
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Additional Experience section (user_input) ────────────────────────── */

function AdditionalExperienceSection({
  chunks,
  onSave,
  onDelete,
  onAdded,
}: {
  chunks: ExperienceChunk[];
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onAdded: (newChunks: ExperienceChunk[]) => void;
}) {
  return (
    <div>
      {chunks.length > 0 && (
        <div className="mb-2">
          {chunks.map((chunk) => (
            <ExperienceChunkItem key={chunk.id} chunk={chunk} onSave={onSave} onDelete={onDelete}
              render={(content) => <p className="text-sm text-text-secondary leading-relaxed">{content}</p>} />
          ))}
        </div>
      )}
      <AddExperienceForm onAdded={onAdded} />
    </div>
  );
}

/* ─── Gap Responses section ─────────────────────────────────────────────── */

function GapResponseSection({
  chunks,
  onSave,
  onDelete,
}: {
  chunks: ExperienceChunk[];
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  return (
    <div className="space-y-3">
      {chunks.map((chunk) => {
        const question = chunk.chunk_metadata?.question;
        return (
          <div key={chunk.id} className="border border-border-subtle rounded-lg px-3 py-2.5 bg-surface-elevated">
            {question && (
              <p className="text-xs text-text-disabled italic leading-relaxed mb-2">{question}</p>
            )}
            <ExperienceChunkItem chunk={chunk} onSave={onSave} onDelete={onDelete}
              render={(content) => <p className="text-sm text-text-secondary leading-relaxed">{content}</p>} />
          </div>
        );
      })}
    </div>
  );
}

/* ─── Top-level section block ───────────────────────────────────────────── */

function ProfileSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="pt-8 border-t border-zinc-950/5 dark:border-white/5 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-medium text-text-primary mb-4">{title}</h3>
      {children}
    </div>
  );
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

  const hasResume = !!data?.resume;
  const hasGithub = !!data?.github;
  const hasUserInput = (data?.user_input?.length ?? 0) > 0;
  const hasGapResponse = (data?.gap_response?.length ?? 0) > 0;
  const hasAnything = hasResume || hasGithub || hasUserInput || hasGapResponse;

  return (
    <div className="space-y-0">
      {hasResume && (
        <ProfileSection title="Resume">
          <ResumeSection resume={data!.resume!} onSave={handleSave} onDelete={handleDelete} onRefetch={fetchChunks} />
        </ProfileSection>
      )}

      {hasGithub && (
        <ProfileSection title="GitHub">
          <GitHubSection github={data!.github!} onSave={handleSave} onDelete={handleDelete} />
        </ProfileSection>
      )}

      <ProfileSection title="Additional Experience">
        <AdditionalExperienceSection
          chunks={data?.user_input ?? []}
          onSave={handleSave}
          onDelete={handleDelete}
          onAdded={handleAdded}
        />
      </ProfileSection>

      {hasGapResponse && (
        <ProfileSection title="Gap Responses">
          <GapResponseSection chunks={data!.gap_response!} onSave={handleSave} onDelete={handleDelete} />
        </ProfileSection>
      )}

      {!hasAnything && !loading && (
        <p className="text-sm text-text-disabled italic">No parsed data available yet.</p>
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
