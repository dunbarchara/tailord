'use client';

import { useState, useEffect, useCallback } from 'react';
import { Loader2, ChevronDown, UserCircle } from 'lucide-react';
import { toast } from 'sonner';
import { cn, toastError } from '@/lib/utils';
import { ProfileChunkEditor } from '@/components/dashboard/ProfileChunkEditor';
import { PendingReviewPanel } from '@/components/dashboard/PendingReviewPanel';
import type { ExperienceRecord, ExperienceClaim, ExperienceClaimsResponse, ExperienceGroup, ProfileCorrections } from '@/types';

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

  // Claims state — for pending review panel and merge resolution
  const [pendingClaims, setPendingClaims] = useState<ExperienceClaim[]>([]);
  const [activeClaims, setActiveClaims] = useState<ExperienceClaim[]>([]);
  const [claimsRefreshKey, setClaimsRefreshKey] = useState(0);

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

  // Fetch claims for the pending review panel; re-runs when claimsRefreshKey changes
  const fetchClaimsForPanel = useCallback(async () => {
    if (noFetch) return;
    try {
      const res = await fetch('/api/experience/claims');
      if (!res.ok) return;
      const data: ExperienceClaimsResponse = await res.json();
      setPendingClaims(data.pending ?? []);
      // Flatten active claims for merge-candidate resolution in PendingReviewPanel
      const active: ExperienceClaim[] = [];
      if (data.resume) {
        data.resume.work_experience.forEach((g) => active.push(...g.chunks));
        active.push(...data.resume.skills);
        data.resume.projects.forEach((g) => active.push(...g.chunks));
        active.push(...data.resume.education, ...data.resume.other);
      }
      if (data.github) data.github.repos.forEach((r) => active.push(...r.chunks));
      active.push(
        ...(data.user_input ?? []),
        ...(data.gap_response ?? []),
        ...(data.partial_response ?? []),
      );
      setActiveClaims(active.filter((c) => c.status === 'active'));
    } catch { /* ignore */ }
  }, [noFetch]);

  useEffect(() => {
    fetchClaimsForPanel();
  }, [fetchClaimsForPanel, claimsRefreshKey]);

  const handleClaimsRefresh = useCallback(() => {
    setClaimsRefreshKey((k) => k + 1);
  }, []);

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
        <div className="mx-auto px-6 lg:px-8 pt-8 pb-24 max-w-6xl">

          {/* Heading */}
          <div className="flex flex-col gap-1 pb-4">
            <h2 className="text-lg font-medium text-text-primary tracking-[-0.2px]">My Experience</h2>
            <p className="text-sm text-text-secondary">Review your inferred profile and edit your experience claims</p>
          </div>

          {/* Pending Review Panel — appears above profile card when signals exist */}
          {!noFetch && (
            <PendingReviewPanel
              pendingClaims={pendingClaims}
              activeClaims={activeClaims}
              onRefresh={handleClaimsRefresh}
            />
          )}

          {/* Inferred Profile Signals — card */}
          {hasProfileData && (() => {
            const computedYoe = computeYoE(record?.extracted_profile?.resume?.work_experience ?? []);
            const yoeDisplay = profileFields.yoe_override
              ? `${profileFields.yoe_override} yrs`
              : computedYoe > 0 ? `${computedYoe} yrs` : null;
            const chips = [yoeDisplay, profileFields.title, profileFields.location].filter(Boolean);
            const isDirty = JSON.stringify(profileFields) !== JSON.stringify(profileFieldsInitial);

            return (
              <div className={cn(
                'mt-6 mb-8 bg-surface-elevated rounded-2xl border transition-[border-color,box-shadow] duration-150'
              )}>
                {/* Card header */}
                <div
                  role="button"
                  tabIndex={0}
                  aria-expanded={profileExpanded}
                  onClick={() => setProfileExpanded((v) => !v)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setProfileExpanded((v) => !v); } }}
                  className="flex items-center gap-3.5 px-5 py-4 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent focus-visible:ring-offset-1 rounded-2xl hover:bg-surface-base"
                >
                  {/* Icon tile */}
                  <div className="w-10 h-10 flex-none rounded-xl border border-border-subtle bg-surface-base flex items-center justify-center">
                    <UserCircle className="h-4.5 w-4.5 text-text-tertiary" style={{ width: 18, height: 18 }} strokeWidth={1.6} />
                  </div>

                  {/* Name + preview */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-semibold tracking-[-0.01em] text-text-primary">Inferred Profile</span>
                      {isDirty && <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400"><span className="w-[7px] h-[7px] rounded-full bg-amber-500 flex-none" />Unsaved</span>}
                    </div>
                    <div className="text-xs text-text-tertiary truncate">
                      {chips.length > 0
                        ? chips.join('  ·  ')
                        : 'Used in every generation — expand to review and correct'}
                    </div>
                  </div>

                  <ChevronDown
                    className={cn('text-text-tertiary transition-transform duration-200', profileExpanded && 'rotate-180')}
                    style={{ width: 18, height: 18 }}
                  />
                </div>

                {/* Drawer */}
                <div style={{ display: 'grid', gridTemplateRows: profileExpanded ? '1fr' : '0fr', transition: 'grid-template-rows 0.18s ease' }}>
                  <div style={{ overflow: 'hidden', minHeight: 0 }}>
                    <div className="px-5 pt-1 pb-5 border-t border-zinc-950/5 dark:border-white/5 space-y-4">

                      {/* Row 1: YoE · Title · Location */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                        <div className="flex flex-col gap-1.5">
                          <label htmlFor="profile-yoe" className="text-xs font-medium text-text-secondary">Years of experience</label>
                          <input
                            id="profile-yoe"
                            type="number"
                            min="0"
                            step="0.5"
                            value={profileFields.yoe_override}
                            onChange={(e) => setProfileFields((p) => ({ ...p, yoe_override: e.target.value }))}
                            placeholder={computedYoe > 0 ? `${computedYoe} (auto-computed)` : 'Auto-computed'}
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

                      {/* Row 2: Contact — Email · Phone · LinkedIn */}
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

                      {/* Row 3: Headline */}
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

                      {/* Row 4: Summary */}
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

                      {/* Save */}
                      {!readOnly && (
                        <div className="flex items-center gap-3 pt-1 border-t border-zinc-950/5 dark:border-white/5">
                          <button
                            type="button"
                            onClick={handleProfileSave}
                            disabled={profileSaving || !isDirty}
                            className={saveBtnCls}
                          >
                            {profileSaving ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving…</> : 'Save signals'}
                          </button>
                          <p className="text-xs text-text-tertiary">These signals are passed to the LLM on every generation.</p>
                        </div>
                      )}

                    </div>
                  </div>
                </div>

              </div>
            );
          })()}

          {/* Parsed experience */}
          <div className="mt-8">
            <ProfileChunkEditor refreshKey={claimsRefreshKey} initialData={initialChunks} initialGroups={initialGroups} noFetch={noFetch} readOnly={readOnly} />
          </div>

        </div>
      </div>

    </div>
  );
}
