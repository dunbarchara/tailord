/* eslint-disable jsx-a11y/no-autofocus */
'use client';

import { useState, Fragment } from 'react';
import { Sparkles } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import type { EducationEntry as EduEntry, ResumeDraft, ResumeSection } from '@/types';

// ── Helpers ───────────────────────────────────────────────────────────────────

function normalizeUrl(value: string): string {
  if (!value) return value;
  if (value.startsWith('https://')) return value;
  if (value.startsWith('http://')) return `https://${value.slice(7)}`;
  return `https://${value}`;
}

// ── Popover UI primitives ─────────────────────────────────────────────────────

function PopoverCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-surface-elevated border border-border-default rounded-xl shadow-lg p-3 flex flex-col gap-2.5">
      {children}
    </div>
  );
}

function PopLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] font-medium text-text-tertiary leading-none">{children}</div>;
}

function PopInput({
  label, value, onChange, onKeyDown, placeholder, type = 'text', autoFocus = false,
}: {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  placeholder?: string;
  type?: string;
  autoFocus?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 flex-1 min-w-0">
      {label && <label className="text-[11px] text-text-tertiary font-medium leading-none">{label}</label>}
      <input
        autoFocus={autoFocus}
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        className="h-7 px-2.5 text-xs rounded-lg border border-border-default bg-surface-base text-text-primary placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-brand-primary/20 focus:border-border-focus transition-colors"
      />
    </div>
  );
}

function PopActions({
  onSave, onCancel, extra,
}: {
  onSave: () => void;
  onCancel: () => void;
  extra?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 pt-0.5">
      {extra}
      <div className="flex-1" />
      <button
        type="button" onClick={onCancel}
        className="h-7 px-3 text-xs rounded-lg border border-border-default text-text-secondary hover:bg-surface-overlay transition-colors"
      >
        Cancel
      </button>
      <button
        type="button" onClick={onSave}
        className="h-7 px-3 text-xs rounded-lg bg-brand-primary text-white font-medium hover:opacity-90 transition-colors"
      >
        Save
      </button>
    </div>
  );
}

// ── Shared hover bar style ────────────────────────────────────────────────────

function barStyle(open: boolean, hovered: boolean): React.CSSProperties {
  return {
    cursor: 'pointer',
    borderRadius: '3px',
    padding: '2px 4px',
    margin: '0 -4px',
    background: open ? 'rgba(59,130,246,0.08)' : hovered ? 'rgba(0,0,0,0.04)' : 'transparent',
    transition: 'background 0.1s',
  };
}

// Transparent wrapper so PopoverCard handles all card styling
const POPOVER_TRANSPARENT: React.CSSProperties = {
  padding: 0,
  background: 'transparent',
  boxShadow: 'none',
  border: 'none',
};

// ── Domain popover forms ───────────────────────────────────────────────────────
// These are pure form content — no positioning logic.
// Each is rendered inside a <PopoverContent> by its parent trigger component.

