'use client';

import { useState } from 'react';
import { Loader2, ChevronDown, ChevronUp, Check, RotateCcw, Sparkles, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ResumeDraft, ResumeSection, EducationEntry } from '@/types';

interface BulletPolishResult {
  rewritten: string;
  unchanged: boolean;
  note: string;
}

interface Props {
  draft: ResumeDraft;
  tailoringId: string;
  onDraftChange: (draft: ResumeDraft) => void;
}

export function ResumeDraftPreview({ draft, tailoringId, onDraftChange }: Props) {
  const [polishingIds, setPolishingIds] = useState<Set<string>>(new Set());
  const [pendingRewrites, setPendingRewrites] = useState<Record<string, BulletPolishResult>>({});
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(
    draft.sections.filter(s => s.included).map(s => s.group_id)
  ));

  async function patchDraft(update: Record<string, unknown>) {
    const res = await fetch(`/api/tailorings/${tailoringId}/resume`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    if (!res.ok) return;
    const updated: ResumeDraft = await res.json();
    onDraftChange(updated);
  }

  function toggleSection(groupId: string, included: boolean) {
    const section = draft.sections.find(s => s.group_id === groupId);
    if (!section) return;
    patchDraft({
      sections: [{ ...section, included }],
    });
  }

  function toggleSectionExpand(groupId: string) {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }

  async function handlePolishBullet(claimId: string) {
    setPolishingIds(prev => new Set(prev).add(claimId));
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/resume/polish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim_ids: [claimId] }),
      });
      if (!res.ok) return;
      const data = await res.json();
      const result: BulletPolishResult = data.results?.[claimId];
      if (result && !result.unchanged) {
        setPendingRewrites(prev => ({ ...prev, [claimId]: result }));
      }
    } finally {
      setPolishingIds(prev => { const next = new Set(prev); next.delete(claimId); return next; });
    }
  }

  function acceptRewrite(section: ResumeSection, claimId: string, rewrite: string) {
    setPendingRewrites(prev => { const next = { ...prev }; delete next[claimId]; return next; });
    patchDraft({ rewrites: { [claimId]: rewrite } });
  }

  function revertRewrite(claimId: string) {
    // Revert: patch empty string means "clear rewrite" — send section without rewrite
    setPendingRewrites(prev => { const next = { ...prev }; delete next[claimId]; return next; });
    const section = draft.sections.find(s => s.claim_ids.includes(claimId));
    if (!section) return;
    const rewrites = { ...section.rewrites };
    delete rewrites[claimId];
    patchDraft({ sections: [{ ...section, rewrites }] });
  }

  function handleContactChange(field: 'linkedin_url' | 'location', value: string) {
    patchDraft({
      contact_override: {
        ...draft.contact_override,
        [field]: value || null,
      },
    });
  }

  const hasNoResumeSource = draft.warnings.includes('no_resume_source');

  return (
    <div className="space-y-4">
      {/* Warnings */}
      {hasNoResumeSource && (
        <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40 text-sm">
          <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <p className="text-amber-800 dark:text-amber-300">
            No resume uploaded — contact info and role dates may be incomplete. Upload a resume in{' '}
            <a href="/dashboard/experience" className="underline">My Experience</a> for a richer export.
          </p>
        </div>
      )}

      {/* How this was built */}
      <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-surface-base border border-border-subtle text-sm text-text-secondary">
        <AlertCircle className="h-4 w-4 text-text-tertiary shrink-0 mt-0.5" />
        <div className="space-y-1.5">
          <p>
            This resume was built by selecting your most relevant experience for this specific role. Sections are ranked by match strength. Toggle bullets on/off, edit your contact info, or use AI polish to tighten individual bullets.
          </p>
          <p className="text-text-tertiary text-xs">
            Note: the Tailoring&apos;s match scoring references your original uploaded resume. If you edit bullets here, the Tailoring&apos;s analysis may reflect different content than what&apos;s in this export.
          </p>
        </div>
      </div>

      {/* Contact info */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider px-0.5">Contact</p>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label htmlFor="resume-linkedin" className="text-xs text-text-secondary block mb-1">LinkedIn URL</label>
            <input
              id="resume-linkedin"
              type="url"
              defaultValue={draft.contact_override.linkedin_url ?? ''}
              onBlur={(e) => handleContactChange('linkedin_url', e.target.value)}
              placeholder="https://linkedin.com/in/…"
              className="w-full h-8 px-2.5 text-sm rounded-[8px] border border-border-default bg-surface-elevated text-text-primary placeholder:text-text-disabled focus:outline-none focus:border-border-focus"
            />
          </div>
          <div>
            <label htmlFor="resume-location" className="text-xs text-text-secondary block mb-1">Location</label>
            <input
              id="resume-location"
              type="text"
              defaultValue={draft.contact_override.location ?? ''}
              onBlur={(e) => handleContactChange('location', e.target.value)}
              placeholder="City, State"
              className="w-full h-8 px-2.5 text-sm rounded-[8px] border border-border-default bg-surface-elevated text-text-primary placeholder:text-text-disabled focus:outline-none focus:border-border-focus"
            />
          </div>
        </div>
      </div>

      {/* Experience sections */}
      {draft.sections.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider px-0.5">Experience</p>
          {draft.sections.map((section) => {
            const expanded = expandedSections.has(section.group_id);
            return (
              <div
                key={section.group_id}
                className={cn(
                  'rounded-xl border transition-colors',
                  section.included
                    ? 'border-border-default bg-surface-elevated'
                    : 'border-border-subtle bg-surface-base opacity-60'
                )}
              >
                {/* Section header */}
                <div className="flex items-center gap-2 px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={section.included}
                    onChange={(e) => toggleSection(section.group_id, e.target.checked)}
                    className="h-3.5 w-3.5 rounded accent-brand-primary shrink-0"
                  />
                  <button
                    type="button"
                    onClick={() => toggleSectionExpand(section.group_id)}
                    className="flex-1 flex items-center gap-1.5 min-w-0 text-left"
                  >
                    <span className="text-sm font-medium text-text-primary truncate">
                      {section.group_name || section.group_id}
                    </span>
                    <span className="text-xs text-text-tertiary shrink-0">
                      {section.claim_ids.length} bullet{section.claim_ids.length !== 1 ? 's' : ''}
                    </span>
                    {expanded
                      ? <ChevronUp className="h-3.5 w-3.5 text-text-tertiary shrink-0 ml-auto" />
                      : <ChevronDown className="h-3.5 w-3.5 text-text-tertiary shrink-0 ml-auto" />}
                  </button>
                </div>

                {/* Bullets */}
                {expanded && section.included && (
                  <div className="border-t border-border-subtle px-3 py-2 space-y-1.5">
                    {section.claim_ids.map((claimId) => {
                      const activeRewrite = section.rewrites[claimId];
                      const pending = pendingRewrites[claimId];
                      const polishing = polishingIds.has(claimId);
                      const displayText = activeRewrite || claimId; // claim_id is a placeholder; actual content resolved server-side

                      return (
                        <div key={claimId} className="group flex items-start gap-2">
                          <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-text-tertiary shrink-0" />
                          <div className="flex-1 min-w-0">
                            {pending ? (
                              <div className="space-y-1.5">
                                <p className="text-sm text-text-secondary line-through">{displayText}</p>
                                <p className="text-sm text-text-primary">{pending.rewritten}</p>
                                <p className="text-xs text-text-tertiary italic">{pending.note}</p>
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => acceptRewrite(section, claimId, pending.rewritten)}
                                    className="inline-flex items-center gap-1 text-xs text-success hover:text-success/80"
                                  >
                                    <Check className="h-3 w-3" /> Accept
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setPendingRewrites(prev => { const next = { ...prev }; delete next[claimId]; return next; })}
                                    className="inline-flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary"
                                  >
                                    <RotateCcw className="h-3 w-3" /> Discard
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-start gap-1.5">
                                <p className={cn('text-sm flex-1', activeRewrite ? 'text-text-primary' : 'text-text-secondary')}>
                                  {displayText}
                                </p>
                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                                  {activeRewrite && (
                                    <button
                                      type="button"
                                      onClick={() => revertRewrite(claimId)}
                                      className="p-0.5 text-text-tertiary hover:text-text-secondary rounded"
                                      title="Revert to original"
                                    >
                                      <RotateCcw className="h-3 w-3" />
                                    </button>
                                  )}
                                  <button
                                    type="button"
                                    onClick={() => handlePolishBullet(claimId)}
                                    disabled={polishing}
                                    className="p-0.5 text-text-tertiary hover:text-brand-primary rounded"
                                    title="Polish with AI"
                                  >
                                    {polishing
                                      ? <Loader2 className="h-3 w-3 animate-spin" />
                                      : <Sparkles className="h-3 w-3" />}
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Skills */}
      {draft.skills_claim_ids.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider px-0.5">Skills</p>
          <div className="px-3 py-2.5 rounded-xl border border-border-default bg-surface-elevated">
            <p className="text-sm text-text-secondary">{draft.skills_claim_ids.length} skill{draft.skills_claim_ids.length !== 1 ? 's' : ''} included</p>
          </div>
        </div>
      )}

      {/* Education */}
      {(draft.education_data ?? []).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider px-0.5">Education</p>
          <div className="px-3 py-2.5 rounded-xl border border-border-default bg-surface-elevated space-y-1">
            {(draft.education_data ?? []).map((edu: EducationEntry, i: number) => (
              <div key={i} className="flex items-baseline justify-between gap-2">
                <span className="text-sm text-text-primary">{edu.name}{edu.degree ? ` — ${edu.degree}` : ''}</span>
                {edu.end_date && <span className="text-xs text-text-tertiary shrink-0">{edu.end_date}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
