'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Loader2, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DashedSquareIcon,
  GroupTypeIcon,
  SOURCE_DOT_CLS,
  SOURCE_LABELS,
  ThreeDashIcon,
  normalizeContent,
  sortGroups,
} from './experience-claim-utils';
import type { ExperienceClaim, ExperienceGroup } from '@/types';

/* ─── Button styles ──────────────────────────────────────────────────────── */

const saveBtnCls =
  'inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-xs font-medium ' +
  'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 ' +
  'hover:opacity-90 disabled:opacity-40 transition-opacity';

const cancelBtnCls =
  'inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-xs font-medium ' +
  'text-text-tertiary hover:text-text-secondary border border-border-default ' +
  'hover:border-border-strong transition-colors';

const deleteBtnCls =
  'inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-xs font-medium ' +
  'text-text-tertiary hover:text-error hover:bg-red-50 dark:hover:bg-red-950/20 ' +
  'transition-colors disabled:opacity-40';

/* ─── GroupPicker ────────────────────────────────────────────────────────── */
/*                                                                             */
/* Renders the current group with its icon. Clicking opens a custom list      */
/* of all groups with their icons — reinforcing the visual language used      */
/* throughout the claims table.                                               */

function GroupPicker({
  value,
  groups,
  onChange,
}: {
  value: string;
  groups: ExperienceGroup[];
  onChange: (groupId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const triggerRef = useRef<HTMLButtonElement>(null);
  const sortedGroups = sortGroups(groups);
  const selectedGroup = sortedGroups.find((g) => g.id === value);

  const handleOpen = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setDropdownStyle({
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
      });
    }
    setOpen(true);
  };

  return (
    <div className="flex-1 min-w-0">
      <button
        ref={triggerRef}
        type="button"
        onClick={open ? () => setOpen(false) : handleOpen}
        className={cn(
          'flex items-center gap-2 w-full px-2.5 py-1.5 rounded-md text-xs transition-colors',
          'border border-border-default bg-surface-base',
          'hover:border-border-strong text-text-secondary',
          open && 'border-border-strong',
        )}
      >
        {selectedGroup ? (
          <>
            <GroupTypeIcon type={selectedGroup.group_type} className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
            <span className="truncate">{selectedGroup.name}</span>
          </>
        ) : (
          <>
            <DashedSquareIcon className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
            <span className="text-text-disabled">Ungrouped</span>
          </>
        )}
        <ChevronDown className="h-3 w-3 text-text-disabled ml-auto flex-shrink-0" />
      </button>

      {open && createPortal(
        <>
          {/* Backdrop to capture outside clicks */}
          <div
            className="fixed inset-0 z-[59]"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          {/* Dropdown — rendered outside all overflow constraints */}
          <div
            className="fixed z-[60] bg-surface-elevated border border-border-subtle rounded-lg shadow-xl py-1 max-h-56 overflow-y-auto"
            style={dropdownStyle}
          >
            <button
              type="button"
              onClick={() => { onChange(''); setOpen(false); }}
              className={cn(
                'w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors hover:bg-surface-sunken',
                !value ? 'text-text-primary font-medium' : 'text-text-secondary',
              )}
            >
              <DashedSquareIcon className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
              Ungrouped
            </button>
            {sortedGroups.map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => { onChange(g.id); setOpen(false); }}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors hover:bg-surface-sunken',
                  value === g.id ? 'text-text-primary font-medium' : 'text-text-secondary',
                )}
              >
                <GroupTypeIcon type={g.group_type} className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
                {g.name}
              </button>
            ))}
          </div>
        </>,
        document.body,
      )}
    </div>
  );
}

/* ─── Props ──────────────────────────────────────────────────────────────── */