function ContactPopover({
  draft, tailoringPublicLink, profilePublicLink, onSave, onClose,
}: {
  draft: ResumeDraft;
  tailoringPublicLink?: string | null;
  profilePublicLink?: string | null;
  onSave: (patch: Record<string, unknown>) => void;
  onClose: () => void;
}) {
  const co = draft.contact_override;
  const hasTailordLink = !!(tailoringPublicLink || profilePublicLink);

  const [email, setEmail] = useState(draft.candidate_email ?? '');
  const [tailordType, setTailordType] = useState<'tailoring' | 'profile'>(
    co.tailord_link_type ?? (profilePublicLink ? 'profile' : 'tailoring'),
  );
  const [linkedinUrl, setLinkedinUrl] = useState(co.linkedin_url ?? '');
  const [linkedinDisplay, setLinkedinDisplay] = useState(co.linkedin_display ?? '');
  const [location, setLocation] = useState(co.location ?? '');

  function handleSave() {
    onSave({
      candidate_email: email,
      contact_override: {
        ...co,
        linkedin_url: normalizeUrl(linkedinUrl) || null,
        linkedin_display: linkedinDisplay || null,
        location: location || null,
        tailord_link_type: hasTailordLink ? tailordType : co.tailord_link_type,
      },
    });
    onClose();
  }

  const esc = (e: React.KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Escape') onClose(); };

  return (
    <PopoverCard>
      <PopLabel>Contact</PopLabel>
      <PopInput label="Email" value={email} onChange={setEmail} type="email" autoFocus onKeyDown={esc} />

      {hasTailordLink && (
        <div className="flex flex-col gap-1.5">
          <div className="text-[11px] text-text-tertiary font-medium leading-none">Tailord link</div>
          <div className="flex flex-col gap-2">
            {profilePublicLink && (
              <label className="flex items-start gap-2 cursor-pointer">
                <input type="radio" name="cp-tl" aria-label="Profile page" checked={tailordType === 'profile'} onChange={() => setTailordType('profile')} className="mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-text-primary font-medium">Profile page</p>
                  <p className="text-[11px] text-text-tertiary">{profilePublicLink}</p>
                </div>
              </label>
            )}
            {tailoringPublicLink && (
              <label className="flex items-start gap-2 cursor-pointer">
                <input type="radio" name="cp-tl" aria-label="This tailoring" checked={tailordType === 'tailoring'} onChange={() => setTailordType('tailoring')} className="mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs text-text-primary font-medium">This tailoring</p>
                  <p className="text-[11px] text-text-tertiary">{tailoringPublicLink}</p>
                </div>
              </label>
            )}
          </div>
        </div>
      )}

      <PopInput label="LinkedIn URL" value={linkedinUrl} onChange={setLinkedinUrl} type="url" placeholder="https://linkedin.com/in/…" onKeyDown={esc} />
      <PopInput label="LinkedIn display" value={linkedinDisplay} onChange={setLinkedinDisplay} placeholder={linkedinUrl || 'e.g. linkedin.com/in/jane'} onKeyDown={esc} />
      <PopInput label="Location" value={location} onChange={setLocation} placeholder="City, Country" onKeyDown={esc} />

      <PopActions onSave={handleSave} onCancel={onClose} />
    </PopoverCard>
  );
}

function BulletPopover({
  text, claimId, sectionName, tailoringId, onSave, onClose,
}: {
  text: string;
  claimId: string;
  sectionName: string;
  tailoringId: string;
  onSave: (v: string) => void;
  onClose: () => void;
}) {
  const [val, setVal] = useState(text);
  const [polishing, setPolishing] = useState(false);
  const [pending, setPending] = useState<{ rewritten: string; note: string } | null>(null);

  function handleSave() { if (val !== text) onSave(val); onClose(); }

  async function handlePolish() {
    setPolishing(true);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/resume/polish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim_ids: [claimId] }),
      });
      if (!res.ok) return;
      const data = await res.json();
      const result = data.results?.[claimId];
      if (result && !result.unchanged) setPending({ rewritten: result.rewritten, note: result.note });
    } finally {
      setPolishing(false);
    }
  }

  return (
    <PopoverCard>
      <PopLabel>{sectionName}</PopLabel>

      {pending ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-text-secondary line-through opacity-60 leading-snug">{text}</p>
          <p className="text-xs text-text-primary italic leading-snug">{pending.rewritten}</p>
          {pending.note && <p className="text-[11px] text-text-tertiary">{pending.note}</p>}
          <div className="flex gap-2">
            <button type="button"
              onClick={() => { onSave(pending.rewritten); onClose(); }}
              className="h-7 px-3 text-xs rounded-lg bg-success text-white font-medium hover:opacity-90 transition-colors">
              ✓ Accept
            </button>
            <button type="button" onClick={() => setPending(null)}
              className="h-7 px-3 text-xs rounded-lg border border-border-default text-text-secondary hover:bg-surface-overlay transition-colors">
              Discard
            </button>
          </div>
        </div>
      ) : (
        <>
          <textarea
            autoFocus
            rows={2}
            value={val}
            onChange={e => setVal(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSave(); } }}
            className="w-full text-xs px-2.5 py-2 rounded-lg border border-border-default bg-surface-base text-text-primary resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary/20 focus:border-border-focus transition-colors leading-snug"
          />
          <PopActions
            onSave={handleSave}
            onCancel={onClose}
            extra={
              <button type="button" onClick={handlePolish} disabled={polishing}
                className="h-7 px-2.5 text-xs rounded-lg border border-border-default text-text-secondary hover:bg-surface-overlay flex items-center gap-1.5 transition-colors disabled:opacity-50 shrink-0">
                <Sparkles size={11} />
                {polishing ? 'Polishing…' : 'Polish'}
              </button>
            }
          />
        </>
      )}
    </PopoverCard>
  );
}

