'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  ChevronRight, Trash2, Loader2, Plus, X,
  MoreHorizontal, Link, Link2Off, Layers, Command,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { ExperienceClaimModal } from './ExperienceClaimModal';
import { ExperienceGroupModal, type GroupPatch } from './ExperienceGroupModal';
import { SkillsModal } from './SkillsModal';
import {
  DashedSquareIcon,
  GroupTypeIcon,
  SOURCE_DOT_CLS,
  SOURCE_LABELS,
  ThreeDashIcon as ThreeDashIconShared,
  normalizeContent,
  parseDateMs,
  sortClaims,
  sortGroups,
} from './experience-claim-utils';
import type { ExperienceClaim, ExperienceClaimsResponse, ExperienceGroup } from '@/types';

/* ─── Icons ──────────────────────────────────────────────────────────────── */

const ThreeDashIcon = ThreeDashIconShared;

/* ─── Data types & helpers ──────────────────────────────────────────────── */

interface GroupNode {
  group: ExperienceGroup;
  claims: ExperienceClaim[];
  children: GroupNode[];
}

function flattenClaims(data: ExperienceClaimsResponse): ExperienceClaim[] {
  const all: ExperienceClaim[] = [];
  if (data.resume) {
    data.resume.work_experience.forEach((g) => all.push(...g.chunks));
    all.push(...data.resume.skills);
    data.resume.projects.forEach((g) => all.push(...g.chunks));
    all.push(...data.resume.education, ...data.resume.other);
  }
  if (data.github) data.github.repos.forEach((r) => all.push(...r.chunks));
  all.push(
    ...(data.user_input ?? []),
    ...(data.gap_response ?? []),
    ...(data.partial_response ?? []),
  );
  return all;
}

function buildGroupTree(groups: ExperienceGroup[], claims: ExperienceClaim[]) {
  const claimsByGroup = new Map<string, ExperienceClaim[]>();
  const ungrouped: ExperienceClaim[] = [];

  for (const claim of claims) {
    if (claim.group_id) {
      const arr = claimsByGroup.get(claim.group_id) ?? [];
      arr.push(claim);
      claimsByGroup.set(claim.group_id, arr);
    } else {
      ungrouped.push(claim);
    }
  }

  const childGroupsByParent = new Map<string, ExperienceGroup[]>();
  for (const g of groups) {
    if (g.parent_group_id) {
      const arr = childGroupsByParent.get(g.parent_group_id) ?? [];
      arr.push(g);
      childGroupsByParent.set(g.parent_group_id, arr);
    }
  }

  const buildNode = (g: ExperienceGroup): GroupNode => ({
    group: g,
    claims: sortClaims(claimsByGroup.get(g.id) ?? []),
    // Nested groups sorted by date before direct claims render
    children: sortGroups(childGroupsByParent.get(g.id) ?? []).map(buildNode),
  });

  const topLevel = sortGroups(groups.filter((g) => !g.parent_group_id));

  return { nodes: topLevel.map(buildNode), ungrouped: sortClaims(ungrouped) };
}

/* ─── SkillsInlineRow ────────────────────────────────────────────────────── */

