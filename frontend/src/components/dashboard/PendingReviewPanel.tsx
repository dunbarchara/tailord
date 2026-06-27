'use client';

import { useState, useMemo } from 'react';
import { Check, X, ChevronDown, GitMerge, ExternalLink, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import { SOURCE_DOT_CLS, SOURCE_LABELS } from './experience-claim-utils';
import type { ExperienceClaim } from '@/types';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

async function bulkReview(
  claimIds: string[],
  action: 'approve' | 'reject',
  mergeIntoId?: string,
): Promise<void> {
  const res = await fetch('/api/experience/claims/bulk-review', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      claim_ids: claimIds,
      action,
      merge_into_id: mergeIntoId ?? null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Request failed');
  }
}

async function patchClaim(id: string, status: 'active' | 'archived'): Promise<void> {
  const res = await fetch(`/api/experience/claims/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Request failed');
  }
}

/* ─── PendingClaimRow ────────────────────────────────────────────────────── */

function PendingClaimRow({
  claim,
  checked,
  onCheck,
  onApprove,
  onReject,
}: {
  claim: ExperienceClaim;
  checked: boolean;
  onCheck: (id: string, checked: boolean) => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [busy, setBusy] = useState(false);

  const provenance = claim.provenance_metadata;
  const dotCls = SOURCE_DOT_CLS[claim.source_type] ?? 'bg-zinc-400';
  const sourceLabel = SOURCE_LABELS[claim.source_type] ?? claim.source_type;

  const handleApprove = async () => {
    setBusy(true);
    try {
      await patchClaim(claim.id, 'active');
      onApprove(claim.id);
      toast.success('Claim approved');
    } catch (e) {
      toastError(e instanceof Error ? e.message : 'Failed to approve');
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    setBusy(true);
    try {
      await patchClaim(claim.id, 'archived');
      onReject(claim.id);
      toast.success('Claim rejected');
    } catch (e) {
      toastError(e instanceof Error ? e.message : 'Failed to reject');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={cn(
        'group flex items-start gap-3 px-4 py-3 rounded-xl transition-colors duration-100',
        'hover:bg-surface-sunken',
        checked && 'bg-surface-sunken',
      )}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Checkbox column — 22px wide */}
      <div className="w-[22px] flex-none flex items-center justify-center pt-0.5">
        {hovered || checked ? (
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => onCheck(claim.id, e.target.checked)}
            className="h-4 w-4 rounded border-border-default accent-brand-primary cursor-pointer"
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse flex-none" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary leading-snug">{claim.content}</p>

        {/* Meta row */}
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-text-tertiary">
          {provenance?.url && provenance?.label && (
            <a
              href={provenance.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-text-link hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <GitMerge className="h-3 w-3 flex-none" />
              {provenance.label}
              <ExternalLink className="h-2.5 w-2.5 flex-none" />
            </a>
          )}
          <span className="flex items-center gap-1">
            <span className={cn('w-1.5 h-1.5 rounded-full flex-none', dotCls)} />
            {sourceLabel}
          </span>
          {claim.updated_at && <span>{formatDate(claim.updated_at)}</span>}
        </div>
      </div>

      {/* Inline actions — visible on hover */}
      <div
        className={cn(
          'flex items-center gap-1 flex-none transition-opacity duration-100',
          hovered && !busy ? 'opacity-100' : 'opacity-0 pointer-events-none',
        )}
      >
        <button
          type="button"
          onClick={handleApprove}
          title="Approve"
          className="p-1.5 rounded-lg text-text-tertiary hover:text-green-600 hover:bg-green-500/10 transition-colors"
        >
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={handleReject}
          title="Reject"
          className="p-1.5 rounded-lg text-text-tertiary hover:text-error hover:bg-error-bg transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

/* ─── MergeProposalCard ──────────────────────────────────────────────────── */

function MergeProposalCard({
  pendingClaims,
  existingClaim,
  onAction,
}: {
  pendingClaims: ExperienceClaim[];
  existingClaim: ExperienceClaim;
  onAction: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);

  const primary = pendingClaims[0];
  const rest = pendingClaims.slice(1);
  const similarity = primary.provenance_metadata?.similarity_score;
  const provenance = primary.provenance_metadata;
  const existingDot = SOURCE_DOT_CLS[existingClaim.source_type] ?? 'bg-zinc-400';
  const existingLabel = SOURCE_LABELS[existingClaim.source_type] ?? existingClaim.source_type;

  const allIds = pendingClaims.map((c) => c.id);

  const handle = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
      onAction();
    } catch (e) {
      toastError(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-border-subtle bg-surface-elevated overflow-hidden">
      {/* NEW side */}
      <div className="px-4 pt-4 pb-3 border-b border-zinc-950/5 dark:border-white/5">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-mono uppercase text-text-tertiary tracking-wide">New</span>
          {provenance?.url && provenance?.label && (
            <a
              href={provenance.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-text-link hover:underline"
            >
              <GitMerge className="h-3 w-3 flex-none" />
              {provenance.label}
              <ExternalLink className="h-2.5 w-2.5 flex-none" />
            </a>
          )}
        </div>
        <p className="text-sm font-medium text-text-primary leading-snug">{primary.content}</p>

        {rest.length > 0 && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="inline-flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              <ChevronRight className={cn('h-3.5 w-3.5 transition-transform', expanded && 'rotate-90')} />
              {expanded ? 'Collapse' : `+ ${rest.length} more`}
            </button>
            {expanded && (
              <div className="mt-2 space-y-2">
                {rest.map((c) => (
                  <p key={c.id} className="text-sm text-text-secondary leading-snug pl-1 border-l-2 border-border-subtle">
                    {c.content}
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        {similarity != null && (
          <p className="mt-2 text-xs text-text-tertiary">≈ {Math.round(similarity * 100)}% similar</p>
        )}
      </div>

      {/* NOW side */}
      <div className="px-4 py-3 bg-surface-sunken">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-mono uppercase text-text-tertiary tracking-wide">Now</span>
          <span className="flex items-center gap-1 text-xs text-text-tertiary">
            <span className={cn('w-1.5 h-1.5 rounded-full flex-none', existingDot)} />
            {existingLabel}
            {existingClaim.date_range && <span>· {existingClaim.date_range}</span>}
          </span>
        </div>
        <p className="text-sm text-text-secondary leading-snug">{existingClaim.content}</p>
      </div>

      {/* Actions */}
      <div className="px-4 py-3 flex flex-wrap gap-2 border-t border-zinc-950/5 dark:border-white/5">
        <button
          type="button"
          disabled={busy}
          onClick={() => handle(async () => { await bulkReview(allIds, 'approve', existingClaim.id); toast.success('Merged into existing claim'); })}
          className="text-xs font-medium px-3 py-1.5 rounded-lg bg-brand-primary text-white hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          Merge into existing
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => handle(async () => { await bulkReview(allIds, 'approve'); toast.success('Kept as separate claims'); })}
          className="text-xs font-medium px-3 py-1.5 rounded-lg border border-border-default text-text-primary hover:bg-surface-sunken transition-colors disabled:opacity-50"
        >
          Keep separate
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => handle(async () => { await bulkReview(allIds, 'reject'); toast.success('Claims rejected'); })}
          className="text-xs font-medium px-3 py-1.5 rounded-lg text-text-tertiary hover:text-error hover:bg-error-bg transition-colors disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}

/* ─── PendingReviewPanel ─────────────────────────────────────────────────── */

export function PendingReviewPanel({
  pendingClaims,
  activeClaims,
  onRefresh,
}: {
  pendingClaims: ExperienceClaim[];
  /** All active claims — needed to resolve merge_candidate_id references */
  activeClaims: ExperienceClaim[];
  onRefresh: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  // Split into standalone vs merge candidates
  const { standalone, mergeGroups } = useMemo(() => {
    const standalone: ExperienceClaim[] = [];
    const byMergeCandidate = new Map<string, ExperienceClaim[]>();

    for (const c of pendingClaims) {
      const mid = c.provenance_metadata?.merge_candidate_id;
      if (mid) {
        const arr = byMergeCandidate.get(mid) ?? [];
        arr.push(c);
        byMergeCandidate.set(mid, arr);
      } else {
        standalone.push(c);
      }
    }

    // Resolve active claim for each merge group
    const activeById = new Map(activeClaims.map((c) => [c.id, c]));
    const mergeGroups: Array<{ existingClaim: ExperienceClaim; pendingClaims: ExperienceClaim[] }> = [];
    for (const [mid, candidates] of byMergeCandidate) {
      const existing = activeById.get(mid);
      if (existing) {
        mergeGroups.push({ existingClaim: existing, pendingClaims: candidates });
      } else {
        // Existing claim not found (deleted?) — treat as standalone
        standalone.push(...candidates);
      }
    }

    return { standalone, mergeGroups };
  }, [pendingClaims, activeClaims]);

  if (pendingClaims.length === 0) return null;

  const handleCheck = (id: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) { next.add(id); } else { next.delete(id); }
      return next;
    });
  };

  const handleRemove = (id: string) => {
    setSelected((prev) => { const n = new Set(prev); n.delete(id); return n; });
    onRefresh();
  };

  const handleBulkAction = async (action: 'approve' | 'reject') => {
    if (selected.size === 0) return;
    setBulkBusy(true);
    try {
      await bulkReview([...selected], action);
      toast.success(action === 'approve' ? `${selected.size} claim(s) approved` : `${selected.size} claim(s) rejected`);
      setSelected(new Set());
      onRefresh();
    } catch (e) {
      toastError(e instanceof Error ? e.message : 'Action failed');
    } finally {
      setBulkBusy(false);
    }
  };

  return (
    <div className="mb-8 bg-surface-elevated rounded-2xl border border-border-default">
      {/* Panel header */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded((v) => !v); } }}
        className="flex items-center gap-3 px-5 py-4 cursor-pointer select-none rounded-2xl hover:bg-surface-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent focus-visible:ring-offset-1"
      >
        <div className="w-10 h-10 flex-none rounded-xl border border-border-subtle bg-surface-base flex items-center justify-center">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-[-0.01em] text-text-primary">Pending Review</span>
            <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-400 text-xs font-semibold">
              {pendingClaims.length}
            </span>
          </div>
          <p className="text-xs text-text-tertiary">New experience signals waiting for your review</p>
        </div>

        <ChevronDown
          className={cn('text-text-tertiary transition-transform duration-200', expanded && 'rotate-180')}
          style={{ width: 18, height: 18 }}
        />
      </div>

      {/* Collapsible drawer */}
      <div style={{ display: 'grid', gridTemplateRows: expanded ? '1fr' : '0fr', transition: 'grid-template-rows 0.18s ease' }}>
        <div style={{ overflow: 'hidden', minHeight: 0 }}>
          <div className="px-4 pb-4 border-t border-zinc-950/5 dark:border-white/5 space-y-4 pt-4">

            {/* New captures section */}
            {standalone.length > 0 && (
              <div>
                <div className="flex items-center gap-2 px-1 mb-1">
                  <span className="text-xs font-medium text-text-tertiary uppercase tracking-wide">New captures</span>
                  <span className="text-xs text-text-disabled">{standalone.length}</span>
                </div>
                <div className="rounded-xl border border-border-subtle overflow-hidden divide-y divide-border-subtle">
                  {standalone.map((c) => (
                    <PendingClaimRow
                      key={c.id}
                      claim={c}
                      checked={selected.has(c.id)}
                      onCheck={handleCheck}
                      onApprove={handleRemove}
                      onReject={handleRemove}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Suggested merges section */}
            {mergeGroups.length > 0 && (
              <div>
                <div className="flex items-center gap-2 px-1 mb-2">
                  <span className="text-xs font-medium text-text-tertiary uppercase tracking-wide">Suggested merges</span>
                  <span className="text-xs text-text-disabled">{mergeGroups.length}</span>
                </div>
                <div className="space-y-3">
                  {mergeGroups.map((group) => (
                    <MergeProposalCard
                      key={group.existingClaim.id}
                      pendingClaims={group.pendingClaims}
                      existingClaim={group.existingClaim}
                      onAction={onRefresh}
                    />
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Floating bulk action pill */}
      {selected.size > 0 && (
        <div className="px-4 pb-4">
          <div className="flex items-center gap-2 bg-surface-overlay border border-border-default rounded-xl px-4 py-2.5 shadow-sm">
            <span className="text-xs text-text-secondary flex-1">{selected.size} selected</span>
            <button
              type="button"
              disabled={bulkBusy}
              onClick={() => handleBulkAction('approve')}
              className="text-xs font-medium px-3 py-1.5 rounded-lg bg-brand-primary text-white hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              Approve selected
            </button>
            <button
              type="button"
              disabled={bulkBusy}
              onClick={() => handleBulkAction('reject')}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border border-border-default text-text-primary hover:bg-surface-sunken transition-colors disabled:opacity-50"
            >
              Reject selected
            </button>
            <button
              type="button"
              onClick={() => setSelected(new Set())}
              className="text-xs text-text-tertiary hover:text-text-primary transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
