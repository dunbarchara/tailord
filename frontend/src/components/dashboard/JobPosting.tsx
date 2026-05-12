'use client';

import { useState, useRef, useEffect } from 'react';
import { Eye, EyeOff, FolderMinus, FolderPlus, Info, Loader2, Plus, Trash2, Unlink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { groupBySection, groupChunksForAnalysis, scoreBarColor } from '@/lib/chunks';
import type { ChunksResponse, JobChunk } from '@/types';
import { InlineMarkdown } from '@/components/dashboard/InlineMarkdown';
import { TailoringErrorState } from '@/components/dashboard/TailoringErrorState';
import { TailoringHeader } from '@/components/dashboard/TailoringHeader';

interface JobPostingProps {
  data: ChunksResponse | null;
  error: string | null;
  title: string | null;
  company: string | null;
  jobUrl: string | null;
  authorName?: string | null;
  publicMode?: boolean;
  hideHeader?: boolean;
  generationReady?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  editMode?: boolean;
  showHidden?: boolean;
  tailoringId?: string;
  onChunkUpdate?: (chunk: JobChunk) => void;
  onChunkDelete?: (chunkId: string) => void;
  onChunkCreate?: (chunk: JobChunk) => void;
  onSectionRename?: (oldSection: string, newSection: string | null) => void;
}

const SOURCE_LABELS: Record<string, string> = {
  resume: 'Resume',
  github: 'GitHub',
  user_input: 'Direct Input',
  gap_response: 'Direct Input',
  additional_experience: 'Additional Context',
};

function stripMarkdown(text: string): string {
  return text.replace(/\*\*/g, '').replace(/\*/g, '').trim();
}


/* ─── Chunk item ─────────────────────────────────────────────────────────── */

function ChunkItem({
  chunk,
  expandedId,
  setExpandedId,
  publicMode,
  selectedId,
  onSelect,
  editMode,
  isHidden,
  availableSections,
  onChunkUpdate,
  onChunkDelete,
  onSectionPending,
  pendingMove,
}: {
  chunk: JobChunk;
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
  publicMode?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  editMode?: boolean;
  isHidden?: boolean;
  availableSections: string[];
  onChunkUpdate?: (chunk: JobChunk) => void;
  onChunkDelete?: (chunkId: string) => void;
  /** Signals intent to move to a new section — SectionBlock decides what else moves. */
  onSectionPending?: (chunk: JobChunk, newSection: string | null) => void;
  /** Set by SectionBlock when this chunk is the one being moved and peers exist. */
  pendingMove?: {
    toSection: string | null;
    allCount: number;
    subsequentCount: number;
    onMoveOnly: () => void;
    onMoveSubsequent: () => void;
    onMoveAll: () => void;
    onCancel: () => void;
  } | null;
}) {
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [editingContent, setEditingContent] = useState(false);
  const [draftContent, setDraftContent] = useState(chunk.content);
  const [sectionPickerOpen, setSectionPickerOpen] = useState(false);
  const [newGroupDraft, setNewGroupDraft] = useState('');
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!sectionPickerOpen) return;
    function handleOutside(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setSectionPickerOpen(false);
        setNewGroupDraft('');
      }
    }
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [sectionPickerOpen]);

  const barColor = scoreBarColor(chunk.match_score, publicMode);
  const isInteractive = barColor !== null;

  /** Apply a local field change and notify parent — no API call. */
  function applyChunkEdit(
    fields: Partial<Pick<JobChunk, 'content' | 'should_render' | 'is_requirement' | 'chunk_type'>>,
  ) {
    onChunkUpdate?.({ ...chunk, ...fields });
  }

  function selectSection(newSection: string | null) {
    setSectionPickerOpen(false);
    setNewGroupDraft('');
    if (newSection !== chunk.section) {
      onSectionPending?.(chunk, newSection);
    }
  }

  function handleDelete() {
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      deleteTimerRef.current = setTimeout(() => setDeleteConfirm(false), 2500);
      return;
    }
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
    setDeleteConfirm(false);
    onChunkDelete?.(chunk.id);
  }

  function handleContentBlur() {
    setEditingContent(false);
    const trimmed = draftContent.trim();
    if (trimmed && trimmed !== chunk.content) {
      applyChunkEdit({ content: trimmed });
    }
  }

  const body = editMode && editingContent ? (
    <textarea
      autoFocus
      rows={3}
      value={draftContent}
      onChange={e => setDraftContent(e.target.value)}
      onBlur={handleContentBlur}
      className="w-full resize-none rounded border border-border-focus bg-surface-elevated px-2 py-1 text-sm text-text-primary focus:outline-none"
    />
  ) : chunk.chunk_type === 'bullet' ? (
    <div
      className={cn('flex gap-2 text-sm leading-relaxed', isHidden ? 'text-text-disabled' : 'text-text-secondary')}
      onClick={editMode ? () => { setDraftContent(chunk.content); setEditingContent(true); } : undefined}
    >
      <span className="text-text-tertiary flex-shrink-0 mt-0.5">·</span>
      <span><InlineMarkdown text={chunk.content} /></span>
    </div>
  ) : (
    <p
      className={cn('text-sm leading-relaxed', isHidden ? 'text-text-disabled' : 'text-text-secondary')}
      onClick={editMode ? () => { setDraftContent(chunk.content); setEditingContent(true); } : undefined}
    >
      <InlineMarkdown text={chunk.content} />
    </p>
  );

  const sectionControl = editMode ? (
    <div className="relative mt-0.5">
      <button
        type="button"
        onClick={() => setSectionPickerOpen(v => !v)}
        title="Change group"
        className="inline-flex items-center gap-1 text-[10px] text-text-disabled hover:text-text-tertiary transition-colors"
      >
        <Unlink className="h-2.5 w-2.5" />
        {chunk.section ? `In: ${stripMarkdown(chunk.section)}` : 'Unsectioned — assign to group'}
      </button>
      {sectionPickerOpen && (
        <div
          ref={pickerRef}
          className="absolute left-0 top-full mt-1 z-20 w-52 rounded-lg border border-border-default bg-surface-overlay shadow-lg overflow-hidden"
        >
          <div className="p-2 border-b border-border-subtle">
            <input
              autoFocus
              value={newGroupDraft}
              onChange={e => setNewGroupDraft(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  const trimmed = newGroupDraft.trim();
                  if (trimmed) selectSection(trimmed);
                }
                if (e.key === 'Escape') { setSectionPickerOpen(false); setNewGroupDraft(''); }
              }}
              placeholder="New group…"
              className="w-full text-xs rounded border border-border-focus bg-surface-elevated px-2 py-1 text-text-primary placeholder:text-text-disabled focus:outline-none"
            />
          </div>
          <div className="py-1 max-h-48 overflow-y-auto">
            {availableSections.filter(s => s !== chunk.section).length === 0 && (
              <p className="px-3 py-2 text-xs text-text-disabled italic">No other groups</p>
            )}
            {availableSections.filter(s => s !== chunk.section).map(s => (
              <button
                key={s}
                type="button"
                onClick={() => selectSection(s)}
                className="w-full text-left px-3 py-1.5 text-xs text-text-secondary hover:bg-surface-sunken hover:text-text-primary transition-colors"
              >
                {stripMarkdown(s)}
              </button>
            ))}
          </div>
          {chunk.section && (
            <div className="border-t border-border-subtle py-1">
              <button
                type="button"
                onClick={() => selectSection(null)}
                className="w-full text-left px-3 py-1.5 text-xs text-text-disabled hover:bg-surface-sunken hover:text-text-tertiary transition-colors"
              >
                Remove from group
              </button>
            </div>
          )}
        </div>
      )}
      {/* Move scope prompt — anchored here so it's always near the trigger */}
      {!sectionPickerOpen && pendingMove && (
        <div className="absolute left-0 top-full mt-1 z-20 w-64 rounded-lg border border-border-default bg-surface-overlay shadow-lg p-3">
          <p className="text-xs text-text-secondary leading-snug mb-2.5">
            {pendingMove.allCount - 1 === 1 ? '1 other chunk remains' : `${pendingMove.allCount - 1} other chunks remain`}{' '}
            in this group. Also move to{' '}
            <span className="font-medium text-text-primary">{pendingMove.toSection ?? 'unsectioned'}</span>?
          </p>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={pendingMove.onMoveAll}
              className="h-6 px-2.5 rounded text-xs bg-brand-primary text-white"
            >
              Move all ({pendingMove.allCount})
            </button>
            {pendingMove.subsequentCount > 1 && pendingMove.subsequentCount < pendingMove.allCount && (
              <button
                type="button"
                onClick={pendingMove.onMoveSubsequent}
                className="h-6 px-2.5 rounded text-xs border border-border-default text-text-secondary hover:text-text-primary hover:border-border-strong transition-colors"
              >
                Subsequent ({pendingMove.subsequentCount})
              </button>
            )}
            <button
              type="button"
              onClick={pendingMove.onMoveOnly}
              className="h-6 px-2.5 rounded text-xs border border-border-default text-text-secondary hover:text-text-primary hover:border-border-strong transition-colors"
            >
              Just this one
            </button>
            <button
              type="button"
              onClick={pendingMove.onCancel}
              className="h-6 px-2 rounded text-xs text-text-disabled hover:text-text-tertiary transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  ) : null;

  const editControls = editMode ? (
    <div className="flex items-center gap-1 mt-1">
      {chunk.chunk_type !== 'header' && (
        <button
          type="button"
          title={chunk.chunk_type === 'bullet' ? 'Switch to paragraph' : 'Switch to bullet'}
          onClick={() => {
            const newType = chunk.chunk_type === 'bullet' ? 'paragraph' : 'bullet';
            applyChunkEdit({ chunk_type: newType });
          }}
          className={cn(
            'h-5 px-1.5 rounded text-[10px] inline-flex items-center gap-0.5 border transition-colors',
            chunk.chunk_type === 'bullet'
              ? 'border-border-subtle text-text-disabled hover:text-text-secondary hover:border-border-default'
              : 'border-border-subtle text-text-disabled bg-surface-sunken hover:text-text-secondary hover:border-border-default',
          )}
        >
          {chunk.chunk_type === 'bullet' ? '· Bullet' : '¶ Para'}
        </button>
      )}
      <button
        type="button"
        title={chunk.should_render === false ? 'Show in posting' : 'Hide from posting'}
        onClick={() => applyChunkEdit({ should_render: !(chunk.should_render !== false) })}
        className="h-5 px-1.5 rounded text-[10px] inline-flex items-center gap-0.5 border border-border-subtle text-text-disabled hover:text-text-secondary hover:border-border-default transition-colors"
      >
        {chunk.should_render === false ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
        {chunk.should_render === false ? 'Hidden' : 'Shown'}
      </button>
      <button
        type="button"
        title={chunk.is_requirement ? 'Mark as not a requirement' : 'Mark as requirement'}
        onClick={() => applyChunkEdit({ is_requirement: !chunk.is_requirement })}
        className={cn(
          'h-5 px-1.5 rounded text-[10px] inline-flex items-center gap-0.5 border transition-colors',
          chunk.is_requirement
            ? 'border-border-subtle text-text-disabled hover:text-text-secondary hover:border-border-default'
            : 'border-border-subtle text-text-disabled bg-surface-sunken',
        )}
      >
        {chunk.is_requirement ? 'Requirement' : 'Not a req.'}
      </button>
      <button
        type="button"
        onClick={handleDelete}
        title={deleteConfirm ? 'Click again to confirm' : 'Delete chunk'}
        className={cn(
          'h-5 px-1.5 rounded text-[10px] inline-flex items-center gap-0.5 border transition-colors ml-auto',
          deleteConfirm
            ? 'border-red-300 dark:border-red-900/60 text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/20'
            : 'border-border-subtle text-text-disabled hover:text-error hover:border-red-200 dark:hover:border-red-900/40',
        )}
      >
        <Trash2 className="h-3 w-3" />
        {deleteConfirm ? 'Confirm' : ''}
      </button>
    </div>
  ) : null;

  if (!isInteractive && !editMode) {
    return <div className={cn('mb-1.5', isHidden && 'opacity-50')}>{body}</div>;
  }

  if (onSelect) {
    const isSelected = selectedId === chunk.id;
    return (
      <div
        className={cn(
          'relative mb-1.5 rounded px-1 -mx-1 transition-colors duration-150',
          !editMode && 'cursor-pointer select-none',
          isSelected ? 'bg-surface-sunken' : (!editMode && 'hover:bg-surface-sunken/50'),
          isHidden && 'opacity-60',
        )}
        onClick={!editMode ? () => onSelect(isSelected ? null : chunk.id) : undefined}
      >
        {barColor && <div className={cn('absolute top-0 bottom-0 -left-3 w-1 rounded-sm', barColor)} />}
        {body}
        {sectionControl}
        {editControls}
      </div>
    );
  }

  const isExpanded = expandedId === chunk.id;
  return (
    <div
      className={cn(
        'relative mb-1.5 select-none group transition-transform duration-200',
        !editMode && 'cursor-pointer',
        isExpanded ? 'translate-x-0.5' : (!editMode && 'hover:translate-x-0.5'),
        isHidden && 'opacity-60',
      )}
      onClick={!editMode ? () => setExpandedId(isExpanded ? null : chunk.id) : undefined}
    >
      <div className={cn(
        'absolute top-0 bottom-0 -left-3 rounded-sm transition-all duration-200',
        barColor,
        isExpanded ? 'w-1 -translate-x-0.5' : 'w-0.5 group-hover:w-1 group-hover:-translate-x-0.5',
      )} />
      {body}
      {sectionControl}
      {editControls}
      {!editMode && (
        <div className={cn('grid transition-all duration-200', isExpanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
          <div className="overflow-hidden">
            <div className="mt-1.5 mb-0.5 px-2 py-1.5 rounded bg-surface-sunken">
              {chunk.advocacy_blurb && (
                <p className="text-xs text-text-secondary leading-relaxed">{chunk.advocacy_blurb}</p>
              )}
              {chunk.advocacy_blurb && !!(chunk.experience_sources?.length || chunk.experience_source) && chunk.match_score !== 0 && (
                <hr className="my-1.5 border-border-strong" />
              )}
              {!!(chunk.experience_sources?.length || chunk.experience_source) && chunk.match_score !== 0 && (
                <p className="text-xs text-text-tertiary">
                  Source:{' '}
                  <span className="font-medium text-text-secondary">
                    {chunk.experience_sources?.length
                      ? chunk.experience_sources.map(s => SOURCE_LABELS[s] ?? s).join(', ')
                      : (chunk.source_label ?? chunk.experience_source)}
                  </span>
                </p>
              )}
              {!publicMode && chunk.match_score === 0 && chunk.match_rationale && (
                <div className="flex items-center gap-1.5 text-text-tertiary">
                  <Info className="h-3.5 w-3.5 shrink-0" />
                  <p className="text-xs leading-relaxed italic">{chunk.match_rationale}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


/* ─── Section block ──────────────────────────────────────────────────────── */

interface PendingMassMove {
  chunk: JobChunk;
  toSection: string | null;
  /** All other chunks still in the section */
  allPeers: JobChunk[];
  /** Peers with position > chunk.position */
  subsequentPeers: JobChunk[];
}

function SectionBlock({
  section,
  chunks,
  expandedId,
  setExpandedId,
  publicMode,
  selectedId,
  onSelect,
  editMode,
  availableSections,
  onChunkUpdate,
  onChunkDelete,
  onChunkCreate,
  onSectionRename,
}: {
  section: string;
  chunks: JobChunk[];
  expandedId: string | null;
  setExpandedId: (id: string | null) => void;
  publicMode?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  editMode?: boolean;
  availableSections: string[];
  onChunkUpdate?: (chunk: JobChunk) => void;
  onChunkDelete?: (chunkId: string) => void;
  onChunkCreate?: (chunk: JobChunk) => void;
  onSectionRename?: (oldSection: string, newSection: string | null) => void;
}) {
  const sorted = [...chunks].sort((a, b) => a.position - b.position);
  const [editingSection, setEditingSection] = useState(false);
  const [sectionDraft, setSectionDraft] = useState(section);
  const [addingChunk, setAddingChunk] = useState(false);
  const [newChunkContent, setNewChunkContent] = useState('');
  const [ungroupConfirm, setUngroupConfirm] = useState(false);
  const nextTmpIdRef = useRef(0);
  const ungroupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pendingMassMove, setPendingMassMove] = useState<PendingMassMove | null>(null);

  const isUnsectioned = !section;
  const displaySection = isUnsectioned ? 'Unsectioned' : section;

  function handleSectionHeaderBlur() {
    setEditingSection(false);
    const trimmed = sectionDraft.trim();
    if (trimmed && trimmed !== section) {
      onSectionRename?.(section, trimmed);
    }
  }

  function handleUngroup() {
    if (!ungroupConfirm) {
      setUngroupConfirm(true);
      ungroupTimerRef.current = setTimeout(() => setUngroupConfirm(false), 2500);
      return;
    }
    if (ungroupTimerRef.current) clearTimeout(ungroupTimerRef.current);
    setUngroupConfirm(false);
    onSectionRename?.(section, null);
  }

  /** Called when ChunkItem wants to move to a new section — we decide what else moves. */
  function handleSectionPending(movedChunk: JobChunk, newSection: string | null) {
    const allPeers = sorted.filter(c => c.id !== movedChunk.id);
    if (allPeers.length === 0) {
      // Only chunk in section — move immediately, no prompt needed
      onChunkUpdate?.({ ...movedChunk, section: newSection });
      return;
    }
    const subsequentPeers = allPeers.filter(c => c.position > movedChunk.position);
    setPendingMassMove({ chunk: movedChunk, toSection: newSection, allPeers, subsequentPeers });
  }

  function handleMoveOnly() {
    if (!pendingMassMove) return;
    onChunkUpdate?.({ ...pendingMassMove.chunk, section: pendingMassMove.toSection });
    setPendingMassMove(null);
  }

  function handleMoveSubsequent() {
    if (!pendingMassMove) return;
    onChunkUpdate?.({ ...pendingMassMove.chunk, section: pendingMassMove.toSection });
    for (const peer of pendingMassMove.subsequentPeers) {
      onChunkUpdate?.({ ...peer, section: pendingMassMove.toSection });
    }
    setPendingMassMove(null);
  }

  function handleMoveAll() {
    if (!pendingMassMove) return;
    // onSectionRename moves all chunks in the section (including the pending chunk)
    onSectionRename?.(section, pendingMassMove.toSection);
    setPendingMassMove(null);
  }

  function handleAddChunk() {
    const trimmed = newChunkContent.trim();
    if (!trimmed) return;
    const maxPos = sorted.length > 0 ? Math.max(...sorted.map(c => c.position)) : 0;
    const tmpChunk: JobChunk = {
      id: `tmp-${nextTmpIdRef.current++}`,
      chunk_type: 'bullet',
      content: trimmed,
      position: maxPos + 1,
      section,
      match_score: null,
      match_rationale: null,
      advocacy_blurb: null,
      experience_source: null,
      experience_sources: null,
      source_label: null,
      should_render: true,
      is_requirement: true,
      display_ready: false,
      scored_content: null,
    };
    onChunkCreate?.(tmpChunk);
    setNewChunkContent('');
    setAddingChunk(false);
  }

  return (
    <div className="mb-6">
      {/* Section header */}
      <div className="flex items-center gap-2 mb-3 pb-1 border-b border-border-subtle">
        {editMode && !isUnsectioned && editingSection ? (
          <input
            autoFocus
            value={sectionDraft}
            onChange={e => setSectionDraft(e.target.value)}
            onBlur={handleSectionHeaderBlur}
            onKeyDown={e => {
              if (e.key === 'Enter') e.currentTarget.blur();
              if (e.key === 'Escape') { setEditingSection(false); setSectionDraft(section); }
            }}
            className="flex-1 rounded border border-border-focus bg-surface-elevated px-2 py-0.5 text-sm font-semibold text-text-primary focus:outline-none"
          />
        ) : (
          <h2
            className={cn(
              'flex-1 text-sm font-semibold',
              isUnsectioned ? 'text-text-disabled italic' : 'text-text-primary',
              editMode && !isUnsectioned && 'cursor-text hover:text-text-link',
            )}
            onClick={editMode && !isUnsectioned ? () => { setSectionDraft(section); setEditingSection(true); } : undefined}
          >
            {stripMarkdown(displaySection)}
          </h2>
        )}
        {editMode && !isUnsectioned && (
          <button
            type="button"
            onClick={handleUngroup}
            title={ungroupConfirm ? 'Click again — chunks become unsectioned' : 'Remove this group (chunks become unsectioned)'}
            className={cn(
              'shrink-0 inline-flex items-center gap-1 h-5 px-1.5 rounded text-[10px] border transition-colors',
              ungroupConfirm
                ? 'border-amber-300 dark:border-amber-800 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20'
                : 'border-border-subtle text-text-disabled hover:text-text-tertiary hover:border-border-default',
            )}
          >
            <FolderMinus className="h-3 w-3" />
            {ungroupConfirm ? 'Confirm ungroup' : 'Ungroup'}
          </button>
        )}
      </div>

      {sorted.map(chunk => (
        <ChunkItem
          key={chunk.id}
          chunk={chunk}
          expandedId={expandedId}
          setExpandedId={setExpandedId}
          publicMode={publicMode}
          selectedId={selectedId}
          onSelect={onSelect}
          editMode={editMode}
          isHidden={chunk.should_render === false || !chunk.display_ready}
          availableSections={availableSections}
          onChunkUpdate={onChunkUpdate}
          onChunkDelete={onChunkDelete}
          onSectionPending={editMode ? handleSectionPending : undefined}
          pendingMove={pendingMassMove?.chunk.id === chunk.id ? {
            toSection: pendingMassMove.toSection,
            allCount: pendingMassMove.allPeers.length + 1,
            subsequentCount: pendingMassMove.subsequentPeers.length + 1,
            onMoveOnly: handleMoveOnly,
            onMoveSubsequent: handleMoveSubsequent,
            onMoveAll: handleMoveAll,
            onCancel: () => setPendingMassMove(null),
          } : null}
        />
      ))}

      {/* Add chunk */}
      {editMode && !isUnsectioned && (
        <div className="mt-2">
          {addingChunk ? (
            <div className="space-y-1.5">
              <textarea
                autoFocus
                rows={2}
                placeholder="New requirement…"
                value={newChunkContent}
                onChange={e => setNewChunkContent(e.target.value)}
                className="w-full resize-none rounded border border-border-default bg-surface-elevated px-2 py-1.5 text-sm text-text-primary placeholder:text-text-disabled focus:outline-none focus:border-border-focus"
              />
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={handleAddChunk}
                  disabled={!newChunkContent.trim()}
                  className="h-6 px-2 rounded text-xs bg-brand-primary text-white disabled:opacity-40"
                >
                  Add
                </button>
                <button
                  type="button"
                  onClick={() => { setAddingChunk(false); setNewChunkContent(''); }}
                  className="h-6 px-2 rounded text-xs text-text-tertiary hover:text-text-secondary border border-border-subtle"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAddingChunk(true)}
              className="inline-flex items-center gap-1 text-[11px] text-text-disabled hover:text-text-tertiary transition-colors"
            >
              <Plus className="h-3 w-3" />
              Add requirement
            </button>
          )}
        </div>
      )}
    </div>
  );
}


/* ─── JobPosting ─────────────────────────────────────────────────────────── */

export function JobPosting({
  data, error, title, company, jobUrl, authorName, publicMode, hideHeader,
  generationReady, selectedId, onSelect,
  editMode, showHidden,
  onChunkUpdate, onChunkDelete, onChunkCreate, onSectionRename,
}: JobPostingProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pendingSections, setPendingSections] = useState<string[]>([]);
  const [addingSectionName, setAddingSectionName] = useState('');
  const [showAddSection, setShowAddSection] = useState(false);

  if (error) return <TailoringErrorState message={error} jobUrl={jobUrl} />;
  if (!data) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading…
      </div>
    );
  }

  const groups = editMode && showHidden
    ? groupChunksForAnalysis(data.chunks)
    : groupBySection(data.chunks);

  const dataSections = Array.from(
    new Set(data.chunks.map(c => c.section).filter((s): s is string => !!s))
  );
  // In draft mode, dataSections is always up to date since edits update draftChunks immediately.
  const availableSections = Array.from(new Set([...dataSections, ...pendingSections]));

  function handleAddSectionConfirm() {
    const trimmed = addingSectionName.trim();
    if (trimmed && !availableSections.includes(trimmed)) {
      setPendingSections(prev => [...prev, trimmed]);
    }
    setAddingSectionName('');
    setShowAddSection(false);
  }

  function handleChunkCreate(newChunk: JobChunk) {
    // Once a chunk is added to a pending section, the section becomes data-driven
    if (newChunk.section) {
      setPendingSections(prev => prev.filter(s => s !== newChunk.section));
    }
    onChunkCreate?.(newChunk);
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      {!hideHeader && (
        <TailoringHeader
          company={company}
          title={title}
          jobUrl={jobUrl}
          authorName={authorName}
          className="mb-8"
        />
      )}

      {groups.size === 0 && pendingSections.length === 0 ? (
        <div className="text-sm text-text-tertiary">
          {(generationReady === false) || data.enrichment_status === 'pending' || data.enrichment_status === 'processing' ? (
            <div className="flex items-start gap-2.5">
              <Loader2 className="h-4 w-4 animate-spin flex-shrink-0 mt-0.5" />
              <span>Deeper analysis is running in the background — this view will fill in automatically when complete.</span>
            </div>
          ) : (
            <p className="italic">No job posting data available.</p>
          )}
        </div>
      ) : (
        Array.from(groups.entries()).map(([section, chunks]) => (
          <SectionBlock
            key={section || '__unsectioned__'}
            section={section}
            chunks={chunks}
            expandedId={expandedId}
            setExpandedId={setExpandedId}
            publicMode={publicMode}
            selectedId={selectedId}
            onSelect={onSelect}
            editMode={editMode}
            availableSections={availableSections}
            onChunkUpdate={onChunkUpdate}
            onChunkDelete={onChunkDelete}
            onChunkCreate={handleChunkCreate}
            onSectionRename={onSectionRename}
          />
        ))
      )}

      {/* Pending (empty) sections */}
      {editMode && pendingSections.map(section => (
        <SectionBlock
          key={`pending-${section}`}
          section={section}
          chunks={[]}
          expandedId={expandedId}
          setExpandedId={setExpandedId}
          editMode={editMode}
          availableSections={availableSections}
          onChunkUpdate={onChunkUpdate}
          onChunkDelete={onChunkDelete}
          onChunkCreate={handleChunkCreate}
          onSectionRename={(old, newName) => {
            if (newName === null) {
              setPendingSections(prev => prev.filter(s => s !== old));
            } else {
              setPendingSections(prev => prev.map(s => s === old ? newName : s));
            }
          }}
        />
      ))}

      {/* Add section */}
      {editMode && (
        <div className="mt-4 pt-4 border-t border-border-subtle">
          {showAddSection ? (
            <div className="flex items-center gap-2">
              <input
                autoFocus
                value={addingSectionName}
                onChange={e => setAddingSectionName(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleAddSectionConfirm();
                  if (e.key === 'Escape') { setShowAddSection(false); setAddingSectionName(''); }
                }}
                placeholder="New section name…"
                className="flex-1 rounded border border-border-focus bg-surface-elevated px-2 py-1 text-sm text-text-primary placeholder:text-text-disabled focus:outline-none"
              />
              <button
                type="button"
                onClick={handleAddSectionConfirm}
                disabled={!addingSectionName.trim()}
                className="h-7 px-2.5 rounded text-sm bg-brand-primary text-white disabled:opacity-40"
              >
                Add
              </button>
              <button
                type="button"
                onClick={() => { setShowAddSection(false); setAddingSectionName(''); }}
                className="h-7 px-2.5 rounded text-sm border border-border-subtle text-text-tertiary hover:text-text-secondary"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowAddSection(true)}
              className="inline-flex items-center gap-1.5 text-xs text-text-disabled hover:text-text-tertiary transition-colors"
            >
              <FolderPlus className="h-3.5 w-3.5" />
              Add section
            </button>
          )}
        </div>
      )}
    </div>
  );
}
