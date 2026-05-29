/* eslint-disable jsx-a11y/no-autofocus */
'use client';

import { useState, useRef, useEffect } from 'react';
import { Sparkles } from 'lucide-react';
import type { EducationEntry, ResumeDraft, ResumeSection } from '@/types';

// ── InlineEdit ──────────────────────────────────────────────────────────────
// Single-line field: idle = styled span, active = flush <input>.
// block=true → fills container width; block=false → sizes to content via `size`.

function InlineEdit({
  value,
  onSave,
  style,
  block = false,
}: {
  value: string;
  onSave: (v: string) => void;
  style?: React.CSSProperties;
  block?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState('');
  const spanRef = useRef<HTMLSpanElement>(null);

  function startEdit() { setVal(value); setEditing(true); }

  const layoutStyle: React.CSSProperties = block
    ? { display: 'block', width: '100%' }
    : { display: 'inline' };

  if (editing) {
    return (
      <input
        autoFocus
        value={val}
        onChange={e => setVal(e.target.value)}
        onBlur={() => { setEditing(false); if (val !== value) onSave(val); }}
        onKeyDown={e => {
          if (e.key === 'Enter') e.currentTarget.blur();
          if (e.key === 'Escape') setEditing(false);
        }}
        {...(!block && { size: Math.max(val.length + 1, 4) })}
        style={{
          fontFamily: 'inherit', fontSize: 'inherit', fontWeight: 'inherit',
          color: 'inherit', lineHeight: 'inherit',
          border: 'none', borderBottom: '1px solid #bbb', outline: 'none',
          background: 'rgba(0,0,0,0.02)', padding: 0, margin: 0,
          ...layoutStyle, ...style,
        }}
      />
    );
  }

  return (
    <span
      ref={spanRef}
      role="button"
      tabIndex={0}
      onClick={startEdit}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') startEdit(); }}
      onMouseEnter={() => { if (spanRef.current) spanRef.current.style.background = 'rgba(0,0,0,0.04)'; }}
      onMouseLeave={() => { if (spanRef.current) spanRef.current.style.background = 'transparent'; }}
      style={{ cursor: 'text', borderRadius: '2px', padding: '0 1px', transition: 'background 0.1s', ...layoutStyle, ...style }}
      title="Click to edit"
    >
      {value || <span style={{ opacity: 0.25, fontStyle: 'italic' }}>—</span>}
    </span>
  );
}

// ── BulletRow ───────────────────────────────────────────────────────────────
// A single bullet entry in the resume. The left column (fixed 12px) holds the
// bullet indicator (•) or AI polish trigger (Sparkles) — both at a static position
// so the button never floats to the end of a long line.
// Textarea auto-resizes to match the text height on open so content doesn't jump.
// Enter = save (no newlines in bullets).

interface PendingResult { rewritten: string; note: string }

function BulletRow({
  text,
  onSave,
  onPolish,
  polishing,
  pending,
  onAccept,
  onDiscard,
}: {
  text: string;
  onSave: (v: string) => void;
  onPolish: () => void;
  polishing: boolean;
  pending: PendingResult | null;
  onAccept: (rewrite: string) => void;
  onDiscard: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState('');
  const [hovered, setHovered] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea to match rendered text height when entering edit mode
  useEffect(() => {
    if (!editing || !textareaRef.current) return;
    textareaRef.current.style.height = 'auto';
    textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
  }, [editing]);

  function startEdit() { setVal(text); setEditing(true); }

  const showPolish = hovered && !editing && !pending;

  return (
    <span
      style={{ display: 'flex', alignItems: 'flex-start', gap: '3px' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Left: bullet indicator or polish button — always at a fixed position */}
      <span style={{ flexShrink: 0, width: '12px', textAlign: 'center', paddingTop: '1px', lineHeight: 1.35 }}>
        {showPolish ? (
          <button
            type="button"
            onClick={e => { e.stopPropagation(); onPolish(); }}
            disabled={polishing}
            style={{
              background: 'none', border: 'none', padding: 0,
              cursor: polishing ? 'default' : 'pointer',
              lineHeight: 1, color: '#888', display: 'flex', alignItems: 'center',
            }}
            title="Polish with AI"
          >
            {polishing
              ? <span style={{ fontSize: '9pt' }}>…</span>
              : <Sparkles size={10} />}
          </button>
        ) : (
          <span style={{ userSelect: 'none' }}>•</span>
        )}
      </span>

      {/* Right: text or edit area */}
      <span style={{ flex: 1, minWidth: 0 }}>
        {editing ? (
          <textarea
            ref={textareaRef}
            autoFocus
            value={val}
            onChange={e => {
              setVal(e.target.value);
              if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
                textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
              }
            }}
            onBlur={() => { setEditing(false); if (val !== text) onSave(val); }}
            onKeyDown={e => {
              if (e.key === 'Enter') { e.preventDefault(); e.currentTarget.blur(); }
              if (e.key === 'Escape') setEditing(false);
            }}
            rows={1}
            style={{
              fontFamily: 'inherit', fontSize: 'inherit', lineHeight: 'inherit', color: 'inherit',
              width: '100%', border: 'none', borderBottom: '1px solid #bbb', outline: 'none',
              background: 'rgba(0,0,0,0.02)', resize: 'none', padding: 0, margin: 0, overflow: 'hidden',
            }}
          />
        ) : pending ? (
          <span style={{ display: 'block' }}>
            <span style={{ display: 'block', textDecoration: 'line-through', color: '#bbb', fontSize: '9.5pt' }}>{text}</span>
            <span style={{ display: 'block', color: '#222', fontStyle: 'italic' }}>{pending.rewritten}</span>
            {pending.note && (
              <span style={{ display: 'block', fontSize: '9pt', color: '#999' }}>{pending.note}</span>
            )}
            <span style={{ display: 'inline-flex', gap: '10px', marginTop: '3px' }}>
              <button type="button" onClick={() => onAccept(pending.rewritten)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#22c55e', fontSize: '9pt', padding: 0 }}>
                ✓ Accept
              </button>
              <button type="button" onClick={onDiscard}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#999', fontSize: '9pt', padding: 0 }}>
                ✕ Discard
              </button>
            </span>
          </span>
        ) : (
          <span
            role="button"
            tabIndex={0}
            onClick={startEdit}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') startEdit(); }}
            style={{
              cursor: 'text', display: 'block', borderRadius: '2px', padding: '0 1px',
              background: hovered ? 'rgba(0,0,0,0.03)' : 'transparent', transition: 'background 0.1s',
            }}
            title="Click to edit"
          >
            {text}
          </span>
        )}
      </span>
    </span>
  );
}

// ── ContactPopover ──────────────────────────────────────────────────────────
// Opens below the contact line. Editable: linkedin URL + display, location,
// tailord link type (radio). Read-only: email (from profile).

function normalizeUrl(value: string): string {
  if (!value) return value;
  if (value.startsWith('https://')) return value;
  if (value.startsWith('http://')) return `https://${value.slice(7)}`;
  return `https://${value}`;
}

function ContactPopover({
  draft,
  candidateEmail,
  tailoringPublicLink,
  profilePublicLink,
  onClose,
  onPatch,
}: {
  draft: ResumeDraft;
  candidateEmail: string;
  tailoringPublicLink: string | null | undefined;
  profilePublicLink: string | null | undefined;
  onClose: () => void;
  onPatch: (update: Record<string, unknown>) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, [onClose]);

  const co = draft.contact_override;

  function saveField(field: string, value: string) {
    onPatch({ contact_override: { ...co, [field]: value || null } });
  }

  function saveLinkedinUrl(value: string) {
    const normalized = value ? normalizeUrl(value) : null;
    onPatch({ contact_override: { ...co, linkedin_url: normalized } });
  }

  // Tailord link options — display text is always profilePublicLink; href differs
  const tailordOptions: Array<{ type: 'profile' | 'tailoring'; label: string; href: string }> = [];
  if (profilePublicLink) tailordOptions.push({ type: 'profile', label: 'Profile page', href: profilePublicLink });
  if (tailoringPublicLink) tailordOptions.push({ type: 'tailoring', label: 'Tailoring page', href: tailoringPublicLink });

  const currentType: 'profile' | 'tailoring' | null =
    co.tailord_link_type ??
    (profilePublicLink ? 'profile' : tailoringPublicLink ? 'tailoring' : null);

  const fieldStyle: React.CSSProperties = {
    fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '9pt', color: '#222',
    border: '1px solid #ddd', borderRadius: '3px', padding: '2px 5px',
    outline: 'none', width: '100%', background: '#fff',
  };
  const labelStyle: React.CSSProperties = { fontSize: '8.5pt', color: '#888', marginBottom: '2px', display: 'block' };

  return (
    <div
      ref={ref}
      style={{
        position: 'absolute', top: '100%', left: 0, zIndex: 20, marginTop: '4px',
        background: '#fff', border: '1px solid #e0e0e0', borderRadius: '6px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.12)', padding: '10px 12px',
        minWidth: '340px', fontFamily: 'Arial, Helvetica, sans-serif',
      }}
    >
      <div style={{ fontSize: '9pt', fontWeight: 'bold', color: '#555', marginBottom: '8px' }}>
        Contact info
      </div>

      {/* Read-only email */}
      {candidateEmail && (
        <div style={{ marginBottom: '6px' }}>
          <span style={labelStyle}>Email (from account)</span>
          <span style={{ fontSize: '9pt', color: '#999' }}>{candidateEmail}</span>
        </div>
      )}

      {/* Tailord link — radio */}
      {tailordOptions.length > 0 ? (
        <div style={{ marginBottom: '6px' }}>
          <span style={labelStyle}>Tailord link</span>
          {tailordOptions.map(opt => (
            <label key={opt.type} style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '3px', cursor: 'pointer' }}>
              <input
                type="radio"
                name="tailord-link-type"
                checked={currentType === opt.type}
                onChange={() => onPatch({ contact_override: { ...co, tailord_link_type: opt.type } })}
                style={{ marginTop: '1px', flexShrink: 0 }}
              />
              <span style={{ fontSize: '9pt', color: '#444' }}>{opt.label}</span>
              <span style={{ fontSize: '8.5pt', color: '#bbb' }}>{opt.href}</span>
            </label>
          ))}
        </div>
      ) : (
        <div style={{ marginBottom: '6px' }}>
          <span style={labelStyle}>Tailord link</span>
          <span style={{ fontSize: '9pt', color: '#bbb' }}>
            No public link — share this tailoring or set a public profile
          </span>
        </div>
      )}

      {/* LinkedIn URL */}
      <div style={{ marginBottom: '6px' }}>
        <label htmlFor="co-linkedin-url" style={labelStyle}>LinkedIn URL</label>
        <input
          id="co-linkedin-url"
          type="url"
          defaultValue={co.linkedin_url ?? ''}
          onBlur={e => saveLinkedinUrl(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }}
          placeholder="https://linkedin.com/in/…"
          style={fieldStyle}
        />
      </div>

      {/* LinkedIn display */}
      <div style={{ marginBottom: '6px' }}>
        <label htmlFor="co-linkedin-display" style={labelStyle}>
          LinkedIn display text <span style={{ color: '#bbb' }}>(optional — shown instead of URL)</span>
        </label>
        <input
          id="co-linkedin-display"
          type="text"
          defaultValue={co.linkedin_display ?? ''}
          onBlur={e => saveField('linkedin_display', e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }}
          placeholder={co.linkedin_url ?? 'e.g. linkedin.com/in/jane'}
          style={fieldStyle}
        />
      </div>

      {/* Location */}
      <div>
        <label htmlFor="co-location" style={labelStyle}>Location</label>
        <input
          id="co-location"
          type="text"
          defaultValue={co.location ?? ''}
          onBlur={e => saveField('location', e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); }}
          placeholder="City, State"
          style={fieldStyle}
        />
      </div>
    </div>
  );
}

