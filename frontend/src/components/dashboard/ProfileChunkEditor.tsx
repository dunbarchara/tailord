'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, Pencil, Trash2, Check, Loader2, Plus, X, GitBranch, MoreHorizontal, Link, Link2Off } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import type {
  ExperienceClaim,
  ExperienceClaimsResponse,
  ExperienceGroup,
  WorkExperienceGroup,
} from '@/types';

/* ─── Content normalizer ─────────────────────────────────────────────────── */

/** PDF extraction often injects mid-sentence line breaks — strip them. */
const normalizeContent = (s: string) => s.replace(/\s*\n\s*/g, ' ').replace(/  +/g, ' ').trim();

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

/* ─── TableRow ───────────────────────────────────────────────────────────── */
/*                                                                            */
/* The shared primitive for every interactive row inside a table.            */
/* - isExpanded is lifted to the parent (one-open-at-a-time per table).      */
/* - editing is local state; entering edit mode switches the header from a   */
/*   <button> to a <div> so the in-place <textarea> is valid HTML.           */
/* - Collapsing externally (isExpanded → false) resets editing + value.      */

interface TableRowProps {
  content: string;
  isGroupHeader?: boolean; // smaller label styling for group-key rows
  context?: string;        // optional label above content (e.g. gap question)
  isExpanded: boolean;
  onExpand: () => void;
  onSave: (newContent: string) => Promise<void>;
  onDelete: () => Promise<void>;
  onMove?: () => void;     // optional: open "Move to group" dialog in parent
  isLast?: boolean;
  readOnly?: boolean;
}

