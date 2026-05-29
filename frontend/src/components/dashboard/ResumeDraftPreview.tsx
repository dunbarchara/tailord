'use client';

import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ResumeDraft, ResumeSection } from '@/types';

interface Props {
  draft: ResumeDraft;
  tailoringId: string;
  onDraftChange: (draft: ResumeDraft) => void;
}

export function ResumeDraftPreview({ draft, tailoringId, onDraftChange }: Props) {
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

  function toggleSection(section: ResumeSection, included: boolean) {
    patchDraft({ sections: [{ ...section, included }] });
  }

  function handleContactChange(field: 'linkedin_url' | 'location', value: string) {
    patchDraft({ contact_override: { ...draft.contact_override, [field]: value || null } });
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

      {/* Hint */}
      <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-surface-base border border-border-subtle text-xs text-text-secondary">
        <AlertCircle className="h-3.5 w-3.5 text-text-tertiary shrink-0 mt-0.5" />
        <p>Click any text in the preview to edit it. Hover bullets for AI polish.</p>
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
              onBlur={e => handleContactChange('linkedin_url', e.target.value)}
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
              onBlur={e => handleContactChange('location', e.target.value)}
              placeholder="City, State"
              className="w-full h-8 px-2.5 text-sm rounded-[8px] border border-border-default bg-surface-elevated text-text-primary placeholder:text-text-disabled focus:outline-none focus:border-border-focus"
            />
          </div>
        </div>
      </div>

      {/* Section toggles */}
      {draft.sections.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider px-0.5">Sections</p>
          {draft.sections.map(section => (
            <div
              key={section.group_id}
              className={cn(
                'flex items-center gap-2.5 px-3 py-2 rounded-xl border transition-colors',
                section.included
                  ? 'border-border-default bg-surface-elevated'
                  : 'border-border-subtle bg-surface-base opacity-60',
              )}
            >
              <input
                type="checkbox"
                checked={section.included}
                onChange={e => toggleSection(section, e.target.checked)}
                className="h-3.5 w-3.5 rounded accent-brand-primary shrink-0"
              />
              <span className="flex-1 text-sm text-text-primary truncate min-w-0">
                {section.group_name || section.group_id}
              </span>
              <span className="text-xs text-text-tertiary shrink-0">
                {section.claim_ids.length} bullet{section.claim_ids.length !== 1 ? 's' : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Skills summary */}
      {draft.skills_claim_ids.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider px-0.5">Skills</p>
          <div className="px-3 py-2 rounded-xl border border-border-default bg-surface-elevated">
            <p className="text-xs text-text-secondary">
              {draft.skills_claim_ids.length} skill{draft.skills_claim_ids.length !== 1 ? 's' : ''} — click to edit in preview
            </p>
          </div>
        </div>
      )}

      {/* Education summary */}
      {(draft.education_data ?? []).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-text-tertiary uppercase tracking-wider px-0.5">Education</p>
          <div className="px-3 py-2.5 rounded-xl border border-border-default bg-surface-elevated space-y-1">
            {(draft.education_data ?? []).map((edu, i) => (
              <div key={i} className="flex items-baseline justify-between gap-2">
                <span className="text-sm text-text-primary truncate">
                  {edu.name}{edu.degree ? ` \u2014 ${edu.degree}` : ''}
                </span>
                {edu.end_date && <span className="text-xs text-text-tertiary shrink-0">{edu.end_date}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