function SectionPopover({
  section, onSave, onClose,
}: {
  section: ResumeSection;
  onSave: (s: ResumeSection) => void;
  onClose: () => void;
}) {
  const isRepo = section.group_type === 'repository';
  const [name, setName] = useState(section.group_name);
  const [title, setTitle] = useState((section.group_type_meta?.['title'] as string) ?? '');
  const [startDate, setStartDate] = useState(section.group_start_date ?? '');
  const [endDate, setEndDate] = useState(section.group_end_date ?? '');
  const [location, setLocation] = useState(section.group_location ?? '');

  function handleSave() {
    onSave({
      ...section,
      group_name: name,
      group_type_meta: isRepo ? section.group_type_meta : { ...(section.group_type_meta ?? {}), title },
      group_start_date: startDate || null,
      group_end_date: endDate || null,
      group_location: location || null,
    });
    onClose();
  }

  const esc = (e: React.KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Escape') onClose(); };

  return (
    <PopoverCard>
      <PopLabel>{isRepo ? 'Repository' : 'Role'}</PopLabel>
      <PopInput label={isRepo ? 'Name' : 'Organization'} value={name} onChange={setName} autoFocus onKeyDown={esc} />
      {!isRepo && <PopInput label="Title / role" value={title} onChange={setTitle} onKeyDown={esc} />}
      {!isRepo && (
        <div className="flex gap-2">
          <PopInput label="Start date" value={startDate} onChange={setStartDate} placeholder="e.g. Jan 2022" onKeyDown={esc} />
          <PopInput label="End date" value={endDate} onChange={setEndDate} placeholder="Present" onKeyDown={esc} />
        </div>
      )}
      {!isRepo && <PopInput label="Location" value={location} onChange={setLocation} placeholder="City, Country" onKeyDown={esc} />}
      <PopActions onSave={handleSave} onCancel={onClose} />
    </PopoverCard>
  );
}

function EducationPopover({
  edu, index, onSave, onClose,
}: {
  edu: EduEntry;
  index: number;
  onSave: (i: number, u: Partial<EduEntry>) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(edu.name);
  const [degree, setDegree] = useState(edu.degree ?? '');
  const [distinction, setDistinction] = useState(edu.distinction ?? '');
  const [endDate, setEndDate] = useState(edu.end_date ?? '');
  const [location, setLocation] = useState(edu.location ?? '');

  function handleSave() {
    onSave(index, {
      name,
      degree: degree || null,
      distinction: distinction || null,
      end_date: endDate || null,
      location: location || null,
    });
    onClose();
  }

  const esc = (e: React.KeyboardEvent<HTMLInputElement>) => { if (e.key === 'Escape') onClose(); };

  return (
    <PopoverCard>
      <PopLabel>Education</PopLabel>
      <PopInput label="Institution" value={name} onChange={setName} autoFocus onKeyDown={esc} />
      <PopInput label="Degree" value={degree} onChange={setDegree} placeholder="e.g. BSc Computer Science" onKeyDown={esc} />
      <div className="flex gap-2">
        <PopInput label="Distinction / honors" value={distinction} onChange={setDistinction} placeholder="e.g. First Class" onKeyDown={esc} />
        <PopInput label="Year" value={endDate} onChange={setEndDate} placeholder="e.g. 2020" onKeyDown={esc} />
      </div>
      <PopInput label="Location" value={location} onChange={setLocation} placeholder="City, Country" onKeyDown={esc} />
      <PopActions onSave={handleSave} onCancel={onClose} />
    </PopoverCard>
  );
}

function SkillsPopover({
  skills, skillClaimIds, onSave, onClose,
}: {
  skills: { cid: string; text: string }[];
  skillClaimIds: string[];
  onSave: (rewrites: Record<string, string>) => void;
  onClose: () => void;
}) {
  const [val, setVal] = useState(skills.map(s => s.text).join('\n'));

  function handleSave() {
    const lines = val.split('\n').map(l => l.trim()).filter(Boolean);
    const rewrites: Record<string, string> = {};
    skillClaimIds.forEach((cid, i) => { if (i < lines.length) rewrites[cid] = lines[i]; });
    onSave(rewrites);
    onClose();
  }

  return (
    <PopoverCard>
      <PopLabel>Skills — one per line</PopLabel>
      <textarea
        autoFocus
        value={val}
        onChange={e => setVal(e.target.value)}
        onWheel={e => e.stopPropagation()}
        rows={Math.min(skills.length + 1, 10)}
        className="w-full text-xs px-2.5 py-2 rounded-lg border border-border-default bg-surface-base text-text-primary resize-none overflow-y-auto focus:outline-none focus:ring-2 focus:ring-brand-primary/20 focus:border-border-focus transition-colors leading-relaxed"
      />
      <PopActions onSave={handleSave} onCancel={onClose} />
    </PopoverCard>
  );
}

// ── Resume building blocks ────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: '12pt', fontWeight: 'bold', borderBottom: '0.75pt solid #aaa', paddingBottom: '1px', marginBottom: '5px' }}>
      {children}
    </div>
  );
}