function TableRow({
  content,
  isGroupHeader: _isGroupHeader = false,
  context,
  isExpanded,
  onExpand,
  onSave,
  onDelete,
  onMove,
  isLast = false,
  readOnly = false,
}: TableRowProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(() => normalizeContent(content));
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Keep value in sync when content prop changes (e.g. after a save)
  useEffect(() => {
    if (!editing) setValue(normalizeContent(content));
  }, [content, editing]);

  // Auto-size textarea and focus when entering edit mode
  useEffect(() => {
    if (editing && textareaRef.current) {
      const el = textareaRef.current;
      el.style.height = '0px';
      el.style.height = `${el.scrollHeight}px`;
      el.focus();
    }
  }, [editing]);

  // When collapsed externally, exit editing and reset
  useEffect(() => {
    if (!isExpanded) {
      setEditing(false);
      setValue(normalizeContent(content));
    }
    // intentionally omit `content` — we only want to react to expansion changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isExpanded]);

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed === content) { setEditing(false); return; }
    setSaving(true);
    try { await onSave(trimmed); setEditing(false); } finally { setSaving(false); }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try { await onDelete(); } finally { setDeleting(false); }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    e.target.style.height = '0px';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setValue(content); setEditing(false); }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
  };

  const headerBase = 'w-full flex items-start gap-3 px-2 py-1 text-left transition-colors duration-100';
  const headerExpanded = isExpanded ? 'bg-surface-base border-b ' : '';

  return (
    <div className={cn(!isLast && 'border-b ')}>

      {/* ── Header: button when idle, div when editing (textarea inside) ── */}
      {editing ? (
        <div className={cn(headerBase, 'bg-surface-base border-b ')}>
          <div className="flex-1 min-w-0 flex gap-2">
            <textarea
              ref={textareaRef}
              value={value}
              rows={1}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              className={cn(
                'flex-1 bg-transparent resize-none overflow-hidden outline-none p-0 leading-relaxed text-sm text-text-primary'
              )}
            />
          </div>
          {/* Chevron kept visible but static while editing */}
          <ChevronDown className="h-3.5 w-3.5 text-text-disabled flex-shrink-0 mt-0.5 rotate-180" />
        </div>
      ) : readOnly ? (
        <div className={cn(headerBase)}>
          <div className="flex-1 min-w-0">
            {context && (
              <p className="text-xs text-text-disabled italic mb-1 leading-relaxed">{context}</p>
            )}
            <p className="text-sm text-text-secondary leading-relaxed">
                {normalizeContent(content)}
              </p>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={onExpand}
          className={cn(
            headerBase,
            'cursor-pointer hover:bg-surface-base',
            headerExpanded,
          )}
        >
          <div className="flex-1 min-w-0">
            {context && (
              <p className="text-xs text-text-disabled italic mb-1 leading-relaxed">{context}</p>
            )}
            <p className="text-sm text-text-secondary leading-relaxed">
                {normalizeContent(content)}
              </p>
          </div>
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 text-text-disabled flex-shrink-0 mt-0.5 transition-transform duration-150',
              isExpanded && 'rotate-180',
            )}
          />
        </button>
      )}

      {/* ── Controls: animates open/closed based on isExpanded ── */}
      {!readOnly && <div className={cn('grid transition-all duration-150', isExpanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
        <div className="overflow-hidden">
          <div className="px-2 py-1 flex items-center gap-0.5">
            {editing ? (
              <>
                <button type="button" onClick={handleSave} disabled={saving || !value.trim()} className={saveBtnCls}>
                  {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                  Save
                </button>
                <button type="button" onClick={() => { setValue(content); setEditing(false); }} className={cancelBtnCls}>
                  <X className="h-3 w-3" />
                  Cancel
                </button>
                <span className="text-xs text-text-disabled ml-1">⌘↵</span>
              </>
            ) : (
              <>
                <button type="button" onClick={() => setEditing(true)} className={actionBtnCls}>
                  <Pencil className="h-3 w-3" />
                  Edit
                </button>
                {onMove && (
                  <button type="button" onClick={onMove} className={actionBtnCls}>
                    <Link className="h-3 w-3" />
                    Move
                  </button>
                )}
                <button type="button" onClick={handleDelete} disabled={deleting} className={deleteBtnCls}>
                  {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                  Delete
                </button>
              </>
            )}
          </div>
        </div>
      </div>}

    </div>
  );
}

/* ─── ExperienceTable ────────────────────────────────────────────────────── */
/*                                                                            */
/* One bordered container. Manages expandedId so only one row is open at a   */
/* time. Optionally renders a group-key header row before the chunk rows.    */

const GROUP_KEY_ID = '__group__';

function ExperienceTable({
  groupLabel,
  groupChunkIds,
  chunks,
  context,
  onSave,
  onSaveGroupKey,
  onDelete,
  onDeleteGroup,
  readOnly = false,
}: {
  groupLabel?: string;
  groupChunkIds?: string[];
  chunks: ExperienceClaim[];
  context?: (chunk: ExperienceClaim) => string | undefined;
  onSave: (id: string, content: string) => Promise<void>;
  onSaveGroupKey?: (chunkIds: string[], newLabel: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onDeleteGroup?: (chunkIds: string[]) => Promise<void>;
  readOnly?: boolean;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tableExpanded, setTableExpanded] = useState(false);

  const toggle = (id: string) =>
    setExpandedId((prev) => (prev === id ? null : id));

  if (!groupLabel && chunks.length === 0) return null;

  const isGrouped = !!(groupLabel && groupChunkIds && onSaveGroupKey && onDeleteGroup);

  if (isGrouped) {
    return (
      <div>
        {/* Group-key header — bottom-right corner open, flowing into indented rows */}
        <div className="rounded-tl-md rounded-tr-md rounded-bl-md border  overflow-hidden">
          <TableRow
            content={groupLabel!}
            isGroupHeader
            isExpanded={expandedId === GROUP_KEY_ID}
            onExpand={() => toggle(GROUP_KEY_ID)}
            onSave={(newLabel) => onSaveGroupKey!(groupChunkIds!, newLabel)}
            onDelete={() => onDeleteGroup!(groupChunkIds!)}
            isLast
            readOnly={readOnly}
          />
        </div>

        {/* Indented rows */}
        {chunks.length > 0 && (
          <div className="ml-6 border border-t-0  rounded-b-md overflow-hidden">
            {chunks.length > 3 ? (
              <>
                {/* Always-visible toggle row */}
                <button
                  type="button"
                  onClick={() => { setTableExpanded((v) => !v); if (tableExpanded) setExpandedId(null); }}
                  className="w-full flex items-center gap-2 px-2 py-1 text-left hover:bg-surface-base transition-colors duration-100"
                >
                  {tableExpanded
                    ? <ChevronUp className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
                    : <ChevronDown className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />}
                  <span className="text-sm text-text-tertiary">
                    {chunks.length} {chunks.length === 1 ? 'item' : 'items'}
                  </span>
                </button>
                {tableExpanded && chunks.map((chunk, i) => (
                  <TableRow
                    key={chunk.id}
                    content={chunk.content}
                    context={context?.(chunk)}
                    isExpanded={expandedId === chunk.id}
                    onExpand={() => toggle(chunk.id)}
                    onSave={(newContent) => onSave(chunk.id, newContent)}
                    onDelete={() => onDelete(chunk.id)}
                    isLast={i === chunks.length - 1}
                    readOnly={readOnly}
                  />
                ))}
              </>
            ) : (
              chunks.map((chunk, i) => (
                <TableRow
                  key={chunk.id}
                  content={chunk.content}
                  context={context?.(chunk)}
                  isExpanded={expandedId === chunk.id}
                  onExpand={() => toggle(chunk.id)}
                  onSave={(newContent) => onSave(chunk.id, newContent)}
                  onDelete={() => onDelete(chunk.id)}
                  isLast={i === chunks.length - 1}
                  readOnly={readOnly}
                />
              ))
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-md border  overflow-hidden">
      {chunks.map((chunk, i) => (
        <TableRow
          key={chunk.id}
          content={chunk.content}
          context={context?.(chunk)}
          isExpanded={expandedId === chunk.id}
          onExpand={() => toggle(chunk.id)}
          onSave={(newContent) => onSave(chunk.id, newContent)}
          onDelete={() => onDelete(chunk.id)}
          isLast={i === chunks.length - 1}
          readOnly={readOnly}
        />
      ))}
    </div>
  );
}

/* ─── SkillsTable ────────────────────────────────────────────────────────── */
/*                                                                            */
/* One bordered container with a static "Skills" label row (non-interactive) */
/* and a single aggregate row that expands to individual deletable pills.    */

function SkillsTable({
  chunks,
  onDelete,
  onSave,
  readOnly = false,
}: {
  chunks: ExperienceClaim[];
  onDelete: (id: string) => Promise<void>;
  onSave: (id: string, content: string) => Promise<void>;
  readOnly?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingPillId, setEditingPillId] = useState<string | null>(null);
  const [editingPillValue, setEditingPillValue] = useState('');
  const [savingPillId, setSavingPillId] = useState<string | null>(null);

  if (chunks.length === 0) return null;

  const preview = chunks.map((c) => c.content).join(' · ');

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try { await onDelete(id); } finally { setDeletingId(null); }
  };

  const startPillEdit = (chunk: ExperienceClaim) => {
    setEditingPillId(chunk.id);
    setEditingPillValue(chunk.content);
  };

  const cancelPillEdit = () => {
    setEditingPillId(null);
    setEditingPillValue('');
  };

  const savePill = async (id: string) => {
    const trimmed = editingPillValue.trim();
    if (!trimmed) { cancelPillEdit(); return; }
    setSavingPillId(id);
    try { await onSave(id, trimmed); } finally { setSavingPillId(null); cancelPillEdit(); }
  };

  return (
    <div className="rounded-md border overflow-hidden">

      {/* Aggregate row */}
      <div>
        <button
          type="button"
          onClick={() => setExpanded((o) => !o)}
          className={cn(
            'w-full flex items-start gap-3 px-2 py-1 text-left cursor-pointer transition-colors duration-100',
            expanded ? 'bg-surface-base border-b' : 'hover:bg-surface-base',
          )}
        >
          <p className="flex-1 text-sm text-text-secondary leading-relaxed truncate">{preview}</p>
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 text-text-disabled flex-shrink-0 mt-0.5 transition-transform duration-150',
              expanded && 'rotate-180',
            )}
          />
        </button>

        <div className={cn('grid transition-all duration-150', expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
          <div className="overflow-hidden">
            <div className="px-2 py-1 flex flex-wrap gap-1.5">
              {chunks.map((chunk) => (
                readOnly ? (
                  <span
                    key={chunk.id}
                    className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-surface-overlay text-text-secondary border "
                  >
                    {chunk.content}
                  </span>
                ) : editingPillId === chunk.id ? (
                  <span
                    key={chunk.id}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-surface-overlay text-text-secondary border "
                  >
                    <input
                      // eslint-disable-next-line jsx-a11y/no-autofocus -- appears in response to a user click; focus is expected
                      autoFocus
                      value={editingPillValue}
                      onChange={(e) => setEditingPillValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') savePill(chunk.id);
                        if (e.key === 'Escape') cancelPillEdit();
                      }}
                      className="bg-transparent outline-none min-w-0"
                      style={{ width: `${Math.max(editingPillValue.length, 3)}ch` }}
                    />
                    <button
                      type="button"
                      onClick={() => savePill(chunk.id)}
                      disabled={savingPillId === chunk.id}
                      className="text-text-disabled hover:text-text-primary transition-colors ml-0.5 flex-shrink-0"
                    >
                      {savingPillId === chunk.id
                        ? <Loader2 className="h-2.5 w-2.5 animate-spin" />
                        : <Check className="h-2.5 w-2.5" />}
                    </button>
                  </span>
                ) : (
                  <span
                    key={chunk.id}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-surface-overlay text-text-secondary border "
                  >
                    <button
                      type="button"
                      onClick={() => startPillEdit(chunk)}
                      className="hover:text-text-primary transition-colors"
                    >
                      {chunk.content}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(chunk.id)}
                      disabled={deletingId === chunk.id}
                      className="text-text-disabled hover:text-error transition-colors ml-0.5 flex-shrink-0"
                    >
                      {deletingId === chunk.id
                        ? <Loader2 className="h-2.5 w-2.5 animate-spin" />
                        : <X className="h-2.5 w-2.5" />}
                    </button>
                  </span>
                )
              ))}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}

/* ─── InlineSkillsRow ────────────────────────────────────────────────────── */
/*                                                                            */
/* Aggregate pill row for skills nested inside a repo table. No header label.*/

function InlineSkillsRow({
  chunks,
  onDelete,
  onSave,
  readOnly = false,
}: {
  chunks: ExperienceClaim[];
  onDelete: (id: string) => Promise<void>;
  onSave: (id: string, content: string) => Promise<void>;
  readOnly?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingPillId, setEditingPillId] = useState<string | null>(null);
  const [editingPillValue, setEditingPillValue] = useState('');
  const [savingPillId, setSavingPillId] = useState<string | null>(null);

  if (chunks.length === 0) return null;

  const preview = chunks.map((c) => c.content).join(' · ');

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try { await onDelete(id); } finally { setDeletingId(null); }
  };

  const startPillEdit = (chunk: ExperienceClaim) => {
    setEditingPillId(chunk.id);
    setEditingPillValue(chunk.content);
  };

  const cancelPillEdit = () => {
    setEditingPillId(null);
    setEditingPillValue('');
  };

  const savePill = async (id: string) => {
    const trimmed = editingPillValue.trim();
    if (!trimmed) { cancelPillEdit(); return; }
    setSavingPillId(id);
    try { await onSave(id, trimmed); } finally { setSavingPillId(null); cancelPillEdit(); }
  };

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((o) => !o)}
        className={cn(
          'w-full flex items-start gap-3 px-2 py-1 text-left cursor-pointer transition-colors duration-100',
          expanded ? 'bg-surface-base border-b ' : 'hover:bg-surface-base',
        )}
      >
        <p className="flex-1 text-sm text-text-secondary leading-relaxed truncate">{preview}</p>
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 text-text-disabled flex-shrink-0 mt-0.5 transition-transform duration-150',
            expanded && 'rotate-180',
          )}
        />
      </button>
      <div className={cn('grid transition-all duration-150', expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
        <div className="overflow-hidden">
          <div className="px-2 py-1 flex flex-wrap gap-1.5">
            {chunks.map((chunk) => (
              readOnly ? (
                <span
                  key={chunk.id}
                  className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-surface-overlay text-text-secondary border "
                >
                  {chunk.content}
                </span>
              ) : editingPillId === chunk.id ? (
                <span
                  key={chunk.id}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-surface-overlay text-text-secondary border "
                >
                  <input
                    // eslint-disable-next-line jsx-a11y/no-autofocus -- appears in response to a user click; focus is expected
                    autoFocus
                    value={editingPillValue}
                    onChange={(e) => setEditingPillValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') savePill(chunk.id);
                      if (e.key === 'Escape') cancelPillEdit();
                    }}
                    className="bg-transparent outline-none min-w-0"
                    style={{ width: `${Math.max(editingPillValue.length, 3)}ch` }}
                  />
                  <button
                    type="button"
                    onClick={() => savePill(chunk.id)}
                    disabled={savingPillId === chunk.id}
                    className="text-text-disabled hover:text-text-primary transition-colors ml-0.5 flex-shrink-0"
                  >
                    {savingPillId === chunk.id
                      ? <Loader2 className="h-2.5 w-2.5 animate-spin" />
                      : <Check className="h-2.5 w-2.5" />}
                  </button>
                </span>
              ) : (
                <span
                  key={chunk.id}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-surface-overlay text-text-secondary border "
                >
                  <button
                    type="button"
                    onClick={() => startPillEdit(chunk)}
                    className="hover:text-text-primary transition-colors"
                  >
                    {chunk.content}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(chunk.id)}
                    disabled={deletingId === chunk.id}
                    className="text-text-disabled hover:text-error transition-colors ml-0.5 flex-shrink-0"
                  >
                    {deletingId === chunk.id
                      ? <Loader2 className="h-2.5 w-2.5 animate-spin" />
                      : <X className="h-2.5 w-2.5" />}
                  </button>
                </span>
              )
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── RepoTable ──────────────────────────────────────────────────────────── */
/*                                                                            */
/* GitHub repo variant: non-editable header, skill chunks as pill row,       */
/* non-skill chunks as TableRows. Collapsible via count card / collapse card.*/

function RepoTable({
  repoName,
  repoGroup,
  chunks,
  onSave,
  onDelete,
  onAssociate,
  onClearAssociation,
  onMoveChunk,
  readOnly = false,
}: {
  repoName: string;
  repoGroup?: ExperienceGroup | null;
  chunks: ExperienceClaim[];
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onAssociate?: (repoGroupId: string) => void;
  onClearAssociation?: (repoGroupId: string) => void;
  onMoveChunk?: (claimId: string) => void;
  readOnly?: boolean;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [tableExpanded, setTableExpanded] = useState(false);

  const toggle = (id: string) =>
    setExpandedId((prev) => (prev === id ? null : id));

  const skillChunks = chunks.filter((c) => c.claim_type === 'skill');
  const contentChunks = chunks.filter((c) => c.claim_type !== 'skill');
  const itemCount = contentChunks.length + (skillChunks.length > 0 ? 1 : 0);

  if (chunks.length === 0) return null;

  const hasParent = !!(repoGroup?.parent_group_id);

  return (
    <div>
      {/* Repo name header — static label with optional association dropdown */}
      <div className="rounded-bl-md border-b overflow-hidden">
        <div className="flex items-center px-2 py-1 gap-1">
          <GitBranch className="size-3.5 text-text-tertiary flex-shrink-0" />
          <p className="flex-1 text-sm text-text-tertiary">{repoName}</p>
          {!readOnly && repoGroup && (onAssociate || onClearAssociation) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="p-0.5 rounded text-text-disabled hover:text-text-secondary hover:bg-surface-sunken transition-colors flex-shrink-0"
                  aria-label="Repo options"
                >
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                {onAssociate && (
                  <DropdownMenuItem onSelect={() => onAssociate(repoGroup.id)}>
                    <Link className="h-3.5 w-3.5 mr-2" />
                    Associate with a role
                  </DropdownMenuItem>
                )}
                {hasParent && onClearAssociation && (
                  <DropdownMenuItem onSelect={() => onClearAssociation(repoGroup.id)}>
                    <Link2Off className="h-3.5 w-3.5 mr-2" />
                    Remove association
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      {/* Indented rows */}
      {itemCount > 0 && (
        <div className="ml-6 border border-t-0  rounded-b-md overflow-hidden">
          {itemCount > 3 ? (
            <>
              {/* Always-visible toggle row */}
              <button
                type="button"
                onClick={() => { setTableExpanded((v) => !v); if (tableExpanded) setExpandedId(null); }}
                className="w-full flex items-center gap-2 px-2 py-1 text-left hover:bg-surface-base transition-colors duration-100"
              >
                {tableExpanded
                  ? <ChevronUp className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
                  : <ChevronDown className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />}
                <span className="text-sm text-text-tertiary">
                  {itemCount} {itemCount === 1 ? 'item' : 'items'}
                </span>
              </button>
              {tableExpanded && (
                <>
                  {contentChunks.map((chunk, i) => (
                    <TableRow
                      key={chunk.id}
                      content={chunk.content}
                      isExpanded={expandedId === chunk.id}
                      onExpand={() => toggle(chunk.id)}
                      onSave={(newContent) => onSave(chunk.id, newContent)}
                      onDelete={() => onDelete(chunk.id)}
                      onMove={onMoveChunk ? () => onMoveChunk(chunk.id) : undefined}
                      isLast={skillChunks.length === 0 && i === contentChunks.length - 1}
                      readOnly={readOnly}
                    />
                  ))}
                  {skillChunks.length > 0 && (
                    <InlineSkillsRow chunks={skillChunks} onDelete={onDelete} onSave={onSave} readOnly={readOnly} />
                  )}
                </>
              )}
            </>
          ) : (
            <>
              {contentChunks.map((chunk, i) => (
                <TableRow
                  key={chunk.id}
                  content={chunk.content}
                  isExpanded={expandedId === chunk.id}
                  onExpand={() => toggle(chunk.id)}
                  onSave={(newContent) => onSave(chunk.id, newContent)}
                  onDelete={() => onDelete(chunk.id)}
                  onMove={onMoveChunk ? () => onMoveChunk(chunk.id) : undefined}
                  isLast={skillChunks.length === 0 && i === contentChunks.length - 1}
                  readOnly={readOnly}
                />
              ))}
              {skillChunks.length > 0 && (
                <InlineSkillsRow chunks={skillChunks} onDelete={onDelete} onSave={onSave} readOnly={readOnly} />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── ActivitySection ────────────────────────────────────────────────────── */

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

/* ─── AddExperienceForm ──────────────────────────────────────────────────── */

function AddExperienceForm({ onAdded, readOnly = false }: { onAdded: (chunks: ExperienceClaim[]) => void; readOnly?: boolean }) {
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
      const res = await fetch('/api/experience/user-input/claims', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chunks }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toastError(err.detail ?? 'Failed to save');
        return;
      }
      const data: { claim_ids: string[] } = await res.json();
      const now = new Date().toISOString();
      const newChunks: ExperienceClaim[] = chunks.map((content, i) => ({
        id: data.claim_ids[i] ?? `temp-${i}`,
        source_type: 'user_input',
        source_ref: null,
        claim_type: 'other',
        content,
        group_key: null,
        group_id: null,
        date_range: null,
        keywords: null,
        provenance_metadata: null,
        original_content: null,
        status: 'active' as const,
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
    'w-full rounded-md border border-border-default bg-surface-elevated px-3 py-2.5 text-sm text-text-primary ' +
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
              <label key={i} className="flex items-start gap-2 px-2 py-1.5 rounded-md hover:bg-surface-sunken cursor-pointer">
                <input type="checkbox" checked={selected.has(i)} onChange={() => toggleSelect(i)} className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 accent-brand-primary cursor-pointer" />
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
            disabled={readOnly}
            className={cn(textareaCls, readOnly && 'opacity-50 cursor-not-allowed')}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleParseAndAdd(); }}
          />
          <button type="button" onClick={handleParseAndAdd} disabled={readOnly || parsing || !text.trim()}
            className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-[8px] text-xs font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity">
            {parsing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
            {parsing ? 'Parsing…' : 'Parse & Add'}
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Group-key helpers ──────────────────────────────────────────────────── */

function formatWorkGroupKey(group: WorkExperienceGroup): string {
  const parts = (group.group_key ?? '').split(' | ').filter(Boolean);
  let label = parts.join(' · ');
  if (group.date_range) label += `  ·  ${group.date_range}`;
  return label || 'Unknown role';
}

/* ─── ProfileChunkEditor ─────────────────────────────────────────────────── */

export function ProfileChunkEditor({ refreshKey, initialData, readOnly }: { refreshKey?: number; initialData?: ExperienceClaimsResponse; readOnly?: boolean }) {
  const [data, setData] = useState<ExperienceClaimsResponse | null>(initialData ?? null);
  const [loading, setLoading] = useState(!initialData);
  const [groups, setGroups] = useState<ExperienceGroup[]>([]);

  // Association dialog state: which repo group the user is associating
  const [associatingRepoGroupId, setAssociatingRepoGroupId] = useState<string | null>(null);
  const [selectedRoleGroupId, setSelectedRoleGroupId] = useState<string>('');
  const [associating, setAssociating] = useState(false);

  // Move claim dialog state
  const [movingClaimId, setMovingClaimId] = useState<string | null>(null);
  const [selectedMoveGroupId, setSelectedMoveGroupId] = useState<string>('');
  const [moving, setMoving] = useState(false);

  const fetchGroups = useCallback(async () => {
    try {
      const res = await fetch('/api/experience/groups');
      if (!res.ok) return;
      const json: ExperienceGroup[] = await res.json();
      setGroups(json);
    } catch { /* ignore */ }
  }, []);

  const fetchChunks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/experience/claims');
      if (!res.ok) return;
      const json: ExperienceClaimsResponse = await res.json();
      setData(json);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialData) return;
    fetchChunks();
    fetchGroups();
  }, [fetchChunks, fetchGroups, refreshKey, initialData]);

  const handleSave = async (id: string, content: string) => {
    const res = await fetch(`/api/experience/claims/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? 'Failed to save');
    }
    const updated: ExperienceClaim = await res.json();
    setData((prev) => prev ? patchChunkInResponse(prev, updated) : prev);
  };

  const handleDelete = async (id: string) => {
    const res = await fetch(`/api/experience/claims/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? 'Failed to delete');
      return;
    }
    setData((prev) => prev ? removeChunkFromResponse(prev, id) : prev);
  };

  /** Rename a group key across all its chunks, then refetch. */
  const handleSaveGroupKey = async (chunkIds: string[], newLabel: string) => {
    const results = await Promise.all(
      chunkIds.map((id) =>
        fetch(`/api/experience/claims/${id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ group_key: newLabel }),
        }),
      ),
    );
    if (results.some((r) => !r.ok)) {
      toastError('Failed to rename group');
      return;
    }
    await fetchChunks();
  };

  /** Delete every chunk in a group. */
  const handleDeleteGroup = async (chunkIds: string[]) => {
    const results = await Promise.all(
      chunkIds.map((id) => fetch(`/api/experience/claims/${id}`, { method: 'DELETE' })),
    );
    if (results.some((r) => !r.ok)) {
      toastError('Some items could not be deleted');
    }
    setData((prev) =>
      prev ? chunkIds.reduce((acc, id) => removeChunkFromResponse(acc, id), prev) : prev,
    );
  };

  const handleAdded = (newChunks: ExperienceClaim[]) => {
    setData((prev) => {
      if (!prev) return prev;
      return { ...prev, user_input: [...(prev.user_input ?? []), ...newChunks] };
    });
  };

  const roleGroups = groups.filter((g) => g.group_type === 'role');

  const findRepoGroup = (repoName: string): ExperienceGroup | null =>
    groups.find((g) => g.source_type === 'github' && (g.source_ref === repoName || g.name === repoName)) ?? null;

  const handleOpenAssociate = (repoGroupId: string) => {
    const repoGroup = groups.find((g) => g.id === repoGroupId);
    const preselect = repoGroup?.suggested_parent_id ?? repoGroup?.parent_group_id ?? '';
    setSelectedRoleGroupId(preselect);
    setAssociatingRepoGroupId(repoGroupId);
  };

  const handleConfirmAssociate = async () => {
    if (!associatingRepoGroupId || !selectedRoleGroupId) return;
    setAssociating(true);
    try {
      const res = await fetch(`/api/experience/groups/${associatingRepoGroupId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parent_group_id: selectedRoleGroupId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toastError(err.detail ?? 'Failed to associate');
        return;
      }
      await fetchGroups();
      toast.success('Repo linked — tailorings will treat them as unified experience.');
    } finally {
      setAssociating(false);
      setAssociatingRepoGroupId(null);
    }
  };

  const handleClearAssociation = async (repoGroupId: string) => {
    const res = await fetch(`/api/experience/groups/${repoGroupId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parent_group_id: '' }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toastError(err.detail ?? 'Failed to remove association');
      return;
    }
    await fetchGroups();
    toast.success('Association removed.');
  };

  const handleOpenMoveChunk = (claimId: string) => {
    setSelectedMoveGroupId('');
    setMovingClaimId(claimId);
  };

  const handleConfirmMove = async () => {
    if (!movingClaimId) return;
    setMoving(true);
    try {
      const res = await fetch(`/api/experience/claims/${movingClaimId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_id: selectedMoveGroupId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toastError(err.detail ?? 'Failed to move claim');
        return;
      }
      const updated: ExperienceClaim = await res.json();
      setData((prev) => prev ? patchChunkInResponse(prev, updated) : prev);
      toast.success('Claim moved.');
    } finally {
      setMoving(false);
      setMovingClaimId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-xs text-text-tertiary">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading…
      </div>
    );
  }

  const resume = data?.resume ?? null;
  const hasResume = !!(
    resume &&
    (resume.other.length > 0 ||
      resume.work_experience.length > 0 ||
      resume.skills.length > 0 ||
      resume.projects.length > 0 ||
      resume.education.length > 0)
  );
  const hasGithub = !!(data?.github?.repos?.some((r) => r.chunks.length > 0));
  const hasGapResponse = !!(data?.gap_response?.length);
  const hasPartialResponse = !!(data?.partial_response?.length);

  return (
    <div className="space-y-10">

      {/* ── Resume ── */}
      {hasResume && (
        <ActivitySection title="Resume" description="Extracted from your uploaded resume">
          <div className="space-y-2">

            {/* Summary — standalone single-row table */}
            {resume!.other[0] && (
              <ExperienceTable
                chunks={[resume!.other[0]]}
                onSave={handleSave}
                onDelete={handleDelete}
                readOnly={readOnly}
              />
            )}

            {/* Work experience — one table per position */}
            {resume!.work_experience.map((g, i) => (
              <ExperienceTable
                key={i}
                groupLabel={formatWorkGroupKey(g)}
                groupChunkIds={g.chunks.map((c) => c.id)}
                chunks={g.chunks}
                onSave={handleSave}
                onSaveGroupKey={handleSaveGroupKey}
                onDelete={handleDelete}
                onDeleteGroup={handleDeleteGroup}
                readOnly={readOnly}
              />
            ))}

            {/* Skills — single aggregate table */}
            {resume!.skills.length > 0 && (
              <SkillsTable
                chunks={resume!.skills}
                onDelete={handleDelete}
                onSave={handleSave}
                readOnly={readOnly}
              />
            )}

            {/* Projects — one table per project */}
            {resume!.projects.map((p, i) => (
              <ExperienceTable
                key={i}
                groupLabel={p.group_key ?? 'Project'}
                groupChunkIds={p.chunks.map((c) => c.id)}
                chunks={p.chunks}
                onSave={handleSave}
                onSaveGroupKey={handleSaveGroupKey}
                onDelete={handleDelete}
                onDeleteGroup={handleDeleteGroup}
                readOnly={readOnly}
              />
            ))}

            {/* Education — one table for all entries */}
            {resume!.education.length > 0 && (
              <ExperienceTable
                chunks={resume!.education}
                onSave={handleSave}
                onDelete={handleDelete}
                readOnly={readOnly}
              />
            )}

            {/* Certifications — one table for remaining "other" chunks */}
            {resume!.other.slice(1).length > 0 && (
              <ExperienceTable
                chunks={resume!.other.slice(1)}
                onSave={handleSave}
                onDelete={handleDelete}
                readOnly={readOnly}
              />
            )}

          </div>
        </ActivitySection>
      )}

      {/* ── GitHub ── */}
      {hasGithub && (
        <ActivitySection title="GitHub" description="Enriched from your linked repositories">
          <div className="space-y-2">
            {data!.github!.repos.map((repo, i) => {
              const repoName = repo.group_key ?? 'Unknown repo';
              const repoGroup = findRepoGroup(repoName);
              return (
                <RepoTable
                  key={i}
                  repoName={repoName}
                  repoGroup={repoGroup}
                  chunks={repo.chunks}
                  onSave={handleSave}
                  onDelete={handleDelete}
                  onAssociate={roleGroups.length > 0 ? handleOpenAssociate : undefined}
                  onClearAssociation={handleClearAssociation}
                  onMoveChunk={handleOpenMoveChunk}
                  readOnly={readOnly}
                />
              );
            })}
          </div>
        </ActivitySection>
      )}

      {/* ── Gap Responses ── */}
      {hasGapResponse && (
        <ActivitySection title="Gap Responses" description="Answers to gap questions from your tailorings">
          <div className="space-y-2">
            {data!.gap_response!.map((chunk) => (
              <ExperienceTable
                key={chunk.id}
                chunks={[chunk]}
                context={(c) => c.provenance_metadata?.question}
                onSave={handleSave}
                onDelete={handleDelete}
                readOnly={readOnly}
              />
            ))}
          </div>
        </ActivitySection>
      )}

      {/* ── Path to Strong Responses ── */}
      {hasPartialResponse && (
        <ActivitySection title="Path to Strong" description="Answers to path-to-strong questions from your tailorings">
          <div className="space-y-2">
            {data!.partial_response!.map((chunk) => (
              <ExperienceTable
                key={chunk.id}
                chunks={[chunk]}
                context={(c) => c.provenance_metadata?.question}
                onSave={handleSave}
                onDelete={handleDelete}
                readOnly={readOnly}
              />
            ))}
          </div>
        </ActivitySection>
      )}

      {/* ── Additional Experience ── */}
      <ActivitySection title="Additional Experience" description="Manually added experience and context">
        <AddExperienceForm onAdded={handleAdded} readOnly={readOnly} />
        {data?.user_input?.length ? (
          <ExperienceTable
            chunks={data.user_input}
            onSave={handleSave}
            onDelete={handleDelete}
            readOnly={readOnly}
          />
        ) : null}
      </ActivitySection>

      {/* ── Associate repo with role dialog ── */}
      <Dialog open={!!associatingRepoGroupId} onOpenChange={(o) => { if (!o) setAssociatingRepoGroupId(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Associate with a role</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-text-secondary">
            Select the role this repository belongs to. Tailorings will present them as unified experience.
          </p>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {roleGroups.map((g) => (
              <label
                key={g.id}
                className={cn(
                  'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors',
                  selectedRoleGroupId === g.id ? 'bg-surface-sunken text-text-primary' : 'text-text-secondary hover:bg-surface-base',
                )}
              >
                <input
                  type="radio"
                  name="role-group"
                  value={g.id}
                  checked={selectedRoleGroupId === g.id}
                  onChange={() => setSelectedRoleGroupId(g.id)}
                  className="accent-brand-primary"
                />
                {g.name}
              </label>
            ))}
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setAssociatingRepoGroupId(null)}
              className="text-sm text-text-tertiary hover:text-text-secondary transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirmAssociate}
              disabled={!selectedRoleGroupId || associating}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[8px] text-sm font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {associating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link className="h-3.5 w-3.5" />}
              Associate
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Move claim to group dialog ── */}
      <Dialog open={!!movingClaimId} onOpenChange={(o) => { if (!o) setMovingClaimId(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Move to group</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-text-secondary">
            Choose a group for this claim, or leave blank to make it ungrouped.
          </p>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            <label className={cn('flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors', selectedMoveGroupId === '' ? 'bg-surface-sunken text-text-primary' : 'text-text-secondary hover:bg-surface-base')}>
              <input type="radio" name="move-group" value="" checked={selectedMoveGroupId === ''} onChange={() => setSelectedMoveGroupId('')} className="accent-brand-primary" />
              Ungrouped
            </label>
            {groups.map((g) => (
              <label
                key={g.id}
                className={cn(
                  'flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors',
                  selectedMoveGroupId === g.id ? 'bg-surface-sunken text-text-primary' : 'text-text-secondary hover:bg-surface-base',
                )}
              >
                <input
                  type="radio"
                  name="move-group"
                  value={g.id}
                  checked={selectedMoveGroupId === g.id}
                  onChange={() => setSelectedMoveGroupId(g.id)}
                  className="accent-brand-primary"
                />
                <span className="flex items-center gap-1">
                  {g.source_type === 'github' && <GitBranch className="h-3 w-3 text-text-disabled flex-shrink-0" />}
                  {g.name}
                </span>
              </label>
            ))}
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setMovingClaimId(null)}
              className="text-sm text-text-tertiary hover:text-text-secondary transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirmMove}
              disabled={moving}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[8px] text-sm font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {moving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              Move
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}

/* ─── Response patch helpers ─────────────────────────────────────────────── */

function patchChunkInResponse(
  prev: ExperienceClaimsResponse,
  updated: ExperienceClaim,
): ExperienceClaimsResponse {
  const replaceIn = (chunks: ExperienceClaim[]) =>
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
    partial_response: prev.partial_response ? replaceIn(prev.partial_response) : null,
  };
}

function removeChunkFromResponse(
  prev: ExperienceClaimsResponse,
  id: string,
): ExperienceClaimsResponse {
  const filterOut = (chunks: ExperienceClaim[]) => chunks.filter((c) => c.id !== id);

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

  return {
    ...prev,
    resume: resumeEmpty ? null : newResume,
    github: prev.github
      ? { repos: prev.github.repos.map((r) => ({ ...r, chunks: filterOut(r.chunks) })) }
      : null,
    user_input: prev.user_input ? filterOut(prev.user_input) : null,
    gap_response: prev.gap_response ? filterOut(prev.gap_response) : null,
    partial_response: prev.partial_response ? filterOut(prev.partial_response) : null,
  };
}