// ── SectionTitle ────────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: '12pt', fontWeight: 'bold', borderBottom: '0.75pt solid #aaa', paddingBottom: '1px', marginBottom: '5px' }}>
      {children}
    </div>
  );
}

// ── ResumeCanvas ─────────────────────────────────────────────────────────────

interface Props {
  draft: ResumeDraft;
  /** Preferred name from session — fallback for old drafts that predate candidate_name snapshot */
  userName?: string | null;
  /** Email from session — fallback for old drafts that predate candidate_email snapshot */
  contactEmail?: string | null;
  /** tailord.app/u/{user-slug}/{tailoring-slug} when the tailoring is publicly shared */
  tailoringPublicLink?: string | null;
  /** tailord.app/u/{slug} when the user has a public profile */
  profilePublicLink?: string | null;
  tailoringId: string;
  onDraftChange: (draft: ResumeDraft) => void;
}

export function ResumeCanvas({ draft, userName, contactEmail, tailoringPublicLink, profilePublicLink, tailoringId, onDraftChange }: Props) {
  const [polishingIds, setPolishingIds] = useState<Set<string>>(new Set());
  const [pendingRewrites, setPendingRewrites] = useState<Record<string, PendingResult>>({});
  const [contactOpen, setContactOpen] = useState(false);

  async function patchDraft(update: Record<string, unknown>) {
    const res = await fetch(`/api/tailorings/${tailoringId}/resume`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update),
    });
    if (!res.ok) return;
    onDraftChange(await res.json());
  }

  function patchSection(section: ResumeSection) {
    patchDraft({ sections: [section] });
  }

  function patchEducation(index: number, updates: Partial<EducationEntry>) {
    const newEdu = (draft.education_data ?? []).map((edu, i) =>
      i === index ? { ...edu, ...updates } : edu
    );
    patchDraft({ education_data: newEdu });
  }

  async function handlePolish(claimId: string) {
    setPolishingIds(prev => new Set(prev).add(claimId));
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/resume/polish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim_ids: [claimId] }),
      });
      if (!res.ok) return;
      const data = await res.json();
      const result = data.results?.[claimId];
      if (result && !result.unchanged) {
        setPendingRewrites(prev => ({ ...prev, [claimId]: { rewritten: result.rewritten, note: result.note } }));
      }
    } finally {
      setPolishingIds(prev => { const next = new Set(prev); next.delete(claimId); return next; });
    }
  }

  function acceptRewrite(claimId: string, rewrite: string) {
    setPendingRewrites(prev => { const next = { ...prev }; delete next[claimId]; return next; });
    patchDraft({ rewrites: { [claimId]: rewrite } });
  }

  function discardRewrite(claimId: string) {
    setPendingRewrites(prev => { const next = { ...prev }; delete next[claimId]; return next; });
  }

  function getBulletText(section: ResumeSection, cid: string): string {
    return section.rewrites?.[cid] ?? section.bullet_snapshots?.[cid] ?? '';
  }

  function getSkillText(cid: string): string {
    return draft.skills_rewrites?.[cid] ?? draft.skills_snapshots?.[cid] ?? '';
  }

  const expEntries = draft.sections.filter(s => s.group_type !== 'repository');
  const projEntries = draft.sections.filter(s => s.group_type === 'repository');

  // Name and email — use draft snapshots, fall back to session values for old drafts
  const displayName = draft.candidate_name || userName || '\u2014';
  const displayEmail = draft.candidate_email || contactEmail || null;

  // Display text for the tailord link is always tailord.app/u/<slug> regardless of which
  // href is selected (profile vs tailoring). The radio only affects the PDF href.
  const co = draft.contact_override;
  const tailordDisplayText = profilePublicLink || null;

  const linkedinText = co.linkedin_display || co.linkedin_url;
  const contactParts = [displayEmail, tailordDisplayText, linkedinText, co.location].filter(Boolean) as string[];

  function renderEntry(section: ResumeSection) {
    const isRepo = section.group_type === 'repository';
    const jobTitle = (section.group_type_meta?.['title'] as string) ?? '';
    const hasDateRow = !isRepo && (section.group_start_date != null || section.group_end_date != null);
    const hasLocation = !isRepo && section.group_location != null;
    const bullets = section.claim_ids
      .map(cid => ({ cid, text: getBulletText(section, cid) }))
      .filter(({ text }) => text);

    return (
      <div
        key={section.group_id}
        style={{ marginBottom: '7px', opacity: section.included ? 1 : 0.35, pointerEvents: section.included ? 'auto' : 'none' }}
      >
        {/* Row 1: org name + location */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontWeight: 'bold', flex: 1, minWidth: 0 }}>
            <InlineEdit value={section.group_name} onSave={v => patchSection({ ...section, group_name: v })} block />
          </span>
          {hasLocation && (
            <span style={{ fontWeight: 'bold', flexShrink: 0, whiteSpace: 'nowrap' }}>
              <InlineEdit
                value={section.group_location!}
                onSave={v => patchSection({ ...section, group_location: v })}
              />
            </span>
          )}
        </div>

        {/* Row 2: job title + dates */}
        {!isRepo && (hasDateRow || jobTitle) && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ color: '#222', flex: 1, minWidth: 0 }}>
              <InlineEdit
                value={jobTitle}
                onSave={v => patchSection({ ...section, group_type_meta: { ...(section.group_type_meta ?? {}), title: v } })}
                block
              />
            </span>
            {hasDateRow && (
              <span style={{ color: '#222', whiteSpace: 'nowrap', flexShrink: 0 }}>
                <InlineEdit
                  value={section.group_start_date ?? ''}
                  onSave={v => patchSection({ ...section, group_start_date: v || null })}
                  style={{ color: '#222' }}
                />
                {' \u2013 '}
                <InlineEdit
                  value={section.group_end_date ?? 'Present'}
                  onSave={v => patchSection({ ...section, group_end_date: (v === 'Present' || v === '') ? null : v })}
                  style={{ color: '#222' }}
                />
              </span>
            )}
          </div>
        )}

        {/* Bullets — custom flex rows, no <ul>/<li>, bullet in fixed left column */}
        {bullets.length > 0 && (
          <div style={{ paddingLeft: '14px', margin: '3px 0 0' }}>
            {bullets.map(({ cid, text }) => (
              <div key={cid} style={{ marginBottom: '2px', lineHeight: 1.35 }}>
                <BulletRow
                  text={text}
                  onSave={v => patchDraft({ rewrites: { [cid]: v } })}
                  onPolish={() => handlePolish(cid)}
                  polishing={polishingIds.has(cid)}
                  pending={pendingRewrites[cid] ?? null}
                  onAccept={rewrite => acceptRewrite(cid, rewrite)}
                  onDiscard={() => discardRewrite(cid)}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  const skills = draft.skills_claim_ids
    .map(cid => ({ cid, text: getSkillText(cid) }))
    .filter(({ text }) => text);

  const education = draft.education_data ?? [];

  return (
    <div
      style={{
        fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '10pt', lineHeight: 1.4,
        color: '#1a1a1a', background: '#fff',
        width: '8.5in', minHeight: '11in', padding: '0.5in',
        boxSizing: 'border-box', boxShadow: '0 4px 24px rgba(0,0,0,0.15)', flexShrink: 0,
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: '10px', paddingBottom: '8px', borderBottom: '1pt solid #1a1a1a' }}>
        <div style={{ fontSize: '18pt', fontWeight: 'bold', marginBottom: '3px' }}>
          {displayName}
        </div>

        {/* Contact line — click to open popover */}
        <div style={{ position: 'relative' }}>
          <span
            role="button"
            tabIndex={0}
            onClick={() => setContactOpen(v => !v)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setContactOpen(v => !v); }}
            style={{
              fontSize: '9.5pt', color: '#444', cursor: 'pointer',
              borderRadius: '2px', padding: '0 1px', display: 'inline-block',
              borderBottom: contactOpen ? '1px solid #bbb' : '1px dashed transparent',
              transition: 'border-color 0.1s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderBottomColor = '#ccc'; }}
            onMouseLeave={e => {
              if (!contactOpen) (e.currentTarget as HTMLElement).style.borderBottomColor = 'transparent';
            }}
            title="Click to edit contact info"
          >
            {contactParts.length > 0 ? contactParts.join(' | ') : 'Click to add contact info'}
          </span>
          {contactOpen && (
            <ContactPopover
              draft={draft}
              candidateEmail={displayEmail ?? ''}
              tailoringPublicLink={tailoringPublicLink}
              profilePublicLink={profilePublicLink}
              onClose={() => setContactOpen(false)}
              onPatch={patchDraft}
            />
          )}
        </div>
      </div>

      {/* Experience */}
      {expEntries.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <SectionTitle>Experience</SectionTitle>
          {expEntries.map(renderEntry)}
        </div>
      )}

      {/* Projects */}
      {projEntries.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <SectionTitle>Projects</SectionTitle>
          {projEntries.map(renderEntry)}
        </div>
      )}

      {/* Skills */}
      {skills.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <SectionTitle>Skills</SectionTitle>
          <div style={{ fontSize: '10pt', lineHeight: 1.5 }}>
            {skills.map(({ cid, text }, i) => (
              <span key={cid}>
                {i > 0 && ' | '}
                <InlineEdit value={text} onSave={v => patchDraft({ skills_rewrites: { [cid]: v } })} />
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Education — distinction shown inline with degree; all fields editable */}
      {education.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <SectionTitle>Education</SectionTitle>
          {education.map((edu, i) => (
            <div key={i} style={{ marginBottom: '7px' }}>
              {/* Row 1: institution + location */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontWeight: 'bold', flex: 1, minWidth: 0 }}>
                  <InlineEdit value={edu.name} onSave={v => patchEducation(i, { name: v })} block />
                </span>
                <span style={{ fontWeight: 'bold', flexShrink: 0, whiteSpace: 'nowrap' }}>
                  <InlineEdit
                    value={edu.location ?? ''}
                    onSave={v => patchEducation(i, { location: v || null })}
                  />
                </span>
              </div>
              {/* Row 2: degree | distinction + end date */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ color: '#222', display: 'flex', alignItems: 'baseline', gap: '3px', flex: 1, minWidth: 0 }}>
                  <InlineEdit
                    value={edu.degree ?? ''}
                    onSave={v => patchEducation(i, { degree: v || null })}
                  />
                  <span style={{ color: '#ccc', userSelect: 'none' }}>|</span>
                  <InlineEdit
                    value={edu.distinction ?? ''}
                    onSave={v => patchEducation(i, { distinction: v || null })}
                  />
                </span>
                <span style={{ color: '#222', flexShrink: 0, whiteSpace: 'nowrap' }}>
                  <InlineEdit
                    value={edu.end_date ?? ''}
                    onSave={v => patchEducation(i, { end_date: v || null })}
                    style={{ color: '#222' }}
                  />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
