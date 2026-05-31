'use client';

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown, Loader2, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DashedSquareIcon, GroupTypeIcon, sortGroups } from './experience-claim-utils';
import type { ExperienceGroup } from '@/types';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const MONTHS = [
  ['01', 'Jan'], ['02', 'Feb'], ['03', 'Mar'], ['04', 'Apr'],
  ['05', 'May'], ['06', 'Jun'], ['07', 'Jul'], ['08', 'Aug'],
  ['09', 'Sep'], ['10', 'Oct'], ['11', 'Nov'], ['12', 'Dec'],
] as const;

/** Parse a stored date string (YYYY or YYYY-MM or YYYY-MM-DD) into { month, year } parts. */
function parseStoredDate(d: string | null | undefined): { month: string; year: string } {
  if (!d) return { month: '', year: '' };
  const parts = d.trim().split('-');
  return { year: parts[0] ?? '', month: parts[1] ?? '' };
}

/** Build a stored date string from month + year parts. Returns null if year is empty. */
function buildStoredDate(month: string, year: string): string | null {
  const y = year.replace(/\D/g, '').slice(0, 4);
  if (!y) return null;
  return month ? `${y}-${month}` : y;
}

/* ─── MonthYearInput ─────────────────────────────────────────────────────── */

function MonthYearInput({
  value,
  onChange,
  placeholder,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  placeholder?: string;
}) {
  const parsed = parseStoredDate(value);
  const [month, setMonth] = React.useState(parsed.month);
  const [year, setYear] = React.useState(parsed.year);

  React.useEffect(() => {
    const p = parseStoredDate(value);
    setMonth(p.month);
    setYear(p.year);
  }, [value]);

  const emit = (m: string, y: string) => onChange(buildStoredDate(m, y));

  return (
    <div className="flex items-center gap-1.5 flex-1">
      <select
        value={month}
        onChange={(e) => { setMonth(e.target.value); emit(e.target.value, year); }}
        className={cn(
          'h-7 px-2 text-xs rounded-md border border-border-default bg-surface-base',
          'focus:border-border-strong outline-none transition-colors cursor-pointer',
          month ? 'text-text-secondary' : 'text-text-disabled',
        )}
      >
        <option value="">Month</option>
        {MONTHS.map(([val, label]) => (
          <option key={val} value={val}>{label}</option>
        ))}
      </select>
      <input
        type="text"
        inputMode="numeric"
        value={year}
        maxLength={4}
        placeholder={placeholder ?? 'YYYY'}
        onChange={(e) => {
          const y = e.target.value.replace(/\D/g, '').slice(0, 4);
          setYear(y);
          emit(month, y);
        }}
        className={cn(
          'w-16 h-7 px-2 text-xs rounded-md border border-border-default bg-surface-base',
          'focus:border-border-strong outline-none transition-colors',
          year ? 'text-text-secondary' : 'text-text-disabled',
        )}
      />
    </div>
  );
}

function getMeta(group: ExperienceGroup, key: string): string {
  const m = group.type_meta;
  if (!m || typeof m !== 'object') return '';
  return String((m as Record<string, unknown>)[key] ?? '');
}

/** Types that can be nested under a role. */
const NESTABLE: ExperienceGroup['group_type'][] = ['repository', 'project', 'custom'];

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

/* ─── Field input styles ─────────────────────────────────────────────────── */

const fieldInputCls =
  'flex-1 h-7 px-2.5 text-xs text-text-primary bg-surface-base rounded-md ' +
  'border border-border-default focus:border-border-strong outline-none ' +
  'transition-colors placeholder:text-text-disabled';

const fieldSelectCls =
  'flex-1 h-7 px-2 text-xs text-text-secondary bg-surface-base rounded-md ' +
  'border border-border-default focus:border-border-strong outline-none ' +
  'transition-colors cursor-pointer';

const fieldTextareaCls =
  'w-full bg-transparent resize-none outline-none text-xs text-text-primary ' +
  'leading-relaxed placeholder:text-text-disabled';

/* ─── FieldRow ───────────────────────────────────────────────────────────── */

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-4">
      <span className="text-xs text-text-disabled w-20 flex-shrink-0">{label}</span>
      {children}
    </div>
  );
}

/* ─── RoleParentPicker ───────────────────────────────────────────────────── */
/*                                                                             */
/* Portal-based picker listing only role groups. Used to set parent_group_id  */
/* on nestable group types (repository, project, custom).                     */

