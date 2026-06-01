'use client';

import { useState, useEffect, useCallback } from 'react';
import { Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import { ProfileChunkEditor } from '@/components/dashboard/ProfileChunkEditor';
import type { ExperienceRecord, ExperienceClaimsResponse, ExperienceGroup, ProfileCorrections } from '@/types';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

const _MONTH_ABBR: Record<string, number> = {
  jan:0, feb:1, mar:2, apr:3, may:4, jun:5, jul:6, aug:7, sep:8, oct:9, nov:10, dec:11,
};

function _parseDate(token: string): Date | null {
  const t = token.trim().toLowerCase();
  if (['present', 'current', 'now', 'today'].includes(t)) return new Date();
  let m = t.match(/^(\d{1,2})[/-](\d{4})$/);
  if (m) return new Date(parseInt(m[2]), parseInt(m[1]) - 1, 1);
  m = t.match(/^([a-z]{3})\s+(\d{4})$/);
  if (m && m[1] in _MONTH_ABBR) return new Date(parseInt(m[2]), _MONTH_ABBR[m[1]], 1);
  m = t.match(/^(\d{4})$/);
  if (m) return new Date(parseInt(m[1]), 0, 1);
  return null;
}

// computeYoE: parses duration strings (e.g. "Mar 2020 – Present") from each role,
// builds date intervals, merges overlapping ones (handles concurrent roles correctly),
// then returns the total accumulated years as a float.
function computeYoE(workExperience: Array<{ duration?: string | null }>): number {
  const intervals: Array<[Date, Date]> = [];
  for (const role of workExperience) {
    const dur = role.duration?.trim();
    if (!dur) continue;
    const parts = dur.split(/\s*[-–—]\s*|\s+to\s+/);
    if (parts.length !== 2) continue;
    const start = _parseDate(parts[0]);
    const end = _parseDate(parts[1]);
    if (start && end && end >= start) intervals.push([start, end]);
  }
  if (!intervals.length) return 0;
  const sorted = [...intervals].sort((a, b) => a[0].getTime() - b[0].getTime());
  // Merge overlapping intervals so concurrent roles don't double-count time
  const merged: Array<[Date, Date]> = [sorted[0]];
  for (const [s, e] of sorted.slice(1)) {
    const last = merged[merged.length - 1];
    if (s <= last[1]) { merged[merged.length - 1] = [last[0], e > last[1] ? e : last[1]]; }
    else { merged.push([s, e]); }
  }
  const totalMs = merged.reduce((sum, [s, e]) => sum + (e.getTime() - s.getTime()), 0);
  return Math.round((totalMs / (365.25 * 24 * 60 * 60 * 1000)) * 10) / 10;
}

/* ─── Shared styles ─────────────────────────────────────────────────────── */

const inputCls =
  'w-full h-10 rounded-xl border border-border-default bg-surface-elevated px-3 text-sm text-text-primary ' +
  'placeholder:text-text-disabled outline-none transition-colors duration-100 ' +
  'hover:border-border-strong hover:bg-surface-base ' +
  'focus:border-text-primary focus:bg-surface-elevated focus:shadow-[0_0_0_2px_rgba(0,0,0,0.08)] ' +
  'dark:focus:shadow-[0_0_0_2px_rgba(255,255,255,0.08)] disabled:opacity-50 disabled:cursor-not-allowed';

const saveBtnCls =
  'inline-flex items-center gap-1.5 justify-center h-9 px-3 rounded-[10px] text-sm font-normal tracking-[-0.1px] ' +
  'bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 ' +
  'hover:opacity-90 transition-opacity ' +
  'disabled:bg-surface-base dark:disabled:bg-surface-overlay disabled:text-text-disabled ' +
  'disabled:cursor-not-allowed disabled:hover:opacity-100';

/* ─── Component ─────────────────────────────────────────────────────────── */

export function ExperienceManager({
  readOnly,
  initialRecord,
  initialChunks,
  initialGroups,
}: {
  readOnly?: boolean;
  initialRecord?: ExperienceRecord;
  initialChunks?: ExperienceClaimsResponse;
  initialGroups?: ExperienceGroup[];
} = {}) {
  // Hard-block all outgoing API calls when mock/demo data is provided.
  const noFetch = !!initialRecord;

  const [record, setRecord] = useState<ExperienceRecord | null>(initialRecord ?? null);

  const _emptyProfile = { yoe_override: '', title: '', location: '', headline: '', summary: '', email: '', phone: '', linkedin: '' };
  const [profileFields, setProfileFields] = useState(_emptyProfile);
  const [profileFieldsInitial, setProfileFieldsInitial] = useState(_emptyProfile);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileExpanded, setProfileExpanded] = useState(false);

  const syncProfileFromRecord = useCallback((r: ExperienceRecord) => {
    const corrections: ProfileCorrections = r.extracted_profile?.corrections ?? {};
    const resume = r.extracted_profile?.resume;
    const fields = {
      yoe_override: corrections.yoe_override != null ? String(corrections.yoe_override) : '',
      title: corrections.title || resume?.title || '',
      location: corrections.location || resume?.location || '',
      headline: corrections.headline || resume?.headline || '',
      summary: corrections.summary || resume?.summary || '',
      email: corrections.email || resume?.email || '',
      phone: corrections.phone || resume?.phone || '',
      linkedin: corrections.linkedin || resume?.linkedin || '',
    };
    setProfileFields(fields);
    setProfileFieldsInitial(fields);
  }, []);

  useEffect(() => {
    if (noFetch) {
      if (initialRecord) syncProfileFromRecord(initialRecord);
      return;
    }
    fetch('/api/experience')
      .then((r) => r.ok ? r.json() : null)
      .then((r: ExperienceRecord | null) => {
        if (r) { setRecord(r); syncProfileFromRecord(r); }
      })
      .catch(() => {});
  }, [noFetch, initialRecord, syncProfileFromRecord]);

  const hasProfileData = !!(record?.extracted_profile && Object.keys(record.extracted_profile).length > 0);

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      const yoe = parseFloat(profileFields.yoe_override);
      const payload: Record<string, string | number | null> = {
        yoe_override: (profileFields.yoe_override !== '' && !isNaN(yoe)) ? yoe : null,
        title: profileFields.title,
        location: profileFields.location,
        headline: profileFields.headline,
        summary: profileFields.summary,
        email: profileFields.email,
        phone: profileFields.phone,
        linkedin: profileFields.linkedin,
      };

      const res = await fetch('/api/experience', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toastError(err.detail ?? 'Failed to save profile signals');
        return;
      }
      const updated = await res.json() as ExperienceRecord;
      setRecord(updated);
      setProfileFieldsInitial(profileFields);
      toast.success('Profile signals saved');
    } catch {
      toastError('Failed to save profile signals');
    } finally {
      setProfileSaving(false);
    }
  };

  /* ─── Render ─────────────────────────────────────────────────────────────── */

  return (
    <div className="h-full flex flex-col bg-surface-elevated">

      {/* Topbar */}
      <div className="shrink-0 flex items-center h-12 px-6 bg-surface-elevated">
        <span className="text-sm font-medium text-text-primary tracking-[-0.1px]">My Experience</span>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="mx-auto px-6 lg:px-16 pt-8 pb-24 max-w-6xl">

          {/* Heading */}
          <div className="flex flex-col gap-1 pb-4">
            <h2 className="text-lg font-medium text-text-primary tracking-[-0.2px]">My Experience</h2>
            <p className="text-sm text-text-secondary">Review your inferred profile and edit your experience claims</p>
          </div>

          {/* Inferred Profile Signals */}
          {hasProfileData && (
            <div className="mt-6 pb-8 border-b border-zinc-950/5 dark:border-white/5">
              <button
                type="button"
                onClick={() => setProfileExpanded((v) => !v)}
                className="flex w-full items-start justify-between gap-3 text-left"
              >
                <div className="flex flex-col gap-1">
                  <h2 className="text-sm font-medium text-text-primary">Inferred Profile</h2>
                  <p className="text-sm text-text-tertiary">
                    {profileExpanded
                      ? 'These signals are used in generation — edit to correct any inaccuracies.'
                      : 'Expand to review inferred signals — years of experience, title, location, and more.'}
                  </p>
                </div>
                <span className="mt-0.5 shrink-0 text-text-tertiary">
                  {profileExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </span>
              </button>
              {profileExpanded && (
                <>
                  <div className="mt-5 space-y-4">

                    {/* Row 1: Contact — Email · Phone · LinkedIn */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-email" className="text-xs font-medium text-text-secondary">Email</label>
                        <input
                          id="profile-email"
                          type="email"
                          value={profileFields.email}
                          onChange={(e) => setProfileFields((p) => ({ ...p, email: e.target.value }))}
                          placeholder="you@example.com"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-phone" className="text-xs font-medium text-text-secondary">Phone</label>
                        <input
                          id="profile-phone"
                          type="tel"
                          value={profileFields.phone}
                          onChange={(e) => setProfileFields((p) => ({ ...p, phone: e.target.value }))}
                          placeholder="+1 555 000 0000"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-linkedin" className="text-xs font-medium text-text-secondary">LinkedIn</label>
                        <input
                          id="profile-linkedin"
                          type="text"
                          value={profileFields.linkedin}
                          onChange={(e) => setProfileFields((p) => ({ ...p, linkedin: e.target.value }))}
                          placeholder="linkedin.com/in/username"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                    </div>

                    {/* Row 2: YoE · Title · Location */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-yoe" className="text-xs font-medium text-text-secondary">Years of experience</label>
                        <input
                          id="profile-yoe"
                          type="number"
                          min="0"
                          step="0.5"
                          value={profileFields.yoe_override}
                          onChange={(e) => setProfileFields((p) => ({ ...p, yoe_override: e.target.value }))}
                          placeholder={(() => {
                            const we = record?.extracted_profile?.resume?.work_experience ?? [];
                            const yoe = computeYoE(we);
                            return yoe >= 0 ? `${yoe} (auto-computed)` : 'Auto-computed';
                          })()}
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-title" className="text-xs font-medium text-text-secondary">Title</label>
                        <input
                          id="profile-title"
                          type="text"
                          value={profileFields.title}
                          onChange={(e) => setProfileFields((p) => ({ ...p, title: e.target.value }))}
                          placeholder="e.g. Software Engineer"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <label htmlFor="profile-location" className="text-xs font-medium text-text-secondary">Location</label>
                        <input
                          id="profile-location"
                          type="text"
                          value={profileFields.location}
                          onChange={(e) => setProfileFields((p) => ({ ...p, location: e.target.value }))}
                          placeholder="e.g. San Francisco, CA"
                          disabled={readOnly}
                          className={inputCls}
                        />
                      </div>
                    </div>

                    {/* Row 3: Headline (full width) */}
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="profile-headline" className="text-xs font-medium text-text-secondary">Headline</label>
                      <input
                        id="profile-headline"
                        type="text"
                        value={profileFields.headline}
                        onChange={(e) => setProfileFields((p) => ({ ...p, headline: e.target.value }))}
                        placeholder="e.g. Senior Software Engineer building developer tools"
                        disabled={readOnly}
                        className={inputCls}
                      />
                    </div>

                    {/* Row 4: Summary (full width) */}
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="profile-summary" className="text-xs font-medium text-text-secondary">Summary</label>
                      <textarea
                        id="profile-summary"
                        value={profileFields.summary}
                        onChange={(e) => setProfileFields((p) => ({ ...p, summary: e.target.value }))}
                        placeholder="Professional summary"
                        disabled={readOnly}
                        rows={3}
                        className={cn(inputCls, 'h-auto py-2 resize-none')}
                      />
                    </div>

                  </div>
                  {!readOnly && (
                    <div className="mt-4">
                      <button
                        type="button"
                        onClick={handleProfileSave}
                        disabled={profileSaving || JSON.stringify(profileFields) === JSON.stringify(profileFieldsInitial)}
                        className={saveBtnCls}
                      >
                        {profileSaving ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving…</> : 'Save signals'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Parsed experience */}
          <div className="mt-8">
            <ProfileChunkEditor refreshKey={0} initialData={initialChunks} initialGroups={initialGroups} noFetch={noFetch} readOnly={readOnly} />
          </div>

        </div>
      </div>

    </div>
  );
}