function ContactBar({
  draft, tailoringPublicLink, profilePublicLink, onSave,
}: {
  draft: ResumeDraft;
  tailoringPublicLink?: string | null;
  profilePublicLink?: string | null;
  onSave: (patch: Record<string, unknown>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);

  const co = draft.contact_override;
  const displayEmail = draft.candidate_email || null;
  const tailordDisplay = profilePublicLink || tailoringPublicLink;
  const linkedinText = co.linkedin_display || co.linkedin_url;

  const parts: string[] = [];
  if (displayEmail) parts.push(displayEmail);
  if (tailordDisplay && (tailoringPublicLink || profilePublicLink)) parts.push(tailordDisplay);
  if (linkedinText) parts.push(linkedinText);
  if (co.location) parts.push(co.location);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          role="button"
          tabIndex={0}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          style={{
            fontSize: '9.5pt', color: '#444',
            display: 'flex', flexWrap: 'wrap', alignItems: 'center',
            ...barStyle(open, hovered),
            padding: '2px 3px', margin: '0 -3px',
          }}
          title="Click to edit contact info"
        >
          {parts.length > 0
            ? parts.map((p, i) => (
                <Fragment key={i}>
                  {i > 0 && <span style={{ margin: '0 4px', color: '#ccc', userSelect: 'none' }}>|</span>}
                  {p}
                </Fragment>
              ))
            : <span style={{ color: '#bbb', fontStyle: 'italic', fontSize: '9pt' }}>—</span>
          }
        </div>
      </PopoverTrigger>
      <PopoverContent align="start" alignOffset={20} sideOffset={3} style={{ ...POPOVER_TRANSPARENT, width: '380px' }}>
        <ContactPopover
          draft={draft}
          tailoringPublicLink={tailoringPublicLink}
          profilePublicLink={profilePublicLink}
          onSave={onSave}
          onClose={() => setOpen(false)}
        />
      </PopoverContent>
    </Popover>
  );
}