function RoleParentPicker({
  value,
  roleGroups,
  onChange,
}: {
  value: string;
  roleGroups: ExperienceGroup[];
  onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const triggerRef = useRef<HTMLButtonElement>(null);
  const sorted = sortGroups(roleGroups);
  const selected = sorted.find((g) => g.id === value);

  const handleOpen = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setDropdownStyle({ top: rect.bottom + 4, left: rect.left, width: rect.width });
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
          'flex items-center gap-2 w-full h-7 px-2.5 rounded-md text-xs transition-colors',
          'border border-border-default bg-surface-base hover:border-border-strong',
          open && 'border-border-strong',
          selected ? 'text-text-secondary' : 'text-text-disabled',
        )}
      >
        {selected ? (
          <>
            <GroupTypeIcon type="role" className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
            <span className="truncate">{selected.name}</span>
          </>
        ) : (
          <>
            <DashedSquareIcon className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
            <span>Standalone</span>
          </>
        )}
        <ChevronDown className="h-3 w-3 text-text-disabled ml-auto flex-shrink-0" />
      </button>

      {open && createPortal(
        <>
          <div className="fixed inset-0 z-[59]" onClick={() => setOpen(false)} aria-hidden="true" />
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
              Standalone
            </button>
            {sorted.map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => { onChange(g.id); setOpen(false); }}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors hover:bg-surface-sunken',
                  value === g.id ? 'text-text-primary font-medium' : 'text-text-secondary',
                )}
              >
                <GroupTypeIcon type="role" className="h-3.5 w-3.5 text-text-disabled flex-shrink-0" />
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

/* ─── Props & patch type ─────────────────────────────────────────────────── */

export interface GroupPatch {
  name?: string;
  start_date?: string | null;
  end_date?: string | null;
  location?: string | null;
  description?: string | null;
  type_meta?: Record<string, unknown>;
  parent_group_id?: string | null;
}

export interface ExperienceGroupModalProps {
  group: ExperienceGroup | null;
  groups: ExperienceGroup[];
  /** Number of claims directly assigned to this group (not counting child groups' claims). */
  directClaimsCount: number;
  onClose: () => void;
  onSave: (id: string, updates: GroupPatch) => Promise<void>;
  onDelete?: (id: string, cascade: boolean) => Promise<void>;
}

/* ─── ExperienceGroupModal ───────────────────────────────────────────────── */

