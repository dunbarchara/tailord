/* eslint-disable jsx-a11y/no-autofocus */
'use client';

import { useState, useRef, Fragment } from 'react';
import { Sparkles } from 'lucide-react';
import type { EducationEntry, ResumeDraft, ResumeSection } from '@/types';

// ── Helpers ───────────────────────────────────────────────────────────────────

function normalizeUrl(value: string): string {
  if (!value) return value;
  if (value.startsWith('https://')) return value;
  if (value.startsWith('http://')) return `https://${value.slice(7)}`;
  return `https://${value}`;
}

// ── SelectedField ─────────────────────────────────────────────────────────────

type SelectedField =
  | { key: string; kind: 'text'; label: string; value: string; onSave: (v: string) => void }
  | { key: string; kind: 'bullet'; label: string; value: string; claimId: string; onSave: (v: string) => void }
  | { key: string; kind: 'tailord-link'; tailoringLink: string | null; profileLink: string | null; currentType: 'tailoring' | 'profile' | null; onSave: (type: 'tailoring' | 'profile') => void }
  | { key: string; kind: 'linkedin'; url: string; display: string; onSave: (url: string, display: string) => void };

// ── ClickableField ────────────────────────────────────────────────────────────
// Renders content as a selectable region — hover bg, selected blue outline.

function ClickableField({
  fieldKey, selectedKey, onClick, children, style, block = false,
}: {
  fieldKey: string;
  selectedKey: string | null;
  onClick: () => void;
  children: React.ReactNode;
  style?: React.CSSProperties;
  block?: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  const isSelected = selectedKey === fieldKey;
  return (
    <span
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onClick(); }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        cursor: 'pointer', borderRadius: '2px', padding: '0 1px',
        display: block ? 'block' : 'inline',
        background: isSelected ? 'rgba(59,130,246,0.12)' : hovered ? 'rgba(0,0,0,0.04)' : 'transparent',
        outline: isSelected ? '1px solid rgba(59,130,246,0.35)' : 'none',
        transition: 'background 0.1s',
        ...style,
      }}
      title="Click to edit"
    >
      {children}
    </span>
  );
}

// ── BulletLine ────────────────────────────────────────────────────────────────
// Renders a bullet — Sparkles icon shows on hover as hint that AI polish is
// available from the editor bar after clicking.

