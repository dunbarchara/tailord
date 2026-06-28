'use client';

import { useState, useEffect, useRef } from 'react';
import { Trash2, Loader2, Layers } from 'lucide-react';
import { cn, toastError } from '@/lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { SOURCE_LABELS, SOURCE_DOT_CLS } from './experience-claim-utils';
import type { ExperienceClaim } from '@/types';

/* ─── Helpers ─────────────────────────────────────────────────────────────── */

function formatAdded(updatedAt: string | null | undefined): string | null {
  if (!updatedAt) return null;
  const d = new Date(updatedAt);
  if (isNaN(d.getTime())) return null;
  return 'Added ' + d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/* ─── SkillsModal ─────────────────────────────────────────────────────────── */

interface SkillsModalProps {
  claims: ExperienceClaim[] | null; // null = closed
  onClose: () => void;
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

export function SkillsModal({ claims, onClose, onSave, onDelete }: SkillsModalProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  // Reset selection when modal opens
  const prevOpenRef = useRef(false);
  useEffect(() => {
    const nowOpen = claims !== null;
    if (nowOpen && !prevOpenRef.current) {
      setSelected(new Set());
      setEditingId(null);
    }
    prevOpenRef.current = nowOpen;
  }, [claims]);

  const list = claims ?? [];
  const allSelected = list.length > 0 && list.every((c) => selected.has(c.id));

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(list.map((c) => c.id)));
  }

  function toggleOne(id: string) {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) { n.delete(id); } else { n.add(id); }
      return n;
    });
  }

  function startEdit(claim: ExperienceClaim) {
    setEditingId(claim.id);
    setEditValue(claim.content);
  }

  async function commitEdit(id: string) {
    const trimmed = editValue.trim();
    const original = list.find((c) => c.id === id)?.content;
    if (!trimmed || trimmed === original) { setEditingId(null); return; }
    setSavingId(id);
    try { await onSave(id, trimmed); }
    catch (err) { toastError(err instanceof Error ? err.message : 'Failed to save'); }
    finally { setSavingId(null); setEditingId(null); }
  }

  async function deleteSingle(id: string) {
    setDeletingIds((prev) => new Set([...prev, id]));
    try {
      await onDelete(id);
      setSelected((prev) => { const n = new Set(prev); n.delete(id); return n; });
    } finally {
      setDeletingIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
    }
  }

  async function bulkDelete() {
    const ids = Array.from(selected).filter((id) => list.some((c) => c.id === id));
    if (ids.length === 0) return;
    setDeletingIds(new Set(ids));
    try {
      await Promise.all(ids.map((id) => onDelete(id)));
      setSelected(new Set());
    } catch { toastError('Some skills could not be deleted'); }
    finally { setDeletingIds(new Set()); }
  }

  const anyDeleting = deletingIds.size > 0;
  // Only count IDs that are still in the list (handles external deletions)
  const selectedCount = [...selected].filter((id) => list.some((c) => c.id === id)).length;

  return (
    <Dialog open={claims !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="max-w-md bg-surface-elevated border-border-subtle rounded-2xl p-0 flex flex-col overflow-hidden"
        style={{ maxHeight: '70vh' }}
      >
        {/* Header */}
        <DialogHeader className="flex-shrink-0 px-4 py-3 border-b border-border-subtle">
          <div className="flex items-center gap-2.5">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="h-3.5 w-3.5 accent-brand-primary cursor-pointer flex-shrink-0"
              aria-label="Select all skills"
            />
            <DialogTitle className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <Layers className="h-4 w-4 text-text-disabled" />
              Skills
              <span className="text-text-disabled font-normal tabular-nums">{list.length}</span>
            </DialogTitle>
            {selectedCount > 0 && (
              <button
                type="button"
                onClick={bulkDelete}
                disabled={anyDeleting}
                className="ml-auto inline-flex items-center gap-1.5 h-6 px-2.5 rounded-[6px] text-xs font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-40 transition-colors flex-shrink-0"
              >
                {anyDeleting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                Delete {selectedCount}
              </button>
            )}
          </div>
        </DialogHeader>

        {/* Scrollable list */}
        <div className="overflow-y-auto flex-1 py-1">
          {list.length === 0 ? (
            <p className="px-5 py-8 text-sm text-text-tertiary text-center">No skills</p>
          ) : (
            list.map((claim) => {
              const isSelected = selected.has(claim.id);
              const isEditing = editingId === claim.id;
              const isDeleting = deletingIds.has(claim.id);
              const isSaving = savingId === claim.id;
              const formattedDate = formatAdded(claim.updated_at);
              const sourceLabel = SOURCE_LABELS[claim.source_type];
              const dotCls = SOURCE_DOT_CLS[claim.source_type] ?? 'bg-zinc-400';

              return (
                <div
                  key={claim.id}
                  className={cn(
                    'group/skill-row flex items-center gap-2 px-4 py-2 min-h-[40px] transition-colors',
                    isSelected ? 'bg-surface-base' : 'hover:bg-surface-base',
                    isDeleting && 'opacity-40 pointer-events-none',
                  )}
                >
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleOne(claim.id)}
                    className={cn(
                      'h-3.5 w-3.5 accent-brand-primary cursor-pointer flex-shrink-0 transition-opacity',
                      isSelected ? 'opacity-100' : 'opacity-0 group-hover/skill-row:opacity-100',
                    )}
                  />

                  {/* Skill text */}
                  {isEditing ? (
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={() => commitEdit(claim.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') { e.preventDefault(); commitEdit(claim.id); }
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      // eslint-disable-next-line jsx-a11y/no-autofocus
                      autoFocus
                      className="flex-1 min-w-0 text-sm text-text-primary bg-transparent border-b border-border-focus outline-none py-0.5"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => !isDeleting && !isSaving && startEdit(claim)}
                      className="flex-1 min-w-0 text-sm text-text-secondary truncate cursor-text select-none text-left bg-transparent border-0 p-0"
                    >
                      {claim.content}
                      {isSaving && <Loader2 className="inline h-3 w-3 ml-1 animate-spin text-text-disabled" />}
                    </button>
                  )}

                  {/* Source badge */}
                  {sourceLabel && (
                    <span className="inline-flex items-center gap-1 h-5 px-1.5 rounded-[4px] text-xs bg-surface-sunken text-text-secondary flex-shrink-0">
                      <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', dotCls)} />
                      {sourceLabel}
                    </span>
                  )}

                  {/* Date */}
                  {formattedDate && (
                    <span className="text-xs text-text-disabled tabular-nums flex-shrink-0 min-w-[52px] text-right">
                      {formattedDate}
                    </span>
                  )}

                  {/* Delete */}
                  {!isEditing && (
                    <button
                      type="button"
                      onClick={() => deleteSingle(claim.id)}
                      disabled={isDeleting}
                      aria-label="Delete skill"
                      className={cn(
                        'w-6 h-6 flex items-center justify-center rounded flex-shrink-0',
                        'text-text-disabled hover:text-error transition-colors',
                        'opacity-0 group-hover/skill-row:opacity-100',
                      )}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