export function ExperienceGroupModal({
  group,
  groups,
  directClaimsCount,
  onClose,
  onSave,
  onDelete,
}: ExperienceGroupModalProps) {
  /* ── Per-type form state ── */
  // Role
  const [company, setCompany] = useState('');
  const [title, setTitle] = useState('');
  const [employmentType, setEmploymentType] = useState('');
  // Education
  const [institution, setInstitution] = useState('');
  const [program, setProgram] = useState('');
  const [fieldOfStudy, setFieldOfStudy] = useState('');
  const [edStatus, setEdStatus] = useState('');
  // Common name (repo / project / custom)
  const [name, setName] = useState('');
  // Shared
  const [startDate, setStartDate] = useState<string | null>(null);
  const [endDate, setEndDate] = useState<string | null>(null);
  const [isCurrent, setIsCurrent] = useState(false);
  const [location, setLocation] = useState('');
  const [description, setDescription] = useState('');
  const [parentGroupId, setParentGroupId] = useState('');
  // Async
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const descRef = useRef<HTMLTextAreaElement>(null);

  // Reset all fields when group changes
  useEffect(() => {
    if (!group) return;
    const parts = group.name.split('|').map((s) => s.trim());

    if (group.group_type === 'role') {
      setCompany(getMeta(group, 'company') || parts[0] || '');
      setTitle(getMeta(group, 'title') || parts[1] || '');
      setEmploymentType(getMeta(group, 'employment_type') || '');
    } else if (group.group_type === 'education') {
      // Education name format: "Program | Institution"
      setProgram(getMeta(group, 'degree') || parts[0] || '');
      setInstitution(getMeta(group, 'institution') || parts[1] || '');
      setFieldOfStudy(getMeta(group, 'field_of_study') || '');
      setEdStatus(getMeta(group, 'status') || '');
    } else {
      setName(group.name);
    }

    setStartDate(group.start_date ?? null);
    setEndDate(group.end_date ?? null);
    setIsCurrent(group.end_date === null && !!group.start_date);
    setLocation(group.location || '');
    setDescription(group.description || '');
    setParentGroupId(group.parent_group_id || '');
    setConfirmingDelete(false);

    // Auto-size description
    requestAnimationFrame(() => {
      const el = descRef.current;
      if (!el) return;
      el.style.height = '0px';
      el.style.height = `${el.scrollHeight}px`;
    });
  }, [group?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Esc to close
  useEffect(() => {
    if (!group) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [group, onClose]);

  if (!group) return null;

  const canHaveParent = NESTABLE.includes(group.group_type);
  const roleGroups = sortGroups(groups.filter((g) => g.group_type === 'role' && g.id !== group.id));
  const childGroupCount = groups.filter((g) => g.parent_group_id === group.id).length;
  const hasContents = directClaimsCount > 0 || childGroupCount > 0;

  /* ── Save ── */
  const handleSave = async () => {
    setSaving(true);
    try {
      // Compute name from structured fields
      let computedName: string;
      const metaUpdates: Record<string, unknown> = { ...(group.type_meta ?? {}) };

      if (group.group_type === 'role') {
        metaUpdates.company = company;
        metaUpdates.title = title;
        metaUpdates.employment_type = employmentType;
        computedName = company && title ? `${company} | ${title}` : company || title || group.name;
      } else if (group.group_type === 'education') {
        metaUpdates.degree = program;
        metaUpdates.institution = institution;
        metaUpdates.field_of_study = fieldOfStudy;
        metaUpdates.status = edStatus;
        computedName = program && institution ? `${program} | ${institution}` : program || institution || group.name;
      } else {
        computedName = name.trim() || group.name;
      }

      const patch: GroupPatch = {
        name: computedName,
        start_date: startDate,
        end_date: isCurrent ? null : endDate,
        location: location || null,
        description: description || null,
        type_meta: metaUpdates,
        ...(canHaveParent ? { parent_group_id: parentGroupId || null } : {}),
      };

      await onSave(group.id, patch);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  /* ── Delete ── */
  const handleDelete = async (cascade: boolean) => {
    if (!onDelete) return;
    setDeleting(true);
    try {
      await onDelete(group.id, cascade);
      onClose();
    } finally {
      setDeleting(false);
    }
  };

  /* ── Type-specific primary fields ── */
  const renderPrimaryFields = () => {
    if (group.group_type === 'role') {
      return (
        <>
          <FieldRow label="Company">
            <input
              type="text"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="Company name"
              className={fieldInputCls}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
            />
          </FieldRow>
          <FieldRow label="Title">
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Job title"
              className={fieldInputCls}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
            />
          </FieldRow>
        </>
      );
    }

    if (group.group_type === 'education') {
      return (
        <>
          <FieldRow label="Degree">
            <input
              type="text"
              value={program}
              onChange={(e) => setProgram(e.target.value)}
              placeholder="Credential received (optional)"
              className={fieldInputCls}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
            />
          </FieldRow>
          <FieldRow label="Institution">
            <input
              type="text"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              placeholder="School or university"
              className={fieldInputCls}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
            />
          </FieldRow>
        </>
      );
    }

    // Repository, Project, Custom
    return (
      <FieldRow label="Name">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Group name"
          className={fieldInputCls}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
        />
      </FieldRow>
    );
  };

  /* ── Type-specific secondary fields ── */
  const renderSecondaryFields = () => {
    if (group.group_type === 'role') {
      return (
        <FieldRow label="Type">
          <select
            value={employmentType}
            onChange={(e) => setEmploymentType(e.target.value)}
            className={fieldSelectCls}
          >
            <option value="">—</option>
            <option value="full_time">Full-time</option>
            <option value="part_time">Part-time</option>
            <option value="contract">Contract</option>
            <option value="freelance">Freelance</option>
            <option value="internship">Internship</option>
          </select>
        </FieldRow>
      );
    }

    if (group.group_type === 'education') {
      return (
        <>
          <FieldRow label="Field">
            <input
              type="text"
              value={fieldOfStudy}
              onChange={(e) => setFieldOfStudy(e.target.value)}
              placeholder="e.g. Computer Science"
              className={fieldInputCls}
            />
          </FieldRow>
          <FieldRow label="Status">
            <select
              value={edStatus}
              onChange={(e) => setEdStatus(e.target.value)}
              className={fieldSelectCls}
            >
              <option value="">—</option>
              <option value="graduated">Graduated</option>
              <option value="pursuing">Pursuing</option>
              <option value="transferred">Transferred</option>
              <option value="attended">Attended</option>
            </select>
          </FieldRow>
        </>
      );
    }

    return null;
  };

  const groupTypeLabel = group.group_type.replace('_', ' ');

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/25"
        style={{ left: 'var(--sidebar-w, 0px)' }}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none px-8"
        style={{ left: 'var(--sidebar-w, 0px)' }}
      >
        <div
          className={cn(
            'pointer-events-auto w-full max-w-[560px] max-h-[85vh]',
            'bg-surface-elevated rounded-xl border border-border-subtle shadow-2xl',
            'flex flex-col overflow-hidden',
          )}
          role="dialog"
          aria-modal="true"
          aria-label="Experience group"
        >

          {/* ── Header ── */}
          <div className="flex items-center justify-between px-5 py-3.5 bg-surface-sunken border-b border-border-subtle flex-shrink-0">
            <div className="flex items-center gap-2">
              <GroupTypeIcon type={group.group_type} className="h-4 w-4 text-text-tertiary" />
              <span className="text-xs font-medium text-text-tertiary tracking-wide capitalize">
                {groupTypeLabel}
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

          {/* ── Body ── */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 min-h-0">

            {/* Primary fields (company+title / institution+program / name) */}
            {renderPrimaryFields()}

            <div className="h-px bg-border-subtle" />

            {/* Type-specific secondary fields */}
            {renderSecondaryFields()}

            {/* Dates — hidden for repository (auto-populated from GitHub commit history) */}
            {group.group_type !== 'repository' && (
              <>
                <FieldRow label="Start">
                  <MonthYearInput value={startDate} onChange={setStartDate} />
                </FieldRow>

                <FieldRow label="End">
                  <div className="flex items-center gap-3 flex-1">
                    {!isCurrent && (
                      <MonthYearInput value={endDate} onChange={setEndDate} />
                    )}
                    <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer flex-shrink-0 select-none">
                      <input
                        type="checkbox"
                        checked={isCurrent}
                        onChange={(e) => {
                          setIsCurrent(e.target.checked);
                          if (e.target.checked) setEndDate(null);
                        }}
                        className="accent-brand-primary"
                      />
                      Current
                    </label>
                  </div>
                </FieldRow>
              </>
            )}

            {/* Location (roles; optional for others) */}
            {(group.group_type === 'role' || group.group_type === 'custom') && (
              <FieldRow label="Location">
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="City, remote, etc."
                  className={fieldInputCls}
                />
              </FieldRow>
            )}

            {/* Parent group (nestable types only) */}
            {canHaveParent && (
              <FieldRow label="Parent">
                {roleGroups.length > 0 ? (
                  <RoleParentPicker
                    value={parentGroupId}
                    roleGroups={roleGroups}
                    onChange={setParentGroupId}
                  />
                ) : (
                  <span className="text-xs text-text-disabled italic">No roles available</span>
                )}
              </FieldRow>
            )}

            {/* Description */}
            <div className="h-px bg-border-subtle" />

            <FieldRow label="Notes">
              <textarea
                ref={descRef}
                value={description}
                rows={2}
                onChange={(e) => {
                  setDescription(e.target.value);
                  e.target.style.height = '0px';
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSave(); }}
                placeholder="Additional context…"
                className={cn(fieldTextareaCls, 'mt-0.5')}
              />
            </FieldRow>

          </div>

          {/* ── Footer ── */}
          <div className="px-5 py-3 bg-surface-sunken border-t border-border-subtle flex-shrink-0">
            {confirmingDelete ? (
              /* Delete confirmation panel */
              <div className="space-y-2.5">
                <p className="text-xs text-text-secondary leading-relaxed">
                  {hasContents ? (
                    <>
                      This group has{' '}
                      {directClaimsCount > 0 && (
                        <span className="font-medium text-text-primary">
                          {directClaimsCount} claim{directClaimsCount !== 1 ? 's' : ''}
                        </span>
                      )}
                      {directClaimsCount > 0 && childGroupCount > 0 && ' and '}
                      {childGroupCount > 0 && (
                        <span className="font-medium text-text-primary">
                          {childGroupCount} nested group{childGroupCount !== 1 ? 's' : ''}
                        </span>
                      )}
                      . What should happen to them?
                    </>
                  ) : (
                    'Delete this group? This cannot be undone.'
                  )}
                </p>
                <div className="flex items-center gap-2 justify-end">
                  <button
                    type="button"
                    onClick={() => setConfirmingDelete(false)}
                    className={cancelBtnCls}
                  >
                    Cancel
                  </button>
                  {hasContents && (
                    <button
                      type="button"
                      onClick={() => handleDelete(false)}
                      disabled={deleting}
                      className={cancelBtnCls}
                    >
                      {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                      Ungroup contents
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => handleDelete(hasContents ? true : false)}
                    disabled={deleting}
                    className={
                      'inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-xs font-medium ' +
                      'bg-red-600 hover:bg-red-700 text-white disabled:opacity-40 transition-colors'
                    }
                  >
                    {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    {hasContents ? 'Delete everything' : 'Delete'}
                  </button>
                </div>
              </div>
            ) : (
              /* Normal footer */
              <div className="flex items-center justify-between">
                {onDelete ? (
                  <button
                    type="button"
                    onClick={() => setConfirmingDelete(true)}
                    className={deleteBtnCls}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete group
                  </button>
                ) : (
                  <div />
                )}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-disabled select-none">⌘↵</span>
                  <button type="button" onClick={onClose} className={cancelBtnCls}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving}
                    className={saveBtnCls}
                  >
                    {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                    Save
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}