function BulletLine({
  cid, text, selectedKey, onSelect,
}: {
  cid: string;
  text: string;
  selectedKey: string | null;
  onSelect: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const fieldKey = `bullet:${cid}`;
  const isSelected = selectedKey === fieldKey;

  return (
    <div
      style={{ display: 'flex', alignItems: 'flex-start', gap: '3px', marginBottom: '2px', lineHeight: 1.35 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span style={{ flexShrink: 0, width: '12px', textAlign: 'center', paddingTop: '2px', color: '#888', lineHeight: 1.35 }}>
        {(hovered || isSelected)
          ? <Sparkles size={9} style={{ display: 'inline-block', verticalAlign: 'middle' }} />
          : '•'}
      </span>
      <ClickableField fieldKey={fieldKey} selectedKey={selectedKey} onClick={onSelect} block>
        {text}
      </ClickableField>
    </div>
  );
}

// ── SectionTitle ──────────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: '12pt', fontWeight: 'bold', borderBottom: '0.75pt solid #aaa', paddingBottom: '1px', marginBottom: '5px' }}>
      {children}
    </div>
  );
}

// ── EditorBar ─────────────────────────────────────────────────────────────────
// Bottom bar that shows editing controls for the selected field.
// Keyed by selectedField.key in the parent so state auto-resets on field change.

function EditorBar({
  field,
  tailoringId,
  onClear,
}: {
  field: SelectedField;
  tailoringId: string;
  onClear: () => void;
}) {
  const [textVal, setTextVal] = useState(
    field.kind === 'text' || field.kind === 'bullet' ? field.value : ''
  );
  const [linkedinUrl, setLinkedinUrl] = useState(field.kind === 'linkedin' ? field.url : '');
  const [linkedinDisplay, setLinkedinDisplay] = useState(field.kind === 'linkedin' ? field.display : '');
  const [tailordType, setTailordType] = useState<'tailoring' | 'profile' | null>(
    field.kind === 'tailord-link' ? (field.currentType ?? (field.profileLink ? 'profile' : 'tailoring')) : null
  );
  const [polishing, setPolishing] = useState(false);
  const [pending, setPending] = useState<{ rewritten: string; note: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function growTextarea(el: HTMLTextAreaElement) {
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }

  async function handlePolish() {
    if (field.kind !== 'bullet') return;
    setPolishing(true);
    try {
      const res = await fetch(`/api/tailorings/${tailoringId}/resume/polish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim_ids: [field.claimId] }),
      });
      if (!res.ok) return;
      const data = await res.json();
      const result = data.results?.[field.claimId];
      if (result && !result.unchanged) setPending({ rewritten: result.rewritten, note: result.note });
    } finally {
      setPolishing(false);
    }
  }

  function handleSave() {
    if (field.kind === 'text' || field.kind === 'bullet') {
      if (textVal !== field.value) field.onSave(textVal);
    } else if (field.kind === 'linkedin') {
      field.onSave(normalizeUrl(linkedinUrl), linkedinDisplay);
    } else if (field.kind === 'tailord-link' && tailordType) {
      field.onSave(tailordType);
    }
    onClear();
  }

  const inputStyle: React.CSSProperties = {
    fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '9.5pt', color: '#1a1a1a',
    border: '1px solid #ddd', borderRadius: '4px', padding: '3px 7px',
    outline: 'none', background: '#fff', lineHeight: 1.4,
  };

  const btnBase: React.CSSProperties = {
    fontFamily: 'inherit', fontSize: '9pt', borderRadius: '5px', padding: '3px 10px',
    cursor: 'pointer', border: 'none', lineHeight: 1.4, whiteSpace: 'nowrap', flexShrink: 0,
  };

  return (
    <div style={{
      borderTop: '1px solid #e0e0e0', background: '#f9f9f9', flexShrink: 0,
      padding: '8px 16px', display: 'flex', alignItems: 'flex-start', gap: '8px', flexWrap: 'wrap',
    }}>
      {/* Label */}
      <span style={{ fontSize: '8.5pt', color: '#999', whiteSpace: 'nowrap', paddingTop: '5px', minWidth: '70px' }}>
        {field.kind === 'tailord-link' ? 'Tailord link' : field.kind === 'linkedin' ? 'LinkedIn' : field.label}
      </span>

      {/* Controls */}
      <div style={{ flex: 1, minWidth: '180px' }}>

        {/* Pending rewrite from AI polish */}
        {pending && (
          <div style={{ marginBottom: '6px', fontSize: '9.5pt' }}>
            <div style={{ textDecoration: 'line-through', color: '#bbb' }}>{field.kind === 'bullet' ? field.value : ''}</div>
            <div style={{ color: '#222', fontStyle: 'italic', marginTop: '2px' }}>{pending.rewritten}</div>
            {pending.note && <div style={{ fontSize: '8.5pt', color: '#999', marginTop: '1px' }}>{pending.note}</div>}
            <div style={{ display: 'flex', gap: '8px', marginTop: '5px' }}>
              <button type="button" onClick={() => { if (field.kind === 'bullet') field.onSave(pending.rewritten); onClear(); }}
                style={{ ...btnBase, background: '#dcfce7', color: '#166534' }}>✓ Accept</button>
              <button type="button" onClick={() => setPending(null)}
                style={{ ...btnBase, background: '#f3f4f6', color: '#6b7280' }}>✕ Discard</button>
            </div>
          </div>
        )}

        {/* Text input */}
        {field.kind === 'text' && (
          <input
            autoFocus
            value={textVal}
            onChange={e => setTextVal(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') onClear(); }}
            style={{ ...inputStyle, width: '100%' }}
          />
        )}

        {/* Bullet textarea */}
        {field.kind === 'bullet' && !pending && (
          <textarea
            ref={textareaRef}
            autoFocus
            rows={1}
            value={textVal}
            onChange={e => { setTextVal(e.target.value); growTextarea(e.currentTarget); }}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSave(); } if (e.key === 'Escape') onClear(); }}
            style={{ ...inputStyle, width: '100%', resize: 'none', overflow: 'hidden', display: 'block' }}
          />
        )}

        {/* LinkedIn inputs */}
        {field.kind === 'linkedin' && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '160px' }}>
              <label htmlFor="bar-li-url" style={{ fontSize: '8pt', color: '#999', display: 'block', marginBottom: '2px' }}>URL</label>
              <input
                id="bar-li-url"
                autoFocus
                type="url"
                value={linkedinUrl}
                onChange={e => setLinkedinUrl(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') onClear(); }}
                placeholder="https://linkedin.com/in/…"
                style={{ ...inputStyle, width: '100%' }}
              />
            </div>
            <div style={{ flex: 1, minWidth: '160px' }}>
              <label htmlFor="bar-li-display" style={{ fontSize: '8pt', color: '#999', display: 'block', marginBottom: '2px' }}>Display text</label>
              <input
                id="bar-li-display"
                type="text"
                value={linkedinDisplay}
                onChange={e => setLinkedinDisplay(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') onClear(); }}
                placeholder={linkedinUrl || 'e.g. linkedin.com/in/jane'}
                style={{ ...inputStyle, width: '100%' }}
              />
            </div>
          </div>
        )}

        {/* Tailord link radio */}
        {field.kind === 'tailord-link' && (
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', paddingTop: '3px' }}>
            {field.profileLink && (
              <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer', fontSize: '9pt' }}>
                <input type="radio" name="bar-tailord" checked={tailordType === 'profile'}
                  onChange={() => setTailordType('profile')} />
                Profile page
                <span style={{ color: '#bbb', fontSize: '8.5pt' }}>{field.profileLink}</span>
              </label>
            )}
            {field.tailoringLink && (
              <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer', fontSize: '9pt' }}>
                <input type="radio" name="bar-tailord" checked={tailordType === 'tailoring'}
                  onChange={() => setTailordType('tailoring')} />
                Tailoring page
                <span style={{ color: '#bbb', fontSize: '8.5pt' }}>{field.tailoringLink}</span>
              </label>
            )}
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', paddingTop: '2px', flexShrink: 0 }}>
        {field.kind === 'bullet' && !pending && (
          <button type="button" onClick={handlePolish} disabled={polishing}
            style={{ ...btnBase, background: '#f3f4f6', color: '#555', display: 'flex', alignItems: 'center', gap: '4px' }}>
            {polishing ? '…' : <><Sparkles size={10} /> Polish</>}
          </button>
        )}
        {!pending && (
          <button type="button" onClick={handleSave}
            style={{ ...btnBase, background: '#1a1a1a', color: '#fff' }}>
            Save
          </button>
        )}
        <button type="button" onClick={onClear}
          style={{ ...btnBase, background: 'transparent', color: '#888', border: '1px solid #e0e0e0' }}>
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── ResumeCanvas ──────────────────────────────────────────────────────────────
// Renders the resume as a selectable preview. Clicking a field opens it in the
// editor bar at the bottom. Manages its own layout: scroll area + editor bar.

interface Props {
  draft: ResumeDraft;
  /** Preferred name from session — fallback for old drafts */
  userName?: string | null;
  /** Email from session — fallback for old drafts */
  contactEmail?: string | null;
  /** tailord.app/u/{user-slug}/{tailoring-slug} when the tailoring is shared */
  tailoringPublicLink?: string | null;
  /** tailord.app/u/{user-slug} when the user has a profile */
  profilePublicLink?: string | null;
  tailoringId: string;
  onDraftChange: (draft: ResumeDraft) => void;
}

export function ResumeCanvas({
  draft, userName, contactEmail, tailoringPublicLink, profilePublicLink, tailoringId, onDraftChange,
}: Props) {
  const [selectedField, setSelectedField] = useState<SelectedField | null>(null);

  const selectedKey = selectedField?.key ?? null;

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

  function patchEducation(index: number, updates: Partial<EducationEntry>) {
    const newEdu = (draft.education_data ?? []).map((edu, i) =>
      i === index ? { ...edu, ...updates } : edu
    );
    patchDraft({ education_data: newEdu });
  }

  function sel(field: SelectedField) { setSelectedField(field); }
  function clear() { setSelectedField(null); }

  function getBulletText(section: ResumeSection, cid: string) {
    return section.rewrites?.[cid] ?? section.bullet_snapshots?.[cid] ?? '';
  }

  function getSkillText(cid: string) {
    return draft.skills_rewrites?.[cid] ?? draft.skills_snapshots?.[cid] ?? '';
  }

  const displayName = draft.candidate_name || userName || '—';
  const displayEmail = draft.candidate_email || contactEmail || null;
  const co = draft.contact_override;

  // Display text for tailord link is always the profile URL (shorter, cleaner)
  const tailordDisplayText = profilePublicLink || null;
  const linkedinText = co.linkedin_display || co.linkedin_url || null;
  const hasTailordLink = !!(tailoringPublicLink || profilePublicLink);

  // Contact line as array of {key, node} pairs, joined by | separators
  const contactItems: Array<{ key: string; node: React.ReactNode }> = [];
  if (displayEmail) {
    contactItems.push({ key: 'email', node: <span>{displayEmail}</span> });
  }
  if (tailordDisplayText && hasTailordLink) {
    contactItems.push({
      key: 'tailord',
      node: (
        <ClickableField
          fieldKey="tailord-link"
          selectedKey={selectedKey}
          onClick={() => sel({
            key: 'tailord-link', kind: 'tailord-link',
            tailoringLink: tailoringPublicLink ?? null,
            profileLink: profilePublicLink ?? null,
            currentType: co.tailord_link_type ?? (profilePublicLink ? 'profile' : 'tailoring'),
            onSave: type => patchDraft({ contact_override: { ...co, tailord_link_type: type } }),
          })}
        >{tailordDisplayText}</ClickableField>
      ),
    });
  }
  if (linkedinText) {
    contactItems.push({
      key: 'linkedin',
      node: (
        <ClickableField
          fieldKey="linkedin"
          selectedKey={selectedKey}
          onClick={() => sel({
            key: 'linkedin', kind: 'linkedin',
            url: co.linkedin_url ?? '',
            display: co.linkedin_display ?? '',
            onSave: (url, display) => patchDraft({ contact_override: { ...co, linkedin_url: url || null, linkedin_display: display || null } }),
          })}
        >{linkedinText}</ClickableField>
      ),
    });
  }
  if (co.location) {
    contactItems.push({
      key: 'location',
      node: (
        <ClickableField
          fieldKey="location"
          selectedKey={selectedKey}
          onClick={() => sel({
            key: 'location', kind: 'text', label: 'Location',
            value: co.location!,
            onSave: v => patchDraft({ contact_override: { ...co, location: v || null } }),
          })}
        >{co.location}</ClickableField>
      ),
    });
  }

  const expEntries = draft.sections.filter(s => s.group_type !== 'repository');
  const projEntries = draft.sections.filter(s => s.group_type === 'repository');

  function renderEntry(section: ResumeSection) {
    const isRepo = section.group_type === 'repository';
    const jobTitle = (section.group_type_meta?.['title'] as string) ?? '';
    const hasDateRow = !isRepo && (section.group_start_date != null || section.group_end_date != null);
    const bullets = section.claim_ids
      .map(cid => ({ cid, text: getBulletText(section, cid) }))
      .filter(({ text }) => text);

    return (
      <div key={section.group_id} style={{ marginBottom: '7px', opacity: section.included ? 1 : 0.35, pointerEvents: section.included ? 'auto' : 'none' }}>

        {/* Row 1: org + location */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontWeight: 'bold', flex: 1, minWidth: 0 }}>
            <ClickableField fieldKey={`org:${section.group_id}`} selectedKey={selectedKey} block
              onClick={() => sel({ key: `org:${section.group_id}`, kind: 'text', label: 'Organization', value: section.group_name, onSave: v => patchSection({ ...section, group_name: v }) })}>
              {section.group_name}
            </ClickableField>
          </span>
          {!isRepo && section.group_location && (
            <span style={{ fontWeight: 'bold', flexShrink: 0, whiteSpace: 'nowrap' }}>
              <ClickableField fieldKey={`loc:${section.group_id}`} selectedKey={selectedKey}
                onClick={() => sel({ key: `loc:${section.group_id}`, kind: 'text', label: 'Location', value: section.group_location!, onSave: v => patchSection({ ...section, group_location: v }) })}>
                {section.group_location}
              </ClickableField>
            </span>
          )}
        </div>

        {/* Row 2: title + dates */}
        {!isRepo && (hasDateRow || jobTitle) && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ color: '#222', flex: 1, minWidth: 0 }}>
              <ClickableField fieldKey={`title:${section.group_id}`} selectedKey={selectedKey} block
                onClick={() => sel({ key: `title:${section.group_id}`, kind: 'text', label: 'Job title', value: jobTitle, onSave: v => patchSection({ ...section, group_type_meta: { ...(section.group_type_meta ?? {}), title: v } }) })}>
                {jobTitle || <span style={{ opacity: 0.25, fontStyle: 'italic' }}>—</span>}
              </ClickableField>
            </span>
            {hasDateRow && (
              <span style={{ color: '#222', flexShrink: 0, whiteSpace: 'nowrap' }}>
                <ClickableField fieldKey={`start:${section.group_id}`} selectedKey={selectedKey} style={{ color: '#222' }}
                  onClick={() => sel({ key: `start:${section.group_id}`, kind: 'text', label: 'Start date', value: section.group_start_date ?? '', onSave: v => patchSection({ ...section, group_start_date: v || null }) })}>
                  {section.group_start_date ?? ''}
                </ClickableField>
                {' – '}
                <ClickableField fieldKey={`end:${section.group_id}`} selectedKey={selectedKey} style={{ color: '#222' }}
                  onClick={() => sel({ key: `end:${section.group_id}`, kind: 'text', label: 'End date', value: section.group_end_date ?? 'Present', onSave: v => patchSection({ ...section, group_end_date: (v === 'Present' || !v) ? null : v }) })}>
                  {section.group_end_date ?? 'Present'}
                </ClickableField>
              </span>
            )}
          </div>
        )}

        {/* Bullets */}
        {bullets.length > 0 && (
          <div style={{ paddingLeft: '14px', margin: '3px 0 0' }}>
            {bullets.map(({ cid, text }) => (
              <BulletLine key={cid} cid={cid} text={text} selectedKey={selectedKey}
                onSelect={() => sel({
                  key: `bullet:${cid}`, kind: 'bullet',
                  label: section.group_name,
                  value: text,
                  claimId: cid,
                  onSave: v => patchDraft({ rewrites: { [cid]: v } }),
                })}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const skills = draft.skills_claim_ids.map(cid => ({ cid, text: getSkillText(cid) })).filter(({ text }) => text);
  const education = draft.education_data ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>

      {/* Scrollable canvas — overflow: auto handles both x and y */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', background: '#e8e8e8', display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: '32px 16px' }}>
        <div style={{
          fontFamily: 'Arial, Helvetica, sans-serif', fontSize: '10pt', lineHeight: 1.4,
          color: '#1a1a1a', background: '#fff',
          width: '8.5in', minHeight: '11in', padding: '0.5in',
          boxSizing: 'border-box', boxShadow: '0 4px 24px rgba(0,0,0,0.15)', flexShrink: 0,
        }}>

          {/* Header */}
          <div style={{ marginBottom: '10px', paddingBottom: '8px', borderBottom: '1pt solid #1a1a1a' }}>
            <div style={{ fontSize: '18pt', fontWeight: 'bold', marginBottom: '3px' }}>
              {displayName}
            </div>
            {/* Contact line — individual clickable parts joined by | */}
            <div style={{ fontSize: '9.5pt', color: '#444', display: 'flex', flexWrap: 'wrap', alignItems: 'center' }}>
              {contactItems.length > 0
                ? contactItems.map(({ key, node }, i) => (
                    <Fragment key={key}>
                      {i > 0 && <span style={{ margin: '0 4px', color: '#ccc', userSelect: 'none' }}>|</span>}
                      {node}
                    </Fragment>
                  ))
                : <span style={{ color: '#bbb', fontStyle: 'italic', fontSize: '9pt' }}>—</span>
              }
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
                  <Fragment key={cid}>
                    {i > 0 && ' | '}
                    <ClickableField
                      fieldKey={`skill:${cid}`}
                      selectedKey={selectedKey}
                      onClick={() => sel({ key: `skill:${cid}`, kind: 'text', label: 'Skill', value: text, onSave: v => patchDraft({ skills_rewrites: { [cid]: v } }) })}
                    >{text}</ClickableField>
                  </Fragment>
                ))}
              </div>
            </div>
          )}

          {/* Education */}
          {education.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <SectionTitle>Education</SectionTitle>
              {education.map((edu, i) => (
                <div key={i} style={{ marginBottom: '7px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                    <span style={{ fontWeight: 'bold', flex: 1, minWidth: 0 }}>
                      <ClickableField fieldKey={`edu-name:${i}`} selectedKey={selectedKey} block
                        onClick={() => sel({ key: `edu-name:${i}`, kind: 'text', label: 'Institution', value: edu.name, onSave: v => patchEducation(i, { name: v }) })}>
                        {edu.name}
                      </ClickableField>
                    </span>
                    <span style={{ fontWeight: 'bold', flexShrink: 0, whiteSpace: 'nowrap' }}>
                      <ClickableField fieldKey={`edu-loc:${i}`} selectedKey={selectedKey}
                        onClick={() => sel({ key: `edu-loc:${i}`, kind: 'text', label: 'Location', value: edu.location ?? '', onSave: v => patchEducation(i, { location: v || null }) })}>
                        {edu.location ?? <span style={{ opacity: 0.25, fontStyle: 'italic' }}>—</span>}
                      </ClickableField>
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                    <span style={{ color: '#222', display: 'flex', alignItems: 'baseline', gap: '3px', flex: 1, minWidth: 0 }}>
                      <ClickableField fieldKey={`edu-deg:${i}`} selectedKey={selectedKey}
                        onClick={() => sel({ key: `edu-deg:${i}`, kind: 'text', label: 'Degree', value: edu.degree ?? '', onSave: v => patchEducation(i, { degree: v || null }) })}>
                        {edu.degree ?? <span style={{ opacity: 0.25, fontStyle: 'italic' }}>—</span>}
                      </ClickableField>
                      <span style={{ color: '#ccc', userSelect: 'none' }}>|</span>
                      <ClickableField fieldKey={`edu-dist:${i}`} selectedKey={selectedKey}
                        onClick={() => sel({ key: `edu-dist:${i}`, kind: 'text', label: 'Distinction', value: edu.distinction ?? '', onSave: v => patchEducation(i, { distinction: v || null }) })}>
                        {edu.distinction ?? <span style={{ opacity: 0.25, fontStyle: 'italic' }}>—</span>}
                      </ClickableField>
                    </span>
                    <span style={{ color: '#222', flexShrink: 0, whiteSpace: 'nowrap' }}>
                      <ClickableField fieldKey={`edu-date:${i}`} selectedKey={selectedKey} style={{ color: '#222' }}
                        onClick={() => sel({ key: `edu-date:${i}`, kind: 'text', label: 'Graduation year', value: edu.end_date ?? '', onSave: v => patchEducation(i, { end_date: v || null }) })}>
                        {edu.end_date ?? <span style={{ opacity: 0.25, fontStyle: 'italic' }}>—</span>}
                      </ClickableField>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Editor bar — appears when a field is selected; keyed to reset on field change */}
      {selectedField && (
        <EditorBar
          key={selectedField.key}
          field={selectedField}
          tailoringId={tailoringId}
          onClear={clear}
        />
      )}
    </div>
  );
}