export interface ExperienceClaimModalProps {
  claim: ExperienceClaim | null;
  groups: ExperienceGroup[];
  onClose: () => void;
  onSave: (id: string, content: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onMoveToGroup: (id: string, groupId: string | null) => Promise<void>;
}

/* ─── ExperienceClaimModal ───────────────────────────────────────────────── */
/*                                                                             */
/* Content-panel-scoped modal for viewing and editing a single claim.         */
/* The backdrop offsets by --sidebar-w (set by Sidebar.tsx) so the sidebar    */
/* remains interactive. Reusable: accepts claim + callbacks, open when        */
/* claim != null.                                                              */

export function ExperienceClaimModal({
  claim,
  groups,
  onClose,
  onSave,
  onDelete,
  onMoveToGroup,
}: ExperienceClaimModalProps) {
  const [value, setValue] = useState('');
  const [groupValue, setGroupValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Reset + focus when claim changes
  useEffect(() => {
    if (!claim) return;
    setValue(normalizeContent(claim.content));
    setGroupValue(claim.group_id ?? '');
    // Double-RAF: first RAF runs before paint (DOM updated, styles unresolved);
    // second RAF runs after the browser has committed the layout, so scrollHeight
    // is accurate for a freshly-mounted textarea.
    let raf2: number;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = '0px';
        el.style.height = `${el.scrollHeight}px`;
        el.focus();
      });
    });
    return () => { cancelAnimationFrame(raf1); cancelAnimationFrame(raf2); };
  }, [claim?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Esc to close
  useEffect(() => {
    if (!claim) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [claim, onClose]);

  if (!claim) return null;

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      const contentChanged = trimmed !== normalizeContent(claim.content);
      const newGroupId = groupValue || null;
      const groupChanged = newGroupId !== (claim.group_id ?? null);
      if (contentChanged) await onSave(claim.id, trimmed);
      if (groupChanged) await onMoveToGroup(claim.id, newGroupId);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(claim.id);
      onClose();
    } finally {
      setDeleting(false);
    }
  };

  const sourceLabel = SOURCE_LABELS[claim.source_type];
  const dotCls = SOURCE_DOT_CLS[claim.source_type] ?? 'bg-zinc-400';

  const addedLabel = claim.updated_at
    ? new Date(claim.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null;

  return (
    <>
      {/* Backdrop — offset by sidebar width so sidebar stays interactive */}
      <div
        className="fixed inset-0 z-40 bg-black/25"
        style={{ left: 'var(--sidebar-w, 0px)' }}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog — centered in the content panel */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none px-8"
        style={{ left: 'var(--sidebar-w, 0px)' }}
      >
        <div
          className={cn(
            'pointer-events-auto w-full max-w-[580px] max-h-[80vh]',
            'bg-surface-elevated rounded-xl border border-border-subtle shadow-2xl',
            'flex flex-col overflow-hidden',
          )}
          role="dialog"
          aria-modal="true"
          aria-label="Experience claim"
        >

          {/* ── Header ── */}
          <div className="flex items-center justify-between px-5 py-3.5 bg-surface-sunken border-b border-border-subtle flex-shrink-0">
            <div className="flex items-center gap-2">
              <ThreeDashIcon className="text-text-tertiary" />
              <span className="text-xs font-medium text-text-tertiary tracking-wide">
                Experience Claim
              </span>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="w-7 h-7 flex items-center justify-center rounded-md text-text-disabled hover:text-text-secondary hover:bg-surface-base transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* ── Body (scrollable) ── */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">

            {/* Content textarea */}
            <textarea
              ref={textareaRef}
              value={value}
              rows={4}
              onChange={(e) => {
                setValue(e.target.value);
                e.target.style.height = '0px';
                e.target.style.height = `${e.target.scrollHeight}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave();
              }}
              className="w-full bg-transparent resize-none outline-none text-sm text-text-primary leading-relaxed"
              placeholder="Claim content…"
            />

            <div className="h-px bg-border-subtle" />

            {/* Property rows */}
            <div className="space-y-2.5">

              {/* Group */}
              <div className="flex items-center gap-4">
                <span className="text-xs text-text-disabled w-12 flex-shrink-0">Group</span>
                <GroupPicker value={groupValue} groups={groups} onChange={setGroupValue} />
              </div>

              {/* Source */}
              {sourceLabel && (
                <div className="flex items-center gap-4">
                  <span className="text-xs text-text-disabled w-12 flex-shrink-0">Source</span>
                  <span className="inline-flex items-center gap-1.5 h-6 px-2.5 rounded-[5px] text-xs bg-surface-sunken text-text-secondary">
                    <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', dotCls)} />
                    {sourceLabel}
                  </span>
                </div>
              )}

              {/* Added */}
              {addedLabel && (
                <div className="flex items-center gap-4">
                  <span className="text-xs text-text-disabled w-12 flex-shrink-0">Added</span>
                  <span className="text-xs text-text-disabled">{addedLabel}</span>
                </div>
              )}

            </div>

            {/* Provenance placeholder — future: source signals list */}

          </div>

          {/* ── Footer ── */}
          <div className="flex items-center justify-between px-5 py-3 bg-surface-sunken border-t border-border-subtle flex-shrink-0">
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className={deleteBtnCls}
            >
              {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              Delete
            </button>
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-disabled select-none">⌘↵</span>
              <button type="button" onClick={onClose} className={cancelBtnCls}>
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving || !value.trim()}
                className={saveBtnCls}
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                Save
              </button>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