function SkillsInlineRow({
  claims,
  nested = false,
  onOpenSkills,
}: {
  claims: ExperienceClaim[];
  nested?: boolean;
  onOpenSkills?: () => void;
}) {
  if (claims.length === 0) return null;

  const text = claims.map((c) => normalizeContent(c.content)).join(' | ');

  // Source summary: single label or 'Multi'
  const sources = new Set(claims.map((c) => c.source_type));
  const sourceLabel = sources.size > 1 ? 'Multi' : SOURCE_LABELS[claims[0]?.source_type];
  const dotCls = sources.size > 1 ? 'bg-zinc-400' : (SOURCE_DOT_CLS[claims[0]?.source_type] ?? 'bg-zinc-400');

  // Oldest date — prefer date_range (skill acquisition context), fall back to updated_at
  // Format matches ClaimRow: "May 30"
  const drDates = claims.map((c) => parseDateMs(c.date_range)).filter((d): d is number => d !== null);
  const addedDates = claims.map((c) => c.updated_at ? new Date(c.updated_at).getTime() : null).filter((d): d is number => d !== null);
  const oldestMs = drDates.length > 0 ? Math.min(...drDates) : addedDates.length > 0 ? Math.min(...addedDates) : null;
  const rowDate = oldestMs !== null
    ? new Date(oldestMs).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null;

  const inner = (
    <>
      <div className="w-[22px] h-[22px] flex-shrink-0" />
      {nested && <div className="w-[22px] h-[22px] flex-shrink-0" />}
      <div className="w-[22px] h-[22px] flex items-center justify-center flex-shrink-0">
        <Layers className="h-4 w-4 text-text-disabled" aria-hidden="true" />
      </div>
      <span className="flex-1 text-sm text-text-tertiary leading-relaxed truncate">
        <span className="text-text-disabled mr-1.5">{claims.length} Skills –</span>
        {text}
      </span>
      <Meta sourceLabel={sourceLabel} dotCls={dotCls} rowDate={rowDate} />
    </>
  );

  if (onOpenSkills) {
    return (
      <button
        type="button"
        onClick={onOpenSkills}
        className="group/row w-full flex items-center gap-2 px-2 min-h-[46px] hover:bg-surface-base transition-colors text-left"
      >
        {inner}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2 px-2 min-h-[46px]">
      {inner}
    </div>
  );
}

/* ─── Meta ───────────────────────────────────────────────────────────────── */

function Meta({ sourceLabel, dotCls, rowDate }: { sourceLabel?: string; dotCls: string; rowDate: string | null }) {
  if (!sourceLabel && !rowDate) return null;
  return (
    <div className="flex items-center gap-3 flex-shrink-0 ml-2">
      {sourceLabel && (
        <span className="inline-flex items-center gap-1.5 h-6 px-2.5 rounded-[5px] text-xs bg-surface-sunken text-text-secondary">
          <span className={cn('w-2 h-2 rounded-full flex-shrink-0', dotCls)} />
          {sourceLabel}
        </span>
      )}
      {rowDate && (
        <span className="text-xs text-text-disabled min-w-[44px] text-right tabular-nums">
          {rowDate}
        </span>
      )}
    </div>
  );
}

/* ─── ClaimRow ───────────────────────────────────────────────────────────── */
/*                                                                             */
/* Clicking the content area calls onOpenClaim — the modal is managed by     */
/* the top-level ProfileChunkEditor component (not per-row).                  */

function ClaimRow({
  claim,
  readOnly = false,
  nested = false,
  isSelected = false,
  onToggleSelect,
  onOpenClaim,
}: {
  claim: ExperienceClaim;
  readOnly?: boolean;
  nested?: boolean;
  isSelected?: boolean;
  onToggleSelect?: (id: string) => void;
  onOpenClaim?: (claim: ExperienceClaim) => void;
}) {
  const sourceLabel = SOURCE_LABELS[claim.source_type];
  const dotCls = SOURCE_DOT_CLS[claim.source_type] ?? 'bg-zinc-400';
  const rowDate = claim.updated_at
    ? new Date(claim.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null;

  const baseRowCls = 'group/row flex items-center gap-2 px-2 min-h-[46px] transition-colors';

  if (readOnly) {
    return (
      <div className={cn(baseRowCls)}>
        <div className="w-[22px] h-[22px] flex-shrink-0" />
        {nested && <div className="w-[22px] h-[22px] flex-shrink-0" />}
        <div className="w-[22px] h-[22px] flex items-center justify-center flex-shrink-0">
          <ThreeDashIcon className="text-text-disabled" />
        </div>
        <span className="flex-1 text-sm text-text-secondary leading-relaxed truncate">
          {normalizeContent(claim.content)}
        </span>
        <Meta sourceLabel={sourceLabel} dotCls={dotCls} rowDate={rowDate} />
      </div>
    );
  }

  return (
    <button type="button" className={cn(baseRowCls, 'hover:bg-surface-base cursor-pointer w-full text-left')} onClick={() => onOpenClaim?.(claim)}>
      {/* col1: hover-revealed checkbox (stays visible when selected) */}
      <div className="w-[22px] h-[22px] flex items-center justify-center flex-shrink-0">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={(e) => { e.stopPropagation(); onToggleSelect?.(claim.id); }}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            'h-3.5 w-3.5 accent-brand-primary transition-opacity cursor-pointer',
            isSelected ? 'opacity-100' : 'opacity-0 group-hover/row:opacity-100',
          )}
        />
      </div>
      {/* col2: spacer where tree connector is drawn absolutely */}
      {nested && <div className="w-[22px] h-[22px] flex-shrink-0" />}
      {/* col2 (flat) / col3 (nested): three-dash */}
      <div className="w-[22px] h-[22px] flex items-center justify-center flex-shrink-0">
        <ThreeDashIcon className="text-text-disabled cursor-grab" />
      </div>
      <span className="flex-1 text-sm text-text-secondary leading-relaxed truncate">
        {normalizeContent(claim.content)}
      </span>
      <Meta sourceLabel={sourceLabel} dotCls={dotCls} rowDate={rowDate} />
    </button>
  );
}

/* ─── TreeClaimsContainer ────────────────────────────────────────────────── */