function BulletLine({
  cid, text, sectionName, tailoringId, onSave,
}: {
  cid: string;
  text: string;
  sectionName: string;
  tailoringId: string;
  onSave: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);

  return (
    <div
      style={{ display: 'flex', alignItems: 'flex-start', gap: '3px', marginBottom: '2px', lineHeight: 1.35 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span style={{ flexShrink: 0, width: '12px', textAlign: 'center', paddingTop: '2px', color: '#888', lineHeight: 1.35 }}>
        •
      </span>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <span
            role="button"
            tabIndex={0}
            style={{
              cursor: 'pointer', flex: 1,
              background: open ? 'rgba(59,130,246,0.08)' : hovered ? 'rgba(0,0,0,0.04)' : 'transparent',
              borderRadius: '2px', padding: '0 2px', transition: 'background 0.1s',
            }}
            title="Click to edit"
          >
            {text}
          </span>
        </PopoverTrigger>
        <PopoverContent align="start" alignOffset={20} sideOffset={3} style={{ ...POPOVER_TRANSPARENT, width: '700px' }}>
          <BulletPopover
            text={text}
            claimId={cid}
            sectionName={sectionName}
            tailoringId={tailoringId}
            onSave={onSave}
            onClose={() => setOpen(false)}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}

function SectionEntry({
  section, getBulletText, tailoringId, patchSection, patchDraft,
}: {
  section: ResumeSection;
  getBulletText: (s: ResumeSection, cid: string) => string;
  tailoringId: string;
  patchSection: (s: ResumeSection) => void;
  patchDraft: (u: Record<string, unknown>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const isRepo = section.group_type === 'repository';
  const jobTitle = (section.group_type_meta?.['title'] as string) ?? '';
  const hasDateRow = !isRepo && (section.group_start_date != null || section.group_end_date != null);
  const bullets = section.claim_ids
    .map(cid => ({ cid, text: getBulletText(section, cid) }))
    .filter(({ text }) => text);

  return (
    <div style={{ marginBottom: '7px', opacity: section.included ? 1 : 0.35, pointerEvents: section.included ? 'auto' : 'none' }}>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <div
            role="button"
            tabIndex={0}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={barStyle(open, hovered)}
            title="Click to edit"
          >
            {/* Row 1: org + location */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontWeight: 'bold', flex: 1, minWidth: 0 }}>
                {section.group_name || <em style={{ opacity: 0.35 }}>—</em>}
              </span>
              {!isRepo && section.group_location && (
                <span style={{ fontWeight: 'bold', flexShrink: 0, whiteSpace: 'nowrap' }}>{section.group_location}</span>
              )}
            </div>
            {/* Row 2: title + dates */}
            {!isRepo && (hasDateRow || jobTitle) && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ color: '#222', flex: 1, minWidth: 0 }}>
                  {jobTitle || <em style={{ opacity: 0.25 }}>—</em>}
                </span>
                {hasDateRow && (
                  <span style={{ color: '#222', flexShrink: 0, whiteSpace: 'nowrap' }}>
                    {section.group_start_date ?? ''}{' – '}{section.group_end_date ?? 'Present'}
                  </span>
                )}
              </div>
            )}
          </div>
        </PopoverTrigger>
        <PopoverContent align="start" alignOffset={20} sideOffset={3} style={{ ...POPOVER_TRANSPARENT, width: '400px' }}>
          <SectionPopover
            section={section}
            onSave={patchSection}
            onClose={() => setOpen(false)}
          />
        </PopoverContent>
      </Popover>

      {bullets.length > 0 && (
        <div style={{ paddingLeft: '14px', margin: '3px 0 0' }}>
          {bullets.map(({ cid, text }) => (
            <BulletLine
              key={cid}
              cid={cid}
              text={text}
              sectionName={section.group_name}
              tailoringId={tailoringId}
              onSave={v => patchDraft({ rewrites: { [cid]: v } })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function EducationEntryRow({
  edu, index, patchEducation,
}: {
  edu: EduEntry;
  index: number;
  patchEducation: (i: number, u: Partial<EduEntry>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);

  return (
    <div style={{ marginBottom: '7px' }}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <div
            role="button"
            tabIndex={0}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={barStyle(open, hovered)}
            title="Click to edit"
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ fontWeight: 'bold', flex: 1, minWidth: 0 }}>{edu.name}</span>
              {edu.location && <span style={{ fontWeight: 'bold', flexShrink: 0, whiteSpace: 'nowrap' }}>{edu.location}</span>}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
              <span style={{ color: '#222', flex: 1, minWidth: 0 }}>
                {[edu.degree, edu.distinction].filter(Boolean).join(' | ') || <em style={{ opacity: 0.25 }}>—</em>}
              </span>
              {edu.end_date && <span style={{ color: '#222', flexShrink: 0 }}>{edu.end_date}</span>}
            </div>
          </div>
        </PopoverTrigger>
        <PopoverContent align="start" alignOffset={20} sideOffset={3} style={{ ...POPOVER_TRANSPARENT, width: '400px' }}>
          <EducationPopover
            edu={edu}
            index={index}
            onSave={patchEducation}
            onClose={() => setOpen(false)}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}

function SkillsBar({
  skills, skillClaimIds, onSave,
}: {
  skills: { cid: string; text: string }[];
  skillClaimIds: string[];
  onSave: (rewrites: Record<string, string>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          role="button"
          tabIndex={0}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          style={{ ...barStyle(open, hovered), fontSize: '10pt', lineHeight: 1.5 }}
          title="Click to edit skills"
        >
          {skills.map(({ text }, i) => (
            <Fragment key={i}>{i > 0 && ' | '}{text}</Fragment>
          ))}
        </div>
      </PopoverTrigger>
      <PopoverContent align="start" alignOffset={20} sideOffset={3} style={{ ...POPOVER_TRANSPARENT, width: '360px' }}>
        <SkillsPopover
          skills={skills}
          skillClaimIds={skillClaimIds}
          onSave={onSave}
          onClose={() => setOpen(false)}
        />
      </PopoverContent>
    </Popover>
  );
}

// ── ResumeCanvas ──────────────────────────────────────────────────────────────

interface Props {
  draft: ResumeDraft;
  userName?: string | null;
  contactEmail?: string | null;
  /** tailord.app/t/{slug} when the tailoring is shared */
  tailoringPublicLink?: string | null;
  /** tailord.app/u/{slug} when the user has a public profile */
  profilePublicLink?: string | null;
  tailoringId: string;
  onDraftChange: (draft: ResumeDraft) => void;
}

export function ResumeCanvas({
  draft, userName, contactEmail, tailoringPublicLink, profilePublicLink, tailoringId, onDraftChange,
}: Props) {
  async function patchDraft(update: Record<string, unknown>) {
    const res = await fetch(`/api/tailorings/${tailoringId}/resume`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    if (!res.ok) return;
    onDraftChange(await res.json());
  }

  function patchSection(section: ResumeSection) { patchDraft({ sections: [section] }); }

  function patchEducation(index: number, updates: Partial<EduEntry>) {
    const newEdu = (draft.education_data ?? []).map((edu, i) =>
      i === index ? { ...edu, ...updates } : edu,
    );
    patchDraft({ education_data: newEdu });
  }

  function getBulletText(section: ResumeSection, cid: string) {
    return section.rewrites?.[cid] ?? section.bullet_snapshots?.[cid] ?? '';
  }

  function getSkillText(cid: string) {
    return draft.skills_rewrites?.[cid] ?? draft.skills_snapshots?.[cid] ?? '';
  }

  const displayName = draft.candidate_name || userName || '—';
  const expEntries = draft.sections.filter(s => s.group_type !== 'repository');
  const projEntries = draft.sections.filter(s => s.group_type === 'repository');
  const skills = draft.skills_claim_ids
    .map(cid => ({ cid, text: getSkillText(cid) }))
    .filter(({ text }) => text);
  const education = draft.education_data ?? [];

  // Merge session fallbacks into draft for display (doesn't mutate draft)
  const displayDraft: ResumeDraft = {
    ...draft,
    candidate_email: draft.candidate_email || contactEmail || '',
  };

  return (
    <div style={{
      flex: 1, minHeight: 0, overflow: 'auto', background: '#e8e8e8',
      display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: '32px 16px',
    }}>
      <div style={{
        fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '10pt', lineHeight: 1.4,
        color: '#1a1a1a', background: '#fff',
        width: '8.5in', minHeight: '11in', padding: '0.5in',
        boxSizing: 'border-box', boxShadow: '0 4px 24px rgba(0,0,0,0.15)', flexShrink: 0,
      }}>

        {/* Header */}
        <div style={{ marginBottom: '10px', paddingBottom: '8px', borderBottom: '1pt solid #1a1a1a' }}>
          <div style={{ fontSize: '18pt', fontWeight: 'bold', marginBottom: '3px' }}>{displayName}</div>
          <ContactBar
            draft={displayDraft}
            tailoringPublicLink={tailoringPublicLink}
            profilePublicLink={profilePublicLink}
            onSave={patchDraft}
          />
        </div>

        {/* Experience */}
        {expEntries.length > 0 && (
          <div style={{ marginBottom: '10px' }}>
            <SectionTitle>Experience</SectionTitle>
            {expEntries.map(s => (
              <SectionEntry key={s.group_id} section={s} getBulletText={getBulletText}
                tailoringId={tailoringId} patchSection={patchSection} patchDraft={patchDraft} />
            ))}
          </div>
        )}

        {/* Projects */}
        {projEntries.length > 0 && (
          <div style={{ marginBottom: '10px' }}>
            <SectionTitle>Projects</SectionTitle>
            {projEntries.map(s => (
              <SectionEntry key={s.group_id} section={s} getBulletText={getBulletText}
                tailoringId={tailoringId} patchSection={patchSection} patchDraft={patchDraft} />
            ))}
          </div>
        )}

        {/* Skills */}
        {skills.length > 0 && (
          <div style={{ marginBottom: '10px' }}>
            <SectionTitle>Skills</SectionTitle>
            <SkillsBar
              skills={skills}
              skillClaimIds={draft.skills_claim_ids}
              onSave={rewrites => patchDraft({ skills_rewrites: rewrites })}
            />
          </div>
        )}

        {/* Education */}
        {education.length > 0 && (
          <div style={{ marginBottom: '10px' }}>
            <SectionTitle>Education</SectionTitle>
            {education.map((edu, i) => (
              <EducationEntryRow key={i} edu={edu} index={i} patchEducation={patchEducation} />
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