const TREE_LEFT = 49;
const TREE_STEM_H = 23;
const TREE_ARM_W = 19;

function TreeClaimsContainer({
  claims,
  readOnly,
  selectedIds,
  onToggleSelect,
  onOpenClaim,
  onOpenSkills,
}: {
  claims: ExperienceClaim[];
  readOnly?: boolean;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onOpenClaim?: (claim: ExperienceClaim) => void;
  onOpenSkills?: (claims: ExperienceClaim[]) => void;
}) {
  if (claims.length === 0) return null;

  const skillClaims = claims.filter((c) => c.claim_type === 'skill');
  const otherClaims = claims.filter((c) => c.claim_type !== 'skill');
  const hasSkills = skillClaims.length > 0;

  return (
    <div>
      {otherClaims.map((claim, i) => {
        const isLast = !hasSkills && i === otherClaims.length - 1;
        return (
          <div key={claim.id} className="relative">
            <div
              className="absolute top-0 border-l border-b border-border-subtle rounded-bl-lg pointer-events-none"
              style={{ left: TREE_LEFT, height: TREE_STEM_H, width: TREE_ARM_W }}
            />
            {!isLast && (
              <div
                className="absolute w-px border-l border-border-subtle pointer-events-none"
                style={{ left: TREE_LEFT, top: TREE_STEM_H, bottom: 0 }}
              />
            )}
            <ClaimRow
              claim={claim}
              readOnly={readOnly}
              nested
              isSelected={selectedIds?.has(claim.id)}
              onToggleSelect={onToggleSelect}
              onOpenClaim={onOpenClaim}
            />
          </div>
        );
      })}
      {hasSkills && (
        <div className="relative">
          <div
            className="absolute top-0 border-l border-b border-border-subtle rounded-bl-lg pointer-events-none"
            style={{ left: TREE_LEFT, height: TREE_STEM_H, width: TREE_ARM_W }}
          />
          <SkillsInlineRow
            claims={skillClaims}
            nested
            onOpenSkills={onOpenSkills ? () => onOpenSkills(skillClaims) : undefined}
          />
        </div>
      )}
    </div>
  );
}

/* ─── GroupRow ───────────────────────────────────────────────────────────── */

function GroupRow({
  node,
  isNested = false,
  roleGroups,
  onDelete,
  onDeleteGroup,
  onOpenAssociate,
  onClearAssociation,
  onOpenGroup,
  readOnly = false,
  selectedIds,
  onToggleSelect,
  onOpenClaim,
  onOpenSkills,
}: {
  node: GroupNode;
  isNested?: boolean;
  roleGroups: ExperienceGroup[];
  onDelete: (id: string) => Promise<void>;
  onDeleteGroup: (claimIds: string[]) => Promise<void>;
  onOpenAssociate?: (repoGroupId: string) => void;
  onClearAssociation?: (repoGroupId: string) => void;
  onOpenGroup?: (group: ExperienceGroup) => void;
  readOnly?: boolean;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onOpenClaim?: (claim: ExperienceClaim) => void;
  onOpenSkills?: (claims: ExperienceClaim[]) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const { group, claims, children } = node;

  function countAll(n: GroupNode): number {
    const nonSkill = n.claims.filter((c) => c.claim_type !== 'skill').length;
    const hasSkills = n.claims.some((c) => c.claim_type === 'skill') ? 1 : 0;
    return nonSkill + hasSkills + n.children.reduce((s, c) => s + countAll(c), 0);
  }
  const totalCount = countAll(node);

  const allDirectClaimIds = claims.map((c) => c.id);
  const isRepo = group.group_type === 'repository';
  const hasParent = !!group.parent_group_id;
  const hasContent = claims.length > 0 || children.length > 0;

  const skillClaims = claims.filter((c) => c.claim_type === 'skill');
  const otherClaims = claims.filter((c) => c.claim_type !== 'skill');

  const claimRowProps = { readOnly, selectedIds, onToggleSelect, onOpenClaim };
  const childGroupProps = { roleGroups, onDelete, onDeleteGroup, onOpenAssociate, onClearAssociation, onOpenGroup, onOpenSkills, ...claimRowProps };

  return (
    <div>
      {/* ── Group header row ── */}
      <div
        className={cn(
          'flex items-center gap-2 px-2 min-h-[44px]',
          isNested
            ? 'hover:bg-surface-base transition-colors'
            : 'bg-surface-sunken hover:bg-surface-overlay transition-colors',
        )}
      >
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? 'Collapse group' : 'Expand group'}
          className={cn(
            'w-[22px] h-[22px] flex items-center justify-center flex-shrink-0 rounded',
            'text-text-disabled hover:text-text-secondary transition-colors',
          )}
        >
          <ChevronRight className={cn('h-3 w-3 transition-transform duration-150', expanded && 'rotate-90')} />
        </button>

        {/* Clickable: icon + name + count → opens group modal */}
        <button
          type="button"
          onClick={() => !readOnly && onOpenGroup?.(group)}
          className={cn(
            'flex items-center gap-2 min-w-0 overflow-hidden',
            !readOnly && onOpenGroup && 'cursor-pointer hover:opacity-80 transition-opacity',
          )}
        >
          <div className="w-[22px] h-[22px] flex items-center justify-center flex-shrink-0">
            <GroupTypeIcon
              type={group.group_type}
              className={cn(isNested ? 'text-text-disabled' : 'text-text-tertiary')}
            />
          </div>
          <span className={cn(
            'text-sm truncate',
            isNested ? 'font-medium text-text-secondary' : 'font-semibold text-text-primary',
          )}>
            {group.name}
          </span>
          {totalCount > 0 && (
            <span className={cn(
              'text-xs font-medium flex-shrink-0',
              isNested ? 'text-text-disabled' : 'text-text-tertiary',
            )}>
              {totalCount}
            </span>
          )}
        </button>

        {/* Spacer */}
        {isNested
          ? <div className="flex-1 h-px bg-border-subtle mx-1 min-w-4" aria-hidden="true" />
          : <div className="flex-1" />
        }

        {!readOnly && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="Group options"
                className={cn(
                  'w-6 h-6 flex items-center justify-center rounded flex-shrink-0',
                  'text-text-disabled hover:text-text-secondary hover:bg-surface-sunken transition-colors',
                )}
              >
                <MoreHorizontal className="h-3.5 w-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {isRepo && !hasParent && onOpenAssociate && roleGroups.length > 0 && (
                <DropdownMenuItem onSelect={() => onOpenAssociate(group.id)}>
                  <Link className="h-3.5 w-3.5 mr-2" />
                  Associate with role
                </DropdownMenuItem>
              )}
              {isRepo && hasParent && onClearAssociation && (
                <DropdownMenuItem onSelect={() => onClearAssociation(group.id)}>
                  <Link2Off className="h-3.5 w-3.5 mr-2" />
                  Remove association
                </DropdownMenuItem>
              )}
              {allDirectClaimIds.length > 0 && (
                <DropdownMenuItem
                  onSelect={() => onDeleteGroup(allDirectClaimIds)}
                  className="text-error focus:text-error"
                >
                  <Trash2 className="h-3.5 w-3.5 mr-2" />
                  Delete all claims
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* ── Expanded content ── */}
      <div className={cn('grid transition-all duration-200', expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
        <div className="overflow-hidden">
          {hasContent && (
            <div>
              {children.map((childNode) => (
                <GroupRow key={childNode.group.id} node={childNode} isNested {...childGroupProps} />
              ))}

              {isNested ? (
                <TreeClaimsContainer claims={claims} onOpenSkills={onOpenSkills} {...claimRowProps} />
              ) : (
                <>
                  {otherClaims.map((claim) => (
                    <ClaimRow key={claim.id} claim={claim} {...claimRowProps} />
                  ))}
                  <SkillsInlineRow
                    claims={skillClaims}
                    onOpenSkills={onOpenSkills ? () => onOpenSkills(skillClaims) : undefined}
                  />
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── UngroupedSection ───────────────────────────────────────────────────── */

function UngroupedSection({
  claims,
  readOnly = false,
  selectedIds,
  onToggleSelect,
  onOpenClaim,
  onOpenSkills,
}: {
  claims: ExperienceClaim[];
  readOnly?: boolean;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onOpenClaim?: (claim: ExperienceClaim) => void;
  onOpenSkills?: (claims: ExperienceClaim[]) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  if (claims.length === 0) return null;

  const skillClaims = claims.filter((c) => c.claim_type === 'skill');
  const otherClaims = claims.filter((c) => c.claim_type !== 'skill');
  const claimRowProps = { readOnly, selectedIds, onToggleSelect, onOpenClaim };

  return (
    <div>
      <div className="flex items-center gap-2 px-2 min-h-[44px] bg-surface-sunken hover:bg-surface-overlay transition-colors">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="w-[22px] h-[22px] flex items-center justify-center flex-shrink-0 rounded text-text-disabled hover:text-text-secondary transition-colors"
        >
          <ChevronRight className={cn('h-3 w-3 transition-transform duration-150', expanded && 'rotate-90')} />
        </button>
        <div className="w-[22px] h-[22px] flex items-center justify-center flex-shrink-0" aria-hidden="true">
          <DashedSquareIcon className="h-4 w-4 text-text-disabled" />
        </div>
        <span className="text-sm font-semibold text-text-primary">Ungrouped</span>
        <span className="text-xs font-medium text-text-tertiary">
          {otherClaims.length + (skillClaims.length > 0 ? 1 : 0)}
        </span>
        <div className="flex-1" />
      </div>

      <div className={cn('grid transition-all duration-200', expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}>
        <div className="overflow-hidden">
          {otherClaims.map((claim) => (
            <ClaimRow key={claim.id} claim={claim} {...claimRowProps} />
          ))}
          <SkillsInlineRow
            claims={skillClaims}
            onOpenSkills={onOpenSkills ? () => onOpenSkills(skillClaims) : undefined}
          />
        </div>
      </div>
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
      if (data.chunks.length <= 1) { await persist(data.chunks); }
      else { setPreview(data.chunks); setSelected(new Set(data.chunks.map((_, i) => i))); }
    } finally { setParsing(false); }
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
        source_type: 'user_input' as const,
        source_ref: null, claim_type: 'other' as const, content,
        group_key: null, group_id: null, date_range: null,
        keywords: null, provenance_metadata: null, original_content: null,
        status: 'active' as const, position: 9999 + i, updated_at: now,
      }));
      onAdded(newChunks);
      reset();
      toast.success(`${chunks.length} claim${chunks.length !== 1 ? 's' : ''} added`);
    } finally { setPersisting(false); }
  };

  const toggleSelect = (i: number) => {
    setSelected((prev) => { const next = new Set(prev); if (next.has(i)) next.delete(i); else next.add(i); return next; });
  };

  const textareaCls =
    'w-full rounded-md border border-border-default bg-surface-elevated px-3 py-2.5 text-sm text-text-primary ' +
    'placeholder:text-text-disabled outline-none transition-colors duration-100 resize-none ' +
    'focus:border-text-primary focus:shadow-[0_0_0_2px_rgba(0,0,0,0.06)] ' +
    'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.06)]';

  return (
    <div className="space-y-2">
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
            <button type="button" onClick={() => persist(preview.filter((_, i) => selected.has(i)))} disabled={persisting || selected.size === 0}
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

/* ─── ProfileChunkEditor ─────────────────────────────────────────────────── */

export function ProfileChunkEditor({
  refreshKey,
  initialData,
  initialGroups,
  noFetch,
  readOnly,
}: {
  refreshKey?: number;
  initialData?: ExperienceClaimsResponse;
  initialGroups?: ExperienceGroup[];
  /** Hard-blocks all outgoing API calls. Use in demo/mock contexts to prevent
   *  live data leaking into the component if mock data is missing or malformed. */
  noFetch?: boolean;
  readOnly?: boolean;
}) {
  const [data, setData] = useState<ExperienceClaimsResponse | null>(initialData ?? null);
  const [loading, setLoading] = useState(!noFetch && !initialData);
  const [groups, setGroups] = useState<ExperienceGroup[]>(initialGroups ?? []);

  // Active claim modal
  const [activeClaim, setActiveClaim] = useState<ExperienceClaim | null>(null);
  // Active group modal
  const [activeGroup, setActiveGroup] = useState<ExperienceGroup | null>(null);
  // Active skills modal
  const [activeSkillClaims, setActiveSkillClaims] = useState<ExperienceClaim[] | null>(null);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  // Associate repo dialog
  const [associatingRepoGroupId, setAssociatingRepoGroupId] = useState<string | null>(null);
  const [selectedRoleGroupId, setSelectedRoleGroupId] = useState<string>('');
  const [associating, setAssociating] = useState(false);

  // Bulk move dialog
  const [movingClaimIds, setMovingClaimIds] = useState<string[]>([]);
  const [selectedMoveGroupId, setSelectedMoveGroupId] = useState<string>('');
  const [moving, setMoving] = useState(false);

  const fetchGroups = useCallback(async () => {
    try {
      const res = await fetch('/api/experience/groups');
      if (!res.ok) return;
      setGroups(await res.json());
    } catch { /* ignore */ }
  }, []);

  const fetchClaims = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/experience/claims');
      if (!res.ok) return;
      setData(await res.json());
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (noFetch || initialData) return;
    fetchClaims();
    fetchGroups();
  }, [fetchClaims, fetchGroups, refreshKey, noFetch, initialData]);

  /* ── Claim mutations ── */

  const handleSave = async (id: string, content: string) => {
    const res = await fetch(`/api/experience/claims/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Failed to save'); }
    const updated: ExperienceClaim = await res.json();
    setData((prev) => prev ? patchClaimInResponse(prev, updated) : prev);
    setActiveClaim((prev) => prev?.id === updated.id ? updated : prev);
    setActiveSkillClaims((prev) => prev?.map((c) => c.id === updated.id ? updated : c) ?? null);
  };

  const handleDelete = async (id: string) => {
    const res = await fetch(`/api/experience/claims/${id}`, { method: 'DELETE' });
    if (!res.ok) { const err = await res.json().catch(() => ({})); toastError(err.detail ?? 'Failed to delete'); return; }
    setData((prev) => prev ? removeClaimFromResponse(prev, id) : prev);
    setActiveSkillClaims((prev) => prev?.filter((c) => c.id !== id) ?? null);
  };

  const handleDeleteGroup = async (claimIds: string[]) => {
    const results = await Promise.all(claimIds.map((id) => fetch(`/api/experience/claims/${id}`, { method: 'DELETE' })));
    if (results.some((r) => !r.ok)) toastError('Some items could not be deleted');
    setData((prev) => prev ? claimIds.reduce((acc, id) => removeClaimFromResponse(acc, id), prev) : prev);
  };

  const handleMoveToGroup = async (claimId: string, groupId: string | null) => {
    const res = await fetch(`/api/experience/claims/${claimId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ group_id: groupId }),
    });
    if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Failed to move claim'); }
    const updated: ExperienceClaim = await res.json();
    setData((prev) => prev ? patchClaimInResponse(prev, updated) : prev);
    setActiveClaim((prev) => prev?.id === updated.id ? updated : prev);
  };

  /* ── Group mutations ── */

  const handleGroupSave = async (id: string, updates: GroupPatch) => {
    const res = await fetch(`/api/experience/groups/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Failed to save group'); }
    const updated: ExperienceGroup = await res.json();
    setGroups((prev) => prev.map((g) => g.id === id ? updated : g));
    setActiveGroup((prev) => prev?.id === id ? updated : prev);
  };

  const handleGroupDelete = async (id: string, cascade: boolean) => {
    const res = await fetch(`/api/experience/groups/${id}?cascade=${cascade}`, { method: 'DELETE' });
    if (!res.ok) { const err = await res.json().catch(() => ({})); toastError(err.detail ?? 'Failed to delete group'); return; }
    setGroups((prev) => {
      const filtered = prev.filter((g) => g.id !== id);
      // If cascading, child groups are also gone from the server; remove them locally too
      return cascade ? filtered.filter((g) => g.parent_group_id !== id) : filtered;
    });
    fetchClaims();
  };

  const handleAdded = (newChunks: ExperienceClaim[]) => {
    setData((prev) => prev ? { ...prev, user_input: [...(prev.user_input ?? []), ...newChunks] } : prev);
  };

  /* ── Association ── */

  const handleOpenAssociate = (repoGroupId: string) => {
    const repoGroup = groups.find((g) => g.id === repoGroupId);
    setSelectedRoleGroupId(repoGroup?.suggested_parent_id ?? repoGroup?.parent_group_id ?? '');
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
      if (!res.ok) { const err = await res.json().catch(() => ({})); toastError(err.detail ?? 'Failed to associate'); return; }
      await fetchGroups();
      toast.success('Repo linked — tailorings will treat them as unified experience.');
    } finally { setAssociating(false); setAssociatingRepoGroupId(null); }
  };

  const handleClearAssociation = async (repoGroupId: string) => {
    const res = await fetch(`/api/experience/groups/${repoGroupId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parent_group_id: '' }),
    });
    if (!res.ok) { const err = await res.json().catch(() => ({})); toastError(err.detail ?? 'Failed to remove association'); return; }
    await fetchGroups();
    toast.success('Association removed.');
  };

  /* ── Bulk move ── */

  const handleOpenBulkMove = () => { setSelectedMoveGroupId(''); setMovingClaimIds(Array.from(selectedIds)); };

  const handleConfirmMove = async () => {
    if (movingClaimIds.length === 0) return;
    setMoving(true);
    try {
      const results = await Promise.all(
        movingClaimIds.map((id) =>
          fetch(`/api/experience/claims/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ group_id: selectedMoveGroupId || null }),
          })
        )
      );
      const failed = results.filter((r) => !r.ok);
      if (failed.length > 0) toastError('Some claims could not be moved');
      for (const res of results) {
        if (res.ok) {
          const updated: ExperienceClaim = await res.json();
          setData((prev) => prev ? patchClaimInResponse(prev, updated) : prev);
        }
      }
      setSelectedIds(new Set());
      toast.success(movingClaimIds.length === 1 ? 'Claim moved.' : `${movingClaimIds.length} claims moved.`);
    } finally { setMoving(false); setMovingClaimIds([]); }
  };

  /* ── Render ── */

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-xs text-text-tertiary">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />Loading…
      </div>
    );
  }

  const allClaims = data ? flattenClaims(data) : [];
  const { nodes, ungrouped } = buildGroupTree(groups, allClaims);
  const roleGroups = groups.filter((g) => g.group_type === 'role');
  const hasTable = nodes.length > 0 || ungrouped.length > 0;
  const activeGroupDirectClaimsCount = activeGroup
    ? allClaims.filter((c) => c.group_id === activeGroup.id).length
    : 0;

  const commonGroupRowProps = {
    roleGroups,
    onDelete: handleDelete,
    onDeleteGroup: handleDeleteGroup,
    onOpenAssociate: handleOpenAssociate,
    onClearAssociation: handleClearAssociation,
    onOpenGroup: setActiveGroup,
    onOpenSkills: !readOnly ? setActiveSkillClaims : undefined,
    readOnly,
    selectedIds,
    onToggleSelect: handleToggleSelect,
    onOpenClaim: setActiveClaim,
  };

  return (
    <div className="space-y-8">

      {/* ── Experience table ── */}
      {hasTable && (
        <div className="mx-2">
          {nodes.map((node) => (
            <GroupRow key={node.group.id} node={node} {...commonGroupRowProps} />
          ))}
          <UngroupedSection
            claims={ungrouped}
            readOnly={readOnly}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
            onOpenClaim={setActiveClaim}
            onOpenSkills={!readOnly ? setActiveSkillClaims : undefined}
          />
        </div>
      )}

      {/* ── Additional experience ── */}
      <div>
        <div className="flex flex-col gap-1 mb-4">
          <h3 className="text-sm font-medium text-text-primary">Additional Experience</h3>
          <p className="text-sm text-text-tertiary">Manually add experience, skills, or context not captured above</p>
        </div>
        <AddExperienceForm onAdded={handleAdded} readOnly={readOnly} />
      </div>

      {/* ── Selection bar ── */}
      {!readOnly && selectedIds.size > 0 && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 flex items-center gap-1 px-1.5 py-1.5 rounded-full bg-surface-elevated shadow-xl border border-border-subtle">
          <span className="px-3.5 py-1.5 rounded-full text-sm font-medium text-text-primary bg-surface-base select-none whitespace-nowrap">
            {selectedIds.size} selected
          </span>
          <button
            type="button"
            onClick={() => setSelectedIds(new Set())}
            aria-label="Clear selection"
            className="w-8 h-8 flex items-center justify-center rounded-full text-text-secondary hover:bg-surface-base transition-colors flex-shrink-0"
          >
            <X className="h-3.5 w-3.5" />
          </button>
          <div className="w-px h-5 bg-border-subtle mx-1 flex-shrink-0" aria-hidden="true" />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-full text-sm font-medium text-text-primary hover:bg-surface-base transition-colors whitespace-nowrap"
              >
                <Command className="h-3.5 w-3.5" />
                Actions
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="center" className="w-44">
              <DropdownMenuItem onSelect={handleOpenBulkMove}>
                <Link className="h-3.5 w-3.5 mr-2" />
                Move to group
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => { handleDeleteGroup(Array.from(selectedIds)); setSelectedIds(new Set()); }}
                className="text-error focus:text-error"
              >
                <Trash2 className="h-3.5 w-3.5 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

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
              <label key={g.id} className={cn('flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors', selectedRoleGroupId === g.id ? 'bg-surface-sunken text-text-primary' : 'text-text-secondary hover:bg-surface-base')}>
                <input type="radio" name="role-group" value={g.id} checked={selectedRoleGroupId === g.id} onChange={() => setSelectedRoleGroupId(g.id)} className="accent-brand-primary" />
                {g.name}
              </label>
            ))}
          </div>
          <DialogFooter>
            <button type="button" onClick={() => setAssociatingRepoGroupId(null)} className="text-sm text-text-tertiary hover:text-text-secondary transition-colors">Cancel</button>
            <button type="button" onClick={handleConfirmAssociate} disabled={!selectedRoleGroupId || associating}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[8px] text-sm font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity">
              {associating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link className="h-3.5 w-3.5" />}
              Associate
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Bulk move dialog ── */}
      <Dialog open={movingClaimIds.length > 0} onOpenChange={(o) => { if (!o) setMovingClaimIds([]); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{movingClaimIds.length === 1 ? 'Move to group' : `Move ${movingClaimIds.length} claims`}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-text-secondary">Choose a group, or leave blank to make {movingClaimIds.length === 1 ? 'it' : 'them'} ungrouped.</p>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            <label className={cn('flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors', !selectedMoveGroupId ? 'bg-surface-sunken text-text-primary' : 'text-text-secondary hover:bg-surface-base')}>
              <input type="radio" name="move-group" value="" checked={!selectedMoveGroupId} onChange={() => setSelectedMoveGroupId('')} className="accent-brand-primary" />
              Ungrouped
            </label>
            {groups.map((g) => (
              <label key={g.id} className={cn('flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer text-sm transition-colors', selectedMoveGroupId === g.id ? 'bg-surface-sunken text-text-primary' : 'text-text-secondary hover:bg-surface-base')}>
                <input type="radio" name="move-group" value={g.id} checked={selectedMoveGroupId === g.id} onChange={() => setSelectedMoveGroupId(g.id)} className="accent-brand-primary" />
                <span className="flex items-center gap-1.5">
                  <GroupTypeIcon type={g.group_type} className="h-3.5 w-3.5 text-text-disabled" />
                  {g.name}
                </span>
              </label>
            ))}
          </div>
          <DialogFooter>
            <button type="button" onClick={() => setMovingClaimIds([])} className="text-sm text-text-tertiary hover:text-text-secondary transition-colors">Cancel</button>
            <button type="button" onClick={handleConfirmMove} disabled={moving}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-[8px] text-sm font-medium bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 hover:opacity-90 disabled:opacity-40 transition-opacity">
              {moving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Move
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Claim detail modal ── */}
      {!readOnly && (
        <ExperienceClaimModal
          claim={activeClaim}
          groups={groups}
          onClose={() => setActiveClaim(null)}
          onSave={handleSave}
          onDelete={handleDelete}
          onMoveToGroup={handleMoveToGroup}
        />
      )}

      {/* ── Group detail modal ── */}
      {!readOnly && (
        <ExperienceGroupModal
          group={activeGroup}
          groups={groups}
          directClaimsCount={activeGroupDirectClaimsCount}
          onClose={() => setActiveGroup(null)}
          onSave={handleGroupSave}
          onDelete={handleGroupDelete}
        />
      )}

      {/* ── Skills modal ── */}
      {!readOnly && (
        <SkillsModal
          claims={activeSkillClaims}
          onClose={() => setActiveSkillClaims(null)}
          onSave={handleSave}
          onDelete={handleDelete}
        />
      )}

    </div>
  );
}

/* ─── Response patch helpers ─────────────────────────────────────────────── */

function patchClaimInResponse(prev: ExperienceClaimsResponse, updated: ExperienceClaim): ExperienceClaimsResponse {
  const replace = (claims: ExperienceClaim[]) => claims.map((c) => (c.id === updated.id ? updated : c));
  return {
    ...prev,
    resume: prev.resume ? {
      ...prev.resume,
      work_experience: prev.resume.work_experience.map((g) => ({ ...g, chunks: replace(g.chunks) })),
      skills: replace(prev.resume.skills),
      projects: prev.resume.projects.map((g) => ({ ...g, chunks: replace(g.chunks) })),
      education: replace(prev.resume.education),
      other: replace(prev.resume.other),
    } : null,
    github: prev.github ? { repos: prev.github.repos.map((r) => ({ ...r, chunks: replace(r.chunks) })) } : null,
    user_input: prev.user_input ? replace(prev.user_input) : null,
    gap_response: prev.gap_response ? replace(prev.gap_response) : null,
    partial_response: prev.partial_response ? replace(prev.partial_response) : null,
  };
}

function removeClaimFromResponse(prev: ExperienceClaimsResponse, id: string): ExperienceClaimsResponse {
  const filter = (claims: ExperienceClaim[]) => claims.filter((c) => c.id !== id);
  const newResume = prev.resume ? {
    ...prev.resume,
    work_experience: prev.resume.work_experience.map((g) => ({ ...g, chunks: filter(g.chunks) })).filter((g) => g.chunks.length > 0),
    skills: filter(prev.resume.skills),
    projects: prev.resume.projects.map((g) => ({ ...g, chunks: filter(g.chunks) })).filter((g) => g.chunks.length > 0),
    education: filter(prev.resume.education),
    other: filter(prev.resume.other),
  } : null;
  const resumeEmpty = newResume && !newResume.work_experience.length && !newResume.skills.length && !newResume.projects.length && !newResume.education.length && !newResume.other.length;
  return {
    ...prev,
    resume: resumeEmpty ? null : newResume,
    github: prev.github ? { repos: prev.github.repos.map((r) => ({ ...r, chunks: filter(r.chunks) })) } : null,
    user_input: prev.user_input ? filter(prev.user_input) : null,
    gap_response: prev.gap_response ? filter(prev.gap_response) : null,
    partial_response: prev.partial_response ? filter(prev.partial_response) : null,
  };
}
